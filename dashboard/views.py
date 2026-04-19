# dashboard/views.py
from datetime import timedelta
import datetime
import calendar
from django.db.models import Q, Count
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from pandora.models import Employee, Role, EmployeeRole, Task, LogEntry, LogTag, EntryTagLink, PersonalTopTaskConfig, EmployeePermission, Announcement
from pandora.models import CompanyTopTaskConfig
from pandora.utils import check_admin_role, check_ceo_role, check_boss_role, has_admin_or_ceo_access, check_task_permission, check_log_permission
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password


def _load_persisted_personal_task_ids(request, employee_id):
    """
    以数据库为准加载个人十大任务配置；若数据库暂无记录，才退回 session。
    """
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


def _build_media_url(request, relative_path):
    if relative_path:
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")
    return ''


def _persist_personal_task_ids(employee_id, task_ids, request=None):
    config, _ = PersonalTopTaskConfig.objects.update_or_create(
        employee_id=employee_id,
        defaults={'task_ids': task_ids},
    )
    if request is not None:
        session_key = f'personal_top_tasks_{employee_id}'
        session_version_key = f'personal_top_tasks_version_{employee_id}'
        request.session[session_key] = config.task_ids or []
        request.session[session_version_key] = config.updated_at.isoformat()

def _load_company_top_task_ids(request=None):
    conf = CompanyTopTaskConfig.objects.order_by('-updated_at').first()
    if conf:
        return conf.task_ids or []
    if request is not None:
        return request.session.get('company_top_tasks', [])
    return []

def _persist_company_top_task_ids(task_ids, request=None):
    conf, _ = CompanyTopTaskConfig.objects.get_or_create(id=1, defaults={'task_ids': task_ids})
    if not _:
        conf.task_ids = task_ids
        conf.save(update_fields=['task_ids'])
    if request is not None:
        request.session['company_top_tasks'] = task_ids


def dashboard_home(request):
    # 如果没有登录，跳转到登录页
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')

    current_work_id = request.session.get('current_employee_work_id')
    current_employee_name = request.session.get('current_employee_name')
    current_employee_id = request.session.get('current_employee_id')

    # 获取当前员工对象
    current_employee = Employee.objects.get(work_id=current_work_id)

    # 检查是否有管理员角色
    has_admin_role = check_admin_role(current_employee)
    has_admin_or_ceo = has_admin_or_ceo_access(current_employee)
    can_view_all_tasks = check_task_permission(current_employee)
    can_view_all_logs = check_log_permission(current_employee)

    # 获取今日日期
    today = timezone.now().date()

    # 任务统计（今日任务）
    if can_view_all_tasks:
        # 拥有任务查看权限（管理员/CEO/授权员工）：查看所有任务
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

    # 获取公司十大任务（所有员工都显示，但非管理员只能查看）
    company_task_ids = _load_company_top_task_ids(request)
    company_tasks = []
    if company_task_ids:
        fetched_tasks = {t.task_id: t for t in Task.objects.filter(task_id__in=company_task_ids)}
        for tid in company_task_ids:
             if tid in fetched_tasks:
                 company_tasks.append(fetched_tasks[tid])

    # 获取个人十大任务
    personal_task_ids = _load_persisted_personal_task_ids(request, current_employee.employee_id)
    personal_tasks = []
    if personal_task_ids:
        fetched_tasks = {t.task_id: t for t in Task.objects.filter(task_id__in=personal_task_ids)}
        for tid in personal_task_ids:
             if tid in fetched_tasks:
                 personal_tasks.append(fetched_tasks[tid])

    # 获取分配给我的任务（未完成）
    assigned_tasks = Task.objects.filter(assignee=current_employee, status__in=['TO_DO', 'IN_PROGRESS']).order_by('-priority', 'due_time')[:5]

    # 获取个人日志（只显示当天的日志，可以编辑）
    personal_logs = LogEntry.objects.filter(
        employee=current_employee,
        log_time__date=today
    ).order_by('-log_time')[:5]

    # 定义导航链接
    nav_items = [
        {'name': '任务', 'url': '/tasks/', 'icon': 'fa-tasks'},
        {'name': '日志', 'url': '/logs/', 'icon': 'fa-book'},
        {'name': '视图', 'url': '#', 'icon': 'fa-chart-bar'},  # 待实现
        {'name': 'AI分析', 'url': '/ai/', 'icon': 'fa-brain'},
        {'name': '我的', 'url': '/employee/', 'icon': 'fa-user'},
    ]
    if has_admin_role:
        nav_items.append({'name': '员工管理', 'url': '/employee_list/', 'icon': 'fa-users'})

    # 问候语和日期
    hour = datetime.datetime.now().hour
    if hour < 12:
        greeting = '早上好'
    elif hour < 18:
        greeting = '下午好'
    else:
        greeting = '晚上好'
    
    weekday_map = {0: '周一', 1: '周二', 2: '周三', 3: '周四', 4: '周五', 5: '周六', 6: '周日'}
    weekday = weekday_map[today.weekday()]
    yesterday = (today - timedelta(days=1)).strftime('%Y年%m月%d日')

    # 获取系统公告
    announcements = Announcement.objects.filter(is_active=True).order_by('-is_pinned', '-created_at')[:5]

    context = {
        'user_name': current_employee_name or (request.user.username if request.user.is_authenticated else 'Guest'),
        'current_work_id': current_work_id,
        'current_employee_name': current_employee_name,
        'current_employee_id': current_employee_id,
        'has_admin_role': has_admin_role,
        'has_admin_or_ceo_access': has_admin_or_ceo,
        'can_view_all_tasks': can_view_all_tasks,
        'can_view_all_logs': can_view_all_logs,
        'task_stats': task_stats,
        'company_tasks': company_tasks,
        'personal_tasks': personal_tasks,
        'assigned_tasks': assigned_tasks,
        'personal_logs': personal_logs,
        'announcements': announcements,
        'nav_items': nav_items,
        'greeting': greeting,
        'today': today.strftime('%Y年%m月%d日'),
        'weekday': weekday,
        'yesterday': yesterday,
    }
    return render(request, 'dashboard_home.html', context)


