"""
Dashboard API views for mobile app - JSON responses
"""
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from pandora.models import Employee, Role, EmployeeRole, Task, LogEntry, LogTag, EntryTagLink, PersonalTopTaskConfig, CompanyTopTaskConfig, Announcement
from pandora.utils import check_admin_role, check_ceo_role, check_boss_role, has_admin_or_ceo_access, check_task_permission
from pandora.message_service import send_announcement
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


def _load_persisted_personal_task_ids(request, employee_id):
    session_key = f'personal_top_tasks_{employee_id}'
    session_version_key = f'personal_top_tasks_version_{employee_id}'

    config = PersonalTopTaskConfig.objects.filter(employee_id=employee_id).first()
    if config:
        config_task_ids = config.task_ids or []
        config_version = config.updated_at.isoformat()
        cached_version = request.session.get(session_version_key)
        cached_tasks = request.session.get(session_key) if cached_version == config_version else None

        if cached_tasks is not None:
            return cached_tasks

        request.session[session_key] = config_task_ids
        request.session[session_version_key] = config_version
        return config_task_ids

    if session_key in request.session:
        return request.session.get(session_key, [])
    return None

def _load_company_top_task_ids(request=None):
    conf = CompanyTopTaskConfig.objects.order_by('-updated_at').first()
    if conf:
        return conf.task_ids or []
    if request is not None:
        return request.session.get('company_top_tasks', [])
    return []