def mobile_dashboard_page(request):
    # 未登录跳转
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')
    # 前端通过 /dashboard/api/ 获取摘要数据
    return render(request, 'mobile_dashboard_page.html', {})


def mobile_workbench_page(request):
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')
    return render(request, 'mobile_workbench_page.html', {})


def mobile_me_page(request):
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')
    work_id = request.session.get('current_employee_work_id')
    emp = Employee.objects.filter(work_id=work_id).first()
    department_name = '未分配'
    join_date = ''
    if emp and emp.department_id:
        try:
            from pandora.models import Department
            dept = Department.objects.get(department_id=emp.department_id)
            department_name = dept.department_name
        except Department.DoesNotExist:
            pass
    if emp and emp.join_date:
        join_date = emp.join_date
    return render(request, 'mobile_me_page.html', {
        'work_id': work_id,
        'employee_name': request.session.get('current_employee_name'),
        'email': emp.email if emp else '',
        'phone_number': emp.phone_number if emp else '',
        'department_name': department_name,
        'join_date': join_date,
        'position': emp.position if emp else '',
    })


def mobile_employees_page(request):
    # 仅管理员/CEO可访问
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')
    current_work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.filter(work_id=current_work_id).first()
    if not current_employee or not has_admin_or_ceo_access(current_employee):
        return redirect('/m/')
    return render(request, 'mobile_employees_page.html', {})

def mobile_views_page(request):
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')
    return render(request, 'mobile_views_page.html', {})


def employee_detail(request):
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return redirect('/login_app/login_page/')  # 未登录跳转

    employee = get_object_or_404(Employee, work_id=work_id)
    
    # 获取部门名称
    department_name = '未分配'
    if employee.department_id:
        try:
            from pandora.models import Department
            dept = Department.objects.get(department_id=employee.department_id)
            department_name = dept.department_name
        except Department.DoesNotExist:
            pass

    context = {
        'employee': employee,
        'department_name': department_name,
        'current_work_id': employee.work_id,
        'current_employee_name': employee.employee_name,
    }
    return render(request, 'employee_detail.html', context)

def employee_subordinates(request):
    work_id = request.GET.get('work_id')
    mode = request.GET.get('mode', 'subordinates') # 'subordinates' (默认) 或 'assignees' (任务分配)

    if not work_id:
        return JsonResponse({'success': False, 'message': '缺少 work_id 参数'})

    # 检查权限
    current_employee_id = request.session.get('current_employee_id')
    can_view_all = False
    if current_employee_id:
        try:
            current_emp = Employee.objects.get(pk=current_employee_id)
            can_view_all = check_task_permission(current_emp)
        except Exception:
            pass

    try:
        # 如果是请求分配任务的候选人列表，且有权限查看所有任务，则返回所有员工
        if mode == 'assignees' and can_view_all:
            subordinates = Employee.objects.filter(status='ACTIVE').values(
                'employee_id', 'employee_name', 'work_id', 'position', 'status'
            ).order_by('employee_name')
        else:
            # 否则只返回指定员工的下属
            subordinates = Employee.objects.filter(manager__work_id=work_id).values(
                'employee_id', 'employee_name', 'work_id', 'position', 'status'
            )
        return JsonResponse({'success': True, 'subordinates': list(subordinates)})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_GET
def get_manager_role(request):
    """获取指定员工作为上级时的角色信息"""
    work_id = request.GET.get('work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '缺少工号参数'})
    
    try:
        manager = Employee.objects.get(work_id=work_id)
        
        # 获取该员工的所有角色
        # 确保使用整数进行查询
        employee_id = int(manager.employee_id)
        # 使用values_list避免访问id字段
        role_ids = list(EmployeeRole.objects.filter(employee_id=employee_id).values_list('role_id', flat=True))
        
        # 调试信息（可以后续删除）
        print(f"DEBUG: 员工 {work_id} (ID: {employee_id}) 的角色ID列表: {role_ids}")
        
        # 查找最高级别的角色（按照优先级：1(ceo) > 3(部门主管) > 4(团队长) > 5(员工)）
        # 如果有多角色，取优先级最高的
        manager_role_id = None
        if 1 in role_ids:  # ceo
            manager_role_id = 1
            new_employee_role_id = 3  # 部门主管
        elif 3 in role_ids:  # 部门主管
            manager_role_id = 3
            new_employee_role_id = 4  # 团队长
        elif 4 in role_ids:  # 团队长
            manager_role_id = 4
            new_employee_role_id = 5  # 员工
        elif 5 in role_ids:  # 员工
            manager_role_id = 5
            new_employee_role_id = None  # 员工不能成为上级
        else:
            # 如果没有找到标准角色，返回空
            return JsonResponse({
                'success': True,
                'manager_role_id': None,
                'new_employee_role_id': None,
                'role_name': '未分配角色'
            })
        
        # 获取角色名称
        try:
            role = Role.objects.get(role_id=manager_role_id)
            role_name = role.role_name
        except Role.DoesNotExist:
            role_name = '未知角色'
        
        return JsonResponse({
            'success': True,
            'manager_role_id': manager_role_id,
            'new_employee_role_id': new_employee_role_id,
            'role_name': role_name,
            'can_be_manager': manager_role_id != 5  # 角色5不能成为上级
        })
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_GET
def get_department_employees(request):
    """根据部门ID获取该部门的员工列表（用于上级选择）"""
    department_id = request.GET.get('department_id', '')
    exclude_work_id = request.GET.get('exclude_work_id', '')  # 编辑时排除当前员工
    
    try:
        # 获取在职和请假的员工（都可以被选为上级）
        employees = Employee.objects.filter(status__in=['ACTIVE', 'LEAVE']).order_by('employee_name')
        
        # 排除指定员工（编辑时排除自己）
        if exclude_work_id:
            employees = employees.exclude(work_id=exclude_work_id)
        
        # 如果指定了部门ID，筛选该部门的员工
        if department_id:
            try:
                department_id_int = int(department_id)
                employees = employees.filter(department_id=department_id_int)
            except ValueError:
                pass
        
        # 过滤掉角色为5（员工）的员工，因为员工不能成为上级
        # 获取所有员工的角色信息（一次性查询，避免循环中查询数据库）
        employee_ids = list(employees.values_list('employee_id', flat=True))
        
        # 调试信息（可以后续删除）
        print(f"DEBUG: get_department_employees - 部门ID: {department_id}, 初始员工数量: {len(employee_ids)}")
        
        # 如果有员工，需要根据角色过滤
        if employee_ids:
            # 确保employee_id都是整数类型
            employee_ids = [int(eid) for eid in employee_ids if eid is not None]
            
            # 获取所有员工的角色（如果没有员工，这里会返回空查询集）
            # 使用values()方法明确指定字段，避免Django尝试访问不存在的id字段
            all_employee_roles = EmployeeRole.objects.filter(employee_id__in=employee_ids).values('employee_id', 'role_id')
            
            # 构建员工ID到角色列表的映射
            employee_roles_map = {}
            for er in all_employee_roles:
                emp_id = int(er['employee_id'])  # 确保是整数
                role_id = int(er['role_id'])  # 确保是整数
                if emp_id not in employee_roles_map:
                    employee_roles_map[emp_id] = []
                employee_roles_map[emp_id].append(role_id)
            
            # 调试信息（可以后续删除）
            print(f"DEBUG: get_department_employees - 员工ID列表: {employee_ids}")
            print(f"DEBUG: get_department_employees - 角色映射: {employee_roles_map}")
            
            # 过滤出有效的员工（只排除明确只有角色5的员工）
            # 允许没有角色的员工被选择（可能是系统配置问题，可以后续手动分配角色）
            valid_employee_ids = []
            for emp_id in employee_ids:
                emp_roles = employee_roles_map.get(emp_id, [])  # 没有角色的员工emp_roles会是[]
                # 只排除明确只有角色5的员工（角色5不能成为上级）
                # 如果员工没有角色，或者有其他角色（即使也有角色5），都允许被选择
                if len(emp_roles) == 1 and 5 in emp_roles:
                    # 只有角色5的员工不能成为上级
                    print(f"DEBUG: 排除员工ID {emp_id}，因为只有角色5")
                    continue
                # 其他情况都允许：
                # - 没有角色的员工（允许被选择，虽然会提示需要分配角色）
                # - 有多个角色的员工（即使包含角色5，只要不只有角色5就可以）
                # - 有其他角色（1,3,4）的员工
                valid_employee_ids.append(emp_id)
            
            # 调试信息
            print(f"DEBUG: get_department_employees - 有效员工ID列表: {valid_employee_ids}, 数量: {len(valid_employee_ids)}")
            
            # 过滤出有效的员工
            if valid_employee_ids:
                employees = employees.filter(employee_id__in=valid_employee_ids)
            else:
                # 如果没有有效员工，返回空结果
                employees = Employee.objects.none()
                print(f"DEBUG: 警告 - 所有员工都被过滤掉了！")
        else:
            # 如果没有员工，直接返回空结果
            print(f"DEBUG: get_department_employees - 该部门没有员工")
            employees = Employee.objects.none()
        
        # 返回员工数据
        employees_data = list(employees.values(
            'employee_id', 'employee_name', 'work_id', 'department_id', 'position'
        ))
        
        # 调试信息（可以后续删除）
        print(f"DEBUG: get_department_employees - 最终返回的员工数量: {len(employees_data)}")
        
        return JsonResponse({
            'success': True,
            'employees': employees_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_GET
def get_employee_logs(request):
    """获取指定员工的日志列表"""
    employee_id = request.GET.get('employee_id')
    date_str = request.GET.get('date', '')
    
    if not employee_id:
        return JsonResponse({'success': False, 'message': '缺少 employee_id 参数'})
    
    try:
        employee = get_object_or_404(Employee, pk=employee_id)
        
        # 获取当前用户，检查权限
        current_employee_id = request.session.get('current_employee_id')
        if not current_employee_id:
            return JsonResponse({'success': False, 'message': '未登录'})
        
        current_employee = get_object_or_404(Employee, pk=current_employee_id)
        has_log_access = check_log_permission(current_employee)
        
        # 检查权限：管理员/CEO/拥有日志查看权限者可以查看所有员工日志，普通用户只能查看自己的或下属的日志
        if not has_log_access:
            # 普通用户：只能查看自己的或直接下属的日志
            try:
                employee_id_int = int(employee_id)
                current_employee_id_int = int(current_employee_id)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': '无效的员工ID'})
            
            if employee_id_int != current_employee_id_int and not Employee.objects.filter(
                employee_id=employee_id_int, 
                manager_id=current_employee_id_int
            ).exists():
                return JsonResponse({'success': False, 'message': '无权查看该员工的日志'})
        
        # 日期筛选
        if date_str:
            try:
                from django.utils.dateparse import parse_date
                selected_date = parse_date(date_str)
            except (ValueError, TypeError):
                selected_date = timezone.now().date()
        else:
            selected_date = timezone.now().date()
        
        # 获取该员工的日志
        try:
            employee_id_int = int(employee_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': '无效的员工ID'})
        
        logs = LogEntry.objects.filter(
            employee_id=employee_id_int,
            log_time__date=selected_date
        ).select_related('employee').order_by('-log_time')
        
        # 获取每个日志的标签
        logs_data = []
        for log in logs:
            log_tags = LogTag.objects.filter(
                entrytaglink__log_entry=log
            ).values_list('tag_name', flat=True)
            
            logs_data.append({
                'log_id': log.log_id,
                'employee_name': log.employee.employee_name,
                'log_time': log.log_time.strftime('%Y-%m-%d %H:%M'),
                'content': log.content,
                'log_type': log.get_log_type_display(),
                'log_type_raw': log.log_type,
                'emotion_tag': log.get_emotion_tag_display() if log.emotion_tag else None,
                'emotion_tag_raw': log.emotion_tag,
                'tags': list(log_tags),
                'image_url': _build_media_url(request, log.image_url),
                'location_name': log.location_name or '',
                'location_lat': float(log.location_lat) if log.location_lat is not None else None,
                'location_lng': float(log.location_lng) if log.location_lng is not None else None,
            })
        
        return JsonResponse({
            'success': True,
            'employee_name': employee.employee_name,
            'logs': logs_data,
            'date': selected_date.strftime('%Y-%m-%d'),
            'total_count': len(logs_data)
        })
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_POST
def employee_add(request):
    try:
        data = request.POST

        # 处理上级员工ID - 如果提供了manager_id，需要根据work_id查找对应的Employee对象
        manager = None
        manager_work_id = data.get('manager_id')
        if manager_work_id:
            try:
                manager = Employee.objects.get(work_id=manager_work_id)
            except Employee.DoesNotExist:
                return JsonResponse({'success': False, 'message': f'上级员工工号 {manager_work_id} 不存在'})

        # 处理部门ID - 确保为空时设置为None
        department_id = data.get('department_id')
        if department_id:
            try:
                department_id = int(department_id)
            except ValueError:
                return JsonResponse({'success': False, 'message': '部门ID必须是数字'})
        else:
            department_id = None

        # 处理入职日期
        join_date = data.get('join_date')
        if not join_date:
            join_date = None

        # 创建员工对象 - 不要设置employee_id，让它自动生成
        emp = Employee.objects.create(
            work_id=data.get('work_id'),
            employee_name=data.get('employee_name'),
            email=data.get('email') or '',
            phone_number=data.get('phone_number') or None,
            department_id=department_id,
            position=data.get('position') or None,
            join_date=join_date,
            status=data.get('status', 'ACTIVE'),
            manager=manager,  # 使用manager对象而不是manager_id
            password=make_password('123456'),  # 默认密码 (哈希)
        )
        
        # 处理权限设置
        can_view_all_tasks = (data.get('can_view_all_tasks') in ('1', 'true', 'True', 'on'))
        can_view_all_logs = (data.get('can_view_all_logs') in ('1', 'true', 'True', 'on'))
        is_admin_flag = (data.get('is_admin') in ('1', 'true', 'True', 'on'))

        # 如果勾选了管理员，自动赋予所有权限
        if is_admin_flag:
            can_view_all_tasks = True
            can_view_all_logs = True
            
        # 创建权限记录
        try:
            EmployeePermission.objects.create(
                employee=emp,
                can_view_all_tasks=can_view_all_tasks,
                can_view_all_logs=can_view_all_logs
            )
        except Exception as e:
            print(f"创建员工权限记录失败: {e}")

        # 选择管理员：为新员工分配管理员角色
        try:
            if is_admin_flag:
                admin_role = Role.objects.get(role_name='管理员')
                exists = EmployeeRole.objects.filter(employee_id=emp.employee_id, role_id=admin_role.role_id).exists()
                if not exists:
                    EmployeeRole.objects.create(employee_id=emp.employee_id, role_id=admin_role.role_id)
        except Role.DoesNotExist:
            pass
        
        # 根据上级角色自动分配新员工的角色
        # 如果选择了上级，根据上级的最高角色来分配新员工的角色
        if manager:
            # 获取上级的所有角色，确保使用整数
            manager_id = int(manager.employee_id)
            # 使用values_list避免访问id字段
            manager_role_ids = [int(rid) for rid in EmployeeRole.objects.filter(employee_id=manager_id).values_list('role_id', flat=True)]
            
            # 调试信息（可以后续删除）
            print(f"DEBUG: employee_add - 上级 {manager.work_id} (ID: {manager_id}) 的角色ID列表: {manager_role_ids}")
            
            # 根据上级的角色确定新员工的角色
            new_employee_role_id = None
            if len(manager_role_ids) == 0:
                # 上级没有角色，不自动分配角色，需要后续手动分配
                pass
            elif 1 in manager_role_ids:  # 上级是ceo
                new_employee_role_id = 3  # 新员工是部门主管
            elif 3 in manager_role_ids:  # 上级是部门主管
                new_employee_role_id = 4  # 新员工是团队长
            elif 4 in manager_role_ids:  # 上级是团队长
                new_employee_role_id = 5  # 新员工是员工
            elif 5 in manager_role_ids and len(manager_role_ids) == 1:
                # 上级只有角色5（员工），不应该出现在列表中，但为了安全不分配角色
                pass
            
            # 如果确定了新员工的角色，创建EmployeeRole记录
            if new_employee_role_id:
                try:
                    EmployeeRole.objects.create(
                        employee_id=emp.employee_id,
                        role_id=new_employee_role_id
                    )
                except Exception as e:
                    # 如果创建角色失败，记录错误但不影响员工创建
                    print(f"创建员工角色失败: {e}")
        
        return JsonResponse({'success': True, 'message': '员工添加成功'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_POST
def employee_delete(request):
    work_id = request.POST.get('work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '缺少工号'})
    try:
        emp = Employee.objects.get(work_id=work_id)
        emp.delete()
        return JsonResponse({'success': True})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@require_GET
def employee_list(request):
    """
    返回员工列表页面，并可通过 query 参数搜索员工姓名或工号
    """
    try:
        query = request.GET.get('query', '').strip()
        employees = Employee.objects.all()

        if query:
            employees = employees.filter(Q(employee_name__icontains=query) | Q(work_id__icontains=query))

        # 获取所有部门列表
        from pandora.models import Department
        departments = Department.objects.all().order_by('department_name')
        
        # 创建部门ID到部门名称的映射字典
        department_dict = {dept.department_id: dept.department_name for dept in departments}
        
        # 为每个员工添加部门名称（在模板中可以使用）
        employees_with_dept = []
        for emp in employees:
            emp_dict = {
                'employee': emp,
                'department_name': department_dict.get(emp.department_id, '未分配') if emp.department_id else '未分配'
            }
            employees_with_dept.append(emp_dict)
        
        # 获取所有boss（CEO+管理员）
        boss_employees = []
        try:
            admin_role = Role.objects.get(role_name='管理员')
            ceo_role = Role.objects.get(role_name='CEO')
            
            # 获取既是管理员又是CEO的员工
            admin_employees = EmployeeRole.objects.filter(role_id=admin_role.role_id).values_list('employee_id', flat=True)
            ceo_employees = EmployeeRole.objects.filter(role_id=ceo_role.role_id).values_list('employee_id', flat=True)
            
            boss_ids = set(admin_employees) & set(ceo_employees)
            boss_employees = Employee.objects.filter(employee_id__in=boss_ids, status__in=['ACTIVE', 'LEAVE']).values(
                'employee_id', 'employee_name', 'work_id', 'department_id'
            )
        except Role.DoesNotExist:
            pass

        context = {
            'employees_with_dept': employees_with_dept,  # 包含部门名称的员工列表
            'employees': employees,  # 保留原列表用于兼容
            'query': query,
            'departments': departments,
            'boss_employees': list(boss_employees),
            'department_dict': department_dict,  # 部门字典，用于快速查找
        }
        # 渲染 HTML 页面
        return render(request, 'employee_list.html', context)

    except Exception as e:
        # 渲染错误页面或显示错误信息
        return render(request, 'employee_list.html', {'error': str(e)})


@require_GET
def employee_get(request):
    """
    获取员工详情（用于编辑表单）
    """
    work_id = request.GET.get('work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '缺少工号参数'})
    
    try:
        employee = Employee.objects.get(work_id=work_id)
        
        # 获取权限信息
        can_view_all_tasks = False
        can_view_all_logs = False
        try:
            perm = employee.permissions
            can_view_all_tasks = perm.can_view_all_tasks
            can_view_all_logs = perm.can_view_all_logs
        except Exception:
            pass
            
        data = {
            'success': True,
            'employee': {
                'work_id': employee.work_id,
                'employee_name': employee.employee_name,
                'email': employee.email or '',
                'phone_number': employee.phone_number or '',
                'department_id': employee.department_id or '',
                'position': employee.position or '',
                'join_date': employee.join_date.strftime('%Y-%m-%d') if employee.join_date else '',
                'status': employee.status,
                'manager_id': employee.manager.work_id if employee.manager else '',
                'is_admin': check_admin_role(employee),
                'can_view_all_tasks': can_view_all_tasks,
                'can_view_all_logs': can_view_all_logs,
            }
        }
        return JsonResponse(data)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def get_all_tasks(request):
    """获取所有任务列表（用于管理员选择公司十大任务）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    current_work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.get(work_id=current_work_id)
    
    # 检查是否有管理员权限或任务查看权限
    if not check_task_permission(current_employee):
        return JsonResponse({'success': False, 'message': '无权访问'})
    
    # 获取所有任务（有执行人的）
    tasks = Task.objects.filter(assignee__isnull=False).order_by('-creation_time')[:100]  # 限制100条
    
    tasks_data = []
    for task in tasks:
        tasks_data.append({
            'task_id': task.task_id,
            'task_name': task.task_name,
            'description': task.description or '',
            'priority': task.priority,
            'status': task.status,
            'assignee_name': task.assignee.employee_name if task.assignee else '',
            'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({'success': True, 'tasks': tasks_data})


@require_GET
def get_personal_tasks(request):
    """获取个人任务列表（用于选择个人十大重要事项）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    current_work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.get(work_id=current_work_id)
    
    # 获取该员工的所有任务（有执行人的）
    tasks = Task.objects.filter(assignee=current_employee).order_by('-creation_time')[:100]  # 限制100条
    
    tasks_data = []
    for task in tasks:
        tasks_data.append({
            'task_id': task.task_id,
            'task_name': task.task_name,
            'description': task.description or '',
            'priority': task.priority,
            'status': task.status,
            'assignee_name': task.assignee.employee_name if task.assignee else '',
            'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
        })
    
    return JsonResponse({'success': True, 'tasks': tasks_data})


@csrf_exempt
@require_POST
def update_company_top_tasks(request):
    """更新公司十大任务配置（管理员功能）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    current_work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.get(work_id=current_work_id)
    
    # 检查是否有管理员权限或任务查看权限
    if not check_task_permission(current_employee):
        return JsonResponse({'success': False, 'message': '无权访问'})
    
    import json
    try:
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])
        
        # 验证任务ID
        if len(task_ids) > 10:
            return JsonResponse({'success': False, 'message': '最多只能选择10个任务'})
        
        # 验证任务是否存在
        tasks = Task.objects.filter(task_id__in=task_ids, assignee__isnull=False)
        if tasks.count() != len(task_ids):
            return JsonResponse({'success': False, 'message': '部分任务不存在'})
        
        _persist_company_top_task_ids(task_ids, request)
        return JsonResponse({'success': True, 'message': '公司十大任务更新成功'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def update_personal_top_tasks(request):
    """更新个人十大重要事项配置（每个员工独立）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    current_work_id = request.session.get('current_employee_work_id')
    current_employee_id = request.session.get('current_employee_id')
    current_employee = Employee.objects.get(work_id=current_work_id)
    
    import json
    try:
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])
        try:
            task_ids = [int(tid) for tid in task_ids]
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': '任务ID格式不正确'})
        
        # 验证任务ID
        if len(task_ids) > 10:
            return JsonResponse({'success': False, 'message': '最多只能选择10个任务'})
        
        # 验证任务是否存在且属于当前员工
        tasks = Task.objects.filter(task_id__in=task_ids, assignee=current_employee)
        if tasks.count() != len(task_ids):
            return JsonResponse({'success': False, 'message': '部分任务不存在或不属于您'})
        
        # 存储配置（数据库 + session），按员工ID区分
        _persist_personal_task_ids(current_employee_id, task_ids, request)
        
        return JsonResponse({'success': True, 'message': '个人十大重要事项更新成功'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def get_employee_detail(request):
    """
    获取员工完整详细信息（用于详情展示模态框）
    包括：基本信息、部门名称、上级信息、角色信息
    """
    work_id = request.GET.get('work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '缺少工号参数'})
    
    try:
        employee = Employee.objects.get(work_id=work_id)
        
        # 获取部门名称
        department_name = '未分配'
        if employee.department_id:
            try:
                from pandora.models import Department
                dept = Department.objects.get(department_id=employee.department_id)
                department_name = dept.department_name
            except Department.DoesNotExist:
                pass
        
        # 获取上级信息
        manager_name = '无'
        manager_work_id = None
        if employee.manager:
            manager_name = employee.manager.employee_name
            manager_work_id = employee.manager.work_id
        
        # 获取角色信息
        roles = []
        try:
            # 确保使用整数进行查询
            employee_id_int = int(employee.employee_id)
            # 使用values()避免访问id字段
            employee_roles = EmployeeRole.objects.filter(employee_id=employee_id_int).values('role_id')
            for er in employee_roles:
                try:
                    role_id_int = int(er['role_id'])
                    role = Role.objects.get(role_id=role_id_int)
                    roles.append(role.role_name)
                except Role.DoesNotExist:
                    pass
        except Exception as e:
            # 调试信息（可以后续删除）
            print(f"DEBUG: get_employee_detail - 获取角色失败: {e}")
            pass
        
        # 是否为管理员角色
        try:
            admin_role = Role.objects.get(role_name='管理员')
            is_admin = EmployeeRole.objects.filter(employee_id=employee.employee_id, role_id=admin_role.role_id).exists()
        except Role.DoesNotExist:
            is_admin = False

        # 获取权限信息
        can_view_all_tasks = False
        can_view_all_logs = False
        try:
            perm = employee.permissions
            can_view_all_tasks = perm.can_view_all_tasks
            can_view_all_logs = perm.can_view_all_logs
        except Exception:
            pass

        data = {
            'success': True,
            'employee': {
                'work_id': employee.work_id,
                'employee_name': employee.employee_name,
                'email': employee.email or '未填写',
                'phone_number': employee.phone_number or '未填写',
                'department_id': employee.department_id,
                'department_name': department_name,
                'position': employee.position or '未填写',
                'join_date': employee.join_date.strftime('%Y-%m-%d') if employee.join_date else '未填写',
                'status': employee.status,
                'status_display': '在职' if employee.status == 'ACTIVE' else ('请假' if employee.status == 'LEAVE' else '禁用'),
                'manager_name': manager_name,
                'manager_work_id': manager_work_id,
                'roles': roles,
                'is_admin': is_admin,
                'can_view_all_tasks': can_view_all_tasks,
                'can_view_all_logs': can_view_all_logs,
            }
        }
        return JsonResponse(data)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_POST
def employee_update(request):
    """
    更新员工信息
    """
    try:
        work_id = request.POST.get('work_id')
        if not work_id:
            return JsonResponse({'success': False, 'message': '缺少工号'})
        
        employee = Employee.objects.get(work_id=work_id)
        data = request.POST

        # 处理上级员工ID
        manager = None
        manager_work_id = data.get('manager_id')
        if manager_work_id:
            try:
                # 不能将自己设为上级
                if manager_work_id == work_id:
                    return JsonResponse({'success': False, 'message': '不能将自己设为上级'})
                manager = Employee.objects.get(work_id=manager_work_id)
            except Employee.DoesNotExist:
                return JsonResponse({'success': False, 'message': f'上级员工工号 {manager_work_id} 不存在'})
        
        # 处理部门ID
        department_id = data.get('department_id')
        if department_id:
            try:
                department_id = int(department_id)
            except ValueError:
                return JsonResponse({'success': False, 'message': '部门ID必须是数字'})
        else:
            department_id = None

        # 处理入职日期
        join_date = data.get('join_date')
        if not join_date:
            join_date = None

        # 更新员工信息
        employee.employee_name = data.get('employee_name')
        employee.email = data.get('email') or ''
        employee.phone_number = data.get('phone_number') or None
        employee.department_id = department_id
        employee.position = data.get('position') or None
        employee.join_date = join_date
        employee.status = data.get('status', 'ACTIVE')
        employee.manager = manager
        employee.save()

        # 处理权限设置
        can_view_all_tasks = (data.get('can_view_all_tasks') in ('1', 'true', 'True', 'on'))
        can_view_all_logs = (data.get('can_view_all_logs') in ('1', 'true', 'True', 'on'))
        is_admin_flag = (data.get('is_admin') in ('1', 'true', 'True', 'on'))

        if is_admin_flag:
            can_view_all_tasks = True
            can_view_all_logs = True
        
        # 更新或创建权限记录
        try:
            perm, created = EmployeePermission.objects.get_or_create(employee=employee)
            perm.can_view_all_tasks = can_view_all_tasks
            perm.can_view_all_logs = can_view_all_logs
            perm.save()
        except Exception as e:
            print(f"更新员工权限记录失败: {e}")

        # 管理员角色开关
        try:
            admin_role = Role.objects.get(role_name='管理员')
            has_admin = EmployeeRole.objects.filter(employee_id=employee.employee_id, role_id=admin_role.role_id).exists()
            
            if is_admin_flag and not has_admin:
                EmployeeRole.objects.create(employee_id=employee.employee_id, role_id=admin_role.role_id)
            elif (not is_admin_flag) and has_admin:
                EmployeeRole.objects.filter(employee_id=employee.employee_id, role_id=admin_role.role_id).delete()
        except Role.DoesNotExist:
            pass

        return JsonResponse({'success': True, 'message': '员工信息更新成功'})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def employee_profile_update(request):
    """当前用户编辑个人资料（仅邮箱、电话）"""
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        employee = Employee.objects.get(work_id=work_id)
        employee.email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone_number', '').strip()
        employee.phone_number = phone or None
        employee.save()
        return JsonResponse({'success': True, 'message': '资料已更新'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def employee_change_password(request):
    """当前用户修改密码（明文校验）"""
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    old_password = request.POST.get('old_password', '')
    new_password = request.POST.get('new_password', '')
    if not old_password or not new_password:
        return JsonResponse({'success': False, 'message': '缺少参数'})
    try:
        employee = Employee.objects.get(work_id=work_id)
        
        # 验证旧密码 (支持哈希和明文)
        if not check_password(old_password, employee.password):
            # 如果不是有效哈希，尝试明文匹配 (兼容旧数据)
            if employee.password != old_password:
                return JsonResponse({'success': False, 'message': '原密码不正确'})
        
        # 设置新密码 (哈希)
        employee.password = make_password(new_password)
        employee.save()
        return JsonResponse({'success': True, 'message': '密码已修改'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

def calendar_page(request):
    work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.filter(work_id=work_id).first() if work_id else None

    context = {
        'current_employee': current_employee,
    }
    return render(request, 'calendar_view.html', context)

@require_GET
def get_calendar_view(request):
    """
    API: /calendar
    Params:
        - view_type (str): 'day', 'week', 'month'
        - date (str): 'YYYY-MM-DD'
    """
    # 1. 获取当前登录员工
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'code': 401, 'error': '用户未登录'}, status=401)

    try:
        current_employee = Employee.objects.get(pk=current_employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'code': 401, 'error': '用户不存在'}, status=401)

    # 2. 获取查询参数
    view_type = request.GET.get('view_type')
    date_str = request.GET.get('date')
    target_employee_id = request.GET.get('employee_id')

    if not view_type or not date_str:
        return JsonResponse({'code': 400, 'error': '缺少 view_type 或 date 参数'}, status=400)

    try:
        query_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse({'code': 400, 'error': '日期格式错误,请使用 YYYY-MM-DD'}, status=400)

    if target_employee_id:
        try:
            target_employee_id = int(target_employee_id)
            target_employee = Employee.objects.get(pk=target_employee_id)
        except Employee.DoesNotExist:
            return JsonResponse({'code': 404, 'error': '目标员工不存在'}, status=404)
        can_view_all = has_admin_or_ceo_access(current_employee) or check_boss_role(current_employee)
        is_subordinate = Employee.objects.filter(manager_id=current_employee.employee_id, employee_id=target_employee_id).exists()
        if can_view_all or is_subordinate or current_employee.employee_id == target_employee_id:
            current_employee = target_employee
        else:
            return JsonResponse({'code': 403, 'error': '无权限查看该员工视图'}, status=403)

    data = {}

    # 3. 根据视图类型处理

    # 日视图
    if view_type == 'day':
        # 显示当天有效的任务：
        # 1. 创建日期 <= 查询日期
        # 2. 状态是 TO_DO 或 IN_PROGRESS (意味着直到现在还是活跃的，所以在查询日期肯定活跃)
        # 3. 状态是 COMPLETED，但完成日期 >= 查询日期 (意味着在查询日期那天还没完成或刚好完成)
        tasks_on_day = Task.objects.filter(
            assignee=current_employee,
            creation_time__date__lte=query_date
        ).filter(
            Q(status__in=['TO_DO', 'IN_PROGRESS']) |
            Q(status='COMPLETED', completion_time__date__gte=query_date)
        ).order_by('start_time')

        task_list = [
            {
                'task_id': t.task_id,
                'task_name': t.task_name,
                'start_time': t.start_time.isoformat() if t.start_time else None,
                'estimated_duration': t.estimated_duration,
                'status': t.status,
                'priority': t.priority,
                'completion_time': t.completion_time.isoformat() if t.completion_time else None
            } for t in tasks_on_day
        ]

        # 汇总任务统计
        summary = tasks_on_day.aggregate(
            total_tasks=Count('task_id'),
            completed_tasks=Count('task_id', filter=Q(status='COMPLETED', completion_time__date=query_date)),  # 仅统计当天完成的
            in_progress_tasks=Count('task_id', filter=Q(status='IN_PROGRESS'))
        )

        data = {
            'date': query_date.isoformat(),
            'tasks': task_list,
            'summary': summary
        }
        return JsonResponse({'code': 200, 'data': data})

    elif view_type == 'week':
        # 计算周的开始和结束
        start_of_week = query_date - timedelta(days=query_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # 查询本周持续的任务（基于创建时间和完成时间）
        tasks_in_week = Task.objects.filter(
            assignee=current_employee,
            creation_time__date__lte=end_of_week,  # 创建日期不晚于本周结束日期
        ).filter(
            Q(status__in=['TO_DO', 'IN_PROGRESS']) |  # 未完成的任务
            Q(status='COMPLETED', completion_time__date__gte=start_of_week)  # 本周或之后完成的任务
        )

        # 汇总本周概览
        week_summary = tasks_in_week.aggregate(
            total_tasks=Count('task_id'),
            total_completed_tasks=Count('task_id', filter=Q(status='COMPLETED'))
        )

        # 每日统计
        daily_stats = []
        for i in range(7):
            current_day = start_of_week + timedelta(days=i)
            # 筛选出在当天的任务（基于创建时间和完成时间）
            tasks_for_day = tasks_in_week.filter(
                Q(creation_time__date__lte=current_day) &  # 任务已创建
                Q(
                    Q(status__in=['TO_DO', 'IN_PROGRESS']) |  # 未完成的任务
                    Q(status='COMPLETED', completion_time__date__gte=current_day)  # 当天或之后完成的任务
                )
            )

            stats = tasks_for_day.aggregate(
                total_tasks=Count('task_id'),
                completed_tasks=Count('task_id', filter=Q(status='COMPLETED')),
                pending_tasks=Count('task_id', filter=Q(status__in=['TO_DO', 'IN_PROGRESS']))
            )

            completion_rate = (stats['completed_tasks'] / stats['total_tasks'] * 100) if stats['total_tasks'] > 0 else 0

            daily_stats.append({
                'date': current_day.isoformat(),
                'total_tasks': stats['total_tasks'],
                'completed_tasks': stats['completed_tasks'],
                'pending_tasks': stats['pending_tasks'],
                'completion_rate': round(completion_rate, 2)
            })

        # 获取本周任务详情（用于前端显示）
        week_tasks = []
        for task in tasks_in_week:
            week_tasks.append({
                'id': task.task_id,
                'task_id': task.task_id,
                'task_name': task.task_name,
                'start_time': task.start_time.isoformat() if task.start_time else None,
                'due_time': task.due_time.isoformat() if task.due_time else None,
                'estimated_duration': task.estimated_duration,
                'status': task.status,
                'priority': task.priority,
                'creation_time': task.creation_time.isoformat() if task.creation_time else None,
                'completion_time': task.completion_time.isoformat() if task.completion_time else None
            })

        data = {
            'week_start_date': start_of_week.isoformat(),
            'week_end_date': end_of_week.isoformat(),
            'daily_stats': daily_stats,
            'summary': {
                'total_tasks': week_summary['total_tasks'],
                'total_completed_tasks': week_summary['total_completed_tasks']
            },
            'tasks': week_tasks  # 使用tasks键名，与前端保持一致
        }
        return JsonResponse({'code': 200, 'data': data})

    # 月视图
    elif view_type == 'month':
        first_day = query_date.replace(day=1)
        num_days_in_month = calendar.monthrange(query_date.year, query_date.month)[1]
        last_day = query_date.replace(day=num_days_in_month)

        # 获取本月所有活跃任务：
        # 1. 创建日期 <= 本月最后一天 (任务在本月结束前已存在)
        # 2. 状态是 TO_DO 或 IN_PROGRESS (一直活跃)
        # 3. 状态是 COMPLETED，但完成日期 >= 本月第一天 (在本月内或之后才完成，意味着本月至少有一段时间是活跃的)
        tasks_in_month = Task.objects.filter(
            assignee=current_employee,
            creation_time__date__lte=last_day
        ).filter(
            Q(status__in=['TO_DO', 'IN_PROGRESS']) |
            Q(status='COMPLETED', completion_time__date__gte=first_day)
        )

        # 汇总本月统计
        month_summary = tasks_in_month.aggregate(
            total_tasks=Count('task_id'),
            total_completed_tasks=Count('task_id', filter=Q(status='COMPLETED', completion_time__date__lte=last_day)) # 仅统计在本月及之前完成的
        )

        # 构造日历网格数据 (不再返回 weekly_stats，前端也没用到)
        month_calendar_weeks = calendar.monthcalendar(query_date.year, query_date.month)
        days_grid = []
        for week in month_calendar_weeks:
            week_row = []
            for day_num in week:
                if day_num == 0:
                    week_row.append({
                        'date': None,
                        'in_month': False,
                        'total_tasks': 0,
                        'tasks': []
                    })
                    continue
                
                current_day = first_day.replace(day=day_num)
                
                # 筛选出在 current_day 这一天应该显示的任务
                # 逻辑同 Day View: 
                # 1. 创建日期 <= current_day
                # 2. 如果已完成，完成日期必须 >= current_day (否则在那天看来已经是历史了，不应该作为活跃任务条显示)
                #    但是，月视图通常显示这一天“存在过”的任务。
                #    为了视觉连贯性，如果任务在 current_day 完成，它当然应该显示。
                #    如果任务在 current_day 之前完成，它就不应该显示在 current_day 的格子里（除非是长条图，但这里我们用的是格子内的点/条）。
                #    根据截图，月视图是格子形式。
                #    修正逻辑：
                #    显示任务条的条件：
                #    (创建 <= current_day) AND ( (未完成) OR (完成日期 >= current_day) )
                
                tasks_for_day = tasks_in_month.filter(
                    creation_time__date__lte=current_day
                ).filter(
                    Q(status__in=['TO_DO', 'IN_PROGRESS']) |
                    Q(status='COMPLETED', completion_time__date__gte=current_day)
                )

                week_row.append({
                    'date': current_day.isoformat(),
                    'in_month': True,
                    'total_tasks': tasks_for_day.count(),
                    'tasks': [
                        {
                            'id': t.task_id,
                            'task_id': t.task_id,
                            'task_name': t.task_name,
                            'status': t.status,
                            'priority': t.priority,
                            'creation_time': t.creation_time.isoformat() if t.creation_time else None,
                            'completion_time': t.completion_time.isoformat() if t.completion_time else None,
                            'start_time': t.start_time.isoformat() if t.start_time else None,
                            'due_time': t.due_time.isoformat() if t.due_time else None
                        } for t in tasks_for_day.order_by('status', '-priority')[:10]
                    ]
                })
            days_grid.append(week_row)

        month_tasks = []
        for t in tasks_in_month.order_by('-creation_time')[:300]:
            month_tasks.append({
                'id': t.task_id,
                'task_id': t.task_id,
                'task_name': t.task_name,
                'status': t.status,
                'priority': t.priority,
                'creation_time': t.creation_time.isoformat() if t.creation_time else None,
                'completion_time': t.completion_time.isoformat() if t.completion_time else None,
                'start_time': t.start_time.isoformat() if t.start_time else None,
                'due_time': t.due_time.isoformat() if t.due_time else None
            })

        data = {
            'month': query_date.strftime('%Y-%m'),
            'weekly_stats': [], # 暂不计算，前端似乎没用
            'summary': month_summary,
            'days_grid': days_grid,
            'tasks': month_tasks
        }
        return JsonResponse({'code': 200, 'data': data})