@require_GET
def dashboard_api(request):
    """返回dashboard数据的JSON API"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    try:
        current_work_id = request.session.get('current_employee_work_id')
        current_employee_name = request.session.get('current_employee_name')
        current_employee_id = request.session.get('current_employee_id')
        
        # 获取当前员工对象
        current_employee = Employee.objects.get(work_id=current_work_id)
        
        # 检查是否有管理员角色
        has_admin_role = check_admin_role(current_employee)
        has_admin_or_ceo = has_admin_or_ceo_access(current_employee)
        
        date_str = request.GET.get('date')
        if date_str:
            try:
                today = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                today = timezone.now().date()
        else:
            today = timezone.now().date()
        
        # 任务统计（今日任务）
        if has_admin_or_ceo:
            # 管理员/CEO：查看所有任务
            today_tasks = Task.objects.filter(creation_time__date=today)
            all_tasks = Task.objects.all()
        else:
            # 普通员工：只查看分配给自己的任务
            today_tasks = Task.objects.filter(assignee=current_employee, creation_time__date=today)
            all_tasks = Task.objects.filter(assignee=current_employee)
        
        # 任务统计
        task_stats = {
            'today_total': today_tasks.count(),
            'completed': all_tasks.filter(status='COMPLETED').count(),
            'in_progress': all_tasks.filter(status='IN_PROGRESS').count(),
            'pending': all_tasks.filter(status='TO_DO').count(),
        }
        
        # 获取公司十大任务（数据库优先）
        company_top_task_ids = _load_company_top_task_ids(request)
        if company_top_task_ids:
            company_tasks_query = Task.objects.filter(task_id__in=company_top_task_ids)
            company_tasks_list = list(company_tasks_query)[:10]
            if not company_tasks_list:
                company_tasks_list = list(Task.objects.all())[:10]
        else:
            company_tasks_list = list(Task.objects.all().order_by('-creation_time')[:10])
        
        # 转换为JSON格式
        company_tasks_data = []
        for task in company_tasks_list:
            company_tasks_data.append({
                'task_id': task.task_id,
                'task_name': task.task_name,
                'description': task.description or '',
                'priority': task.priority,
                'status': task.status,
                'assignee_name': task.assignee.employee_name if task.assignee else '',
                'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
                'due_time': task.due_time.strftime('%Y-%m-%d %H:%M') if task.due_time else None,
            })
        
        # 个人十大重要事项（如果 session 中存在即使为空也尊重为空，不回退默认）
        personal_top_task_ids = _load_persisted_personal_task_ids(request, current_employee_id)
        if personal_top_task_ids is not None:
            if personal_top_task_ids:
                personal_tasks_query = Task.objects.filter(
                    task_id__in=personal_top_task_ids,
                    assignee=current_employee
                )
                task_dict = {task.task_id: task for task in personal_tasks_query}
                personal_tasks_list = [task_dict[tid] for tid in personal_top_task_ids if tid in task_dict][:10]
            else:
                personal_tasks_list = []
        else:
            priority_order = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            personal_tasks_list = list(Task.objects.filter(assignee=current_employee).order_by(
                '-priority',
                '-creation_time'
            )[:10])
        
        personal_tasks_data = []
        for task in personal_tasks_list:
            personal_tasks_data.append({
                'task_id': task.task_id,
                'task_name': task.task_name,
                'description': task.description or '',
                'priority': task.priority,
                'status': task.status,
                'assignee_name': task.assignee.employee_name if task.assignee else '',
                'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
                'due_time': task.due_time.strftime('%Y-%m-%d %H:%M') if task.due_time else None,
            })
        
        # 获取个人日志（只显示当天的日志）
        personal_logs_query = LogEntry.objects.filter(
            employee=current_employee,
            log_time__date=today
        ).order_by('-log_time')[:5]
        
        personal_logs_data = []
        for log in personal_logs_query:
            log_tags = LogTag.objects.filter(
                entrytaglink__log_entry=log
            ).values_list('tag_name', flat=True)
            
            personal_logs_data.append({
                'log_id': log.log_id,
                'employee_name': log.employee.employee_name,
                'log_time': log.log_time.strftime('%Y-%m-%d %H:%M'),
                'content': log.content,
                'log_type': log.get_log_type_display(),
                'log_type_raw': log.log_type,
                'emotion_tag': log.get_emotion_tag_display() if log.emotion_tag else None,
                'tags': list(log_tags),
            })
        
        # 获取当前时间和问候语
        current_hour = datetime.now().hour
        if current_hour < 12:
            greeting = '早上好'
        elif current_hour < 18:
            greeting = '下午好'
        else:
            greeting = '晚上好'
        
        # 获取星期几
        weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        weekday = weekdays[datetime.now().weekday()]
        
        # 获取系统公告
        announcements_query = Announcement.objects.filter(is_active=True).order_by('-is_pinned', '-created_at')[:5]
        announcements_data = []
        for ann in announcements_query:
            announcements_data.append({
                'id': ann.announcement_id,
                'title': ann.title,
                'content': ann.content,
                'is_pinned': ann.is_pinned,
                'priority': ann.priority,
                'priority_display': ann.get_priority_display(),
                'created_at': ann.created_at.strftime('%Y-%m-%d'),
            })

        return JsonResponse({
            'success': True,
            'data': {
                'user_name': current_employee_name,
                'current_work_id': current_work_id,
                'current_employee_name': current_employee_name,
                'current_employee_id': current_employee_id,
                'task_stats': task_stats,
                'company_tasks': company_tasks_data,
                'personal_tasks': personal_tasks_data,
                'personal_logs': personal_logs_data,
                'announcements': announcements_data,
                'greeting': greeting,
                'today': today.strftime('%Y年%m月%d日'),
                'weekday': weekday,
                'has_admin_role': has_admin_role,
                'has_admin_or_ceo_access': has_admin_or_ceo,
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def employees_api(request):
    """管理员/CEO获取员工列表 JSON API（支持 query、department_id）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        current_work_id = request.session.get('current_employee_work_id')
        current_employee = Employee.objects.get(work_id=current_work_id)
        
        # 权限检查：只要有任意一项“查看全部”的权限，就允许获取员工列表用于筛选
        has_access = False
        if has_admin_or_ceo_access(current_employee):
            has_access = True
        elif check_boss_role(current_employee):
            has_access = True
        elif check_task_permission(current_employee):
            has_access = True
        else:
            # Check log permission manually as no helper is imported? 
            # Actually logs_api does: try: if current_employee.permissions.can_view_all_logs ...
            try:
                if hasattr(current_employee, 'permissions') and current_employee.permissions.can_view_all_logs:
                    has_access = True
            except Exception:
                pass
        
        if not has_access:
            return JsonResponse({'success': False, 'message': '无权访问'})

        query = (request.GET.get('query') or '').strip()
        department_id = request.GET.get('department_id')

        employees = Employee.objects.all()
        if query:
            employees = employees.filter(Q(employee_name__icontains=query) | Q(work_id__icontains=query))
        if department_id:
            try:
                employees = employees.filter(department_id=int(department_id))
            except ValueError:
                pass

        employees = employees.order_by('work_id')[:200]

        data = []
        for emp in employees:
            data.append({
                'employee_id': emp.employee_id,
                'employee_name': emp.employee_name,
                'work_id': emp.work_id,
                'department_id': emp.department_id,
                'position': emp.position or '',
                'status': emp.status,
            })

        return JsonResponse({'success': True, 'employees': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_http_methods(["POST"])
def announcement_ops_api(request):
    """公告管理操作 (创建)"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})

    current_work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.get(work_id=current_work_id)
    
    # 权限检查：仅管理员或CEO可发布
    if not has_admin_or_ceo_access(current_employee):
        return JsonResponse({'success': False, 'message': '无权操作'})

    try:
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'create':
            title = data.get('title')
            content = data.get('content')
            is_pinned = data.get('is_pinned', False)
            priority = data.get('priority', 'NORMAL')
            push_to_im = data.get('push_to_im', False)

            if not title or not content:
                return JsonResponse({'success': False, 'message': '标题和内容不能为空'})

            announcement = Announcement.objects.create(
                title=title,
                content=content,
                is_pinned=is_pinned,
                priority=priority,
                created_by=current_employee
            )

            if push_to_im:
                # 触发推送
                send_announcement(title, content)

            return JsonResponse({'success': True, 'message': '公告发布成功'})

        elif action == 'delete':
            announcement_id = data.get('announcement_id')
            if not announcement_id:
                return JsonResponse({'success': False, 'message': '缺少公告ID'})
            
            try:
                announcement = Announcement.objects.get(announcement_id=announcement_id)
                announcement.delete()
                return JsonResponse({'success': True, 'message': '公告已删除'})
            except Announcement.DoesNotExist:
                return JsonResponse({'success': False, 'message': '公告不存在'})

        return JsonResponse({'success': False, 'message': '无效的操作'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
