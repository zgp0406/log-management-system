"""
Task API views for mobile app - JSON responses
"""
from django.conf import settings
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q, Case, When, IntegerField
from django.utils import timezone
from pandora.models import Task, Employee, SubTask, LogEntry, TaskNotificationMessage
from pandora.utils import check_admin_role, check_ceo_role, check_boss_role, has_admin_or_ceo_access, save_uploaded_file, check_task_permission
from pandora.message_service import send_message
from django.utils.dateparse import parse_datetime
import queue
import time
import json


def _build_media_url(request, relative_path):
    if relative_path:
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")
    return ''


def _get_request_data(request):
    content_type = request.META.get('CONTENT_TYPE', '')
    if 'application/json' in content_type:
        try:
            body = request.body.decode('utf-8') if request.body else ''
            return json.loads(body) if body else {}
        except Exception:
            return {}
    return request.POST


_notif_queues = {}

def _publish_notification(employee_id, payload):
    try:
        qs = _notif_queues.get(int(employee_id)) or [];
        for q in list(qs):
            try:
                q.put(payload, block=False)
            except Exception:
                pass
    except Exception:
        pass

@require_GET
def notifications_stream(request):
    eid = request.session.get('current_employee_id')
    if not eid:
        return JsonResponse({'success': False, 'message': '未登录'})
    q = queue.Queue()
    lst = _notif_queues.get(int(eid))
    if lst is None:
        lst = []
        _notif_queues[int(eid)] = lst
    lst.append(q)
    def gen():
        yield 'retry: 2000\n\n'
        try:
            while True:
                try:
                    item = q.get(timeout=25)
                    data = json.dumps(item, ensure_ascii=False)
                    yield f'data: {data}\n\n'
                except queue.Empty:
                    yield 'event: ping\n\n'
        finally:
            try:
                lst = _notif_queues.get(int(eid)) or []
                if q in lst:
                    lst.remove(q)
            except Exception:
                pass
    resp = StreamingHttpResponse(gen(), content_type='text/event-stream')
    resp['Cache-Control'] = 'no-cache'
    return resp


@require_GET
def tasks_api(request):
    """返回任务列表的JSON API"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    
    try:
        current_work_id = request.session.get('current_employee_work_id')
        current_employee = Employee.objects.get(work_id=current_work_id)
        
        # 检查权限
        is_admin = check_admin_role(current_employee)
        is_ceo = check_ceo_role(current_employee)
        is_boss = check_boss_role(current_employee)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        can_view_all_tasks = check_task_permission(current_employee)
        
        view_mode = request.GET.get('view_mode', 'mine')
        search = (request.GET.get('search') or '').strip()
        date_str = request.GET.get('date')
        start_str = request.GET.get('start_date')
        end_str = request.GET.get('end_date')
        selected_date = None
        start_date = None
        end_date = None
        if date_str:
            try:
                selected_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                selected_date = None
        if start_str:
            try:
                start_date = timezone.datetime.strptime(start_str, "%Y-%m-%d").date()
            except Exception:
                start_date = None
        if end_str:
            try:
                end_date = timezone.datetime.strptime(end_str, "%Y-%m-%d").date()
            except Exception:
                end_date = None
        
        employee_filter = request.GET.get('employee_id', '')

        # 如果是boss/管理员或有权限，支持“我的/全部”切换
        if can_view_all_tasks:
            if view_mode == 'all':
                tasks_created = Task.objects.select_related('creator', 'assignee').all()
                if employee_filter:
                    try:
                        filter_eid = int(employee_filter)
                        tasks_created = tasks_created.filter(Q(creator_id=filter_eid) | Q(assignee_id=filter_eid))
                    except ValueError:
                        pass
                tasks_received = Task.objects.none()
            else:
                tasks_created = Task.objects.filter(creator=current_employee)
                tasks_received = Task.objects.filter(assignee=current_employee).exclude(creator=current_employee)
        else:
            tasks_created = Task.objects.filter(creator=current_employee)
            tasks_received = Task.objects.filter(assignee=current_employee).exclude(creator=current_employee)

        if selected_date:
            tasks_created = tasks_created.filter(creation_time__date=selected_date)
            tasks_received = tasks_received.filter(creation_time__date=selected_date)
        else:
            if start_date:
                tasks_created = tasks_created.filter(creation_time__date__gte=start_date)
                tasks_received = tasks_received.filter(creation_time__date__gte=start_date)
            if end_date:
                tasks_created = tasks_created.filter(creation_time__date__lte=end_date)
                tasks_received = tasks_received.filter(creation_time__date__lte=end_date)

        # 搜索过滤（按任务名、描述、项目来源、创建人/执行人姓名）
        if search:
            name_q = Q(task_name__icontains=search) | Q(description__icontains=search) | Q(project_source__icontains=search) | Q(creator__employee_name__icontains=search) | Q(assignee__employee_name__icontains=search)
            if isinstance(tasks_created, list):
                # 不会发生，但以防万一
                pass
            else:
                tasks_created = tasks_created.select_related('creator', 'assignee').filter(name_q)
            if isinstance(tasks_received, list):
                # list -> 再查一遍以便过滤
                received_ids = [t.task_id for t in tasks_received]
                tasks_received = list(Task.objects.select_related('creator', 'assignee').filter(task_id__in=received_ids).filter(name_q))
            else:
                tasks_received = tasks_received.select_related('creator', 'assignee').filter(name_q)

        status_order = Case(
            When(status='TO_DO', then=0),
            When(status='IN_PROGRESS', then=1),
            When(status='COMPLETED', then=2),
            default=3,
            output_field=IntegerField()
        )
        tasks_created = tasks_created.annotate(status_rank=status_order).order_by('status_rank', '-task_id')
        tasks_received = tasks_received.annotate(status_rank=status_order).order_by('status_rank', '-task_id')
        
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        try:
            # 移动端默认分页大小调小，优化加载速度
            page_size = int(request.GET.get('page_size', '10'))
        except ValueError:
            page_size = 10
        try:
            page_created = int(request.GET.get('page_created', str(page)))
        except ValueError:
            page_created = page
        try:
            page_size_created = int(request.GET.get('page_size_created', str(page_size)))
        except ValueError:
            page_size_created = page_size
        try:
            page_received = int(request.GET.get('page_received', str(page)))
        except ValueError:
            page_received = page
        try:
            page_size_received = int(request.GET.get('page_size_received', str(page_size)))
        except ValueError:
            page_size_received = page_size
        if page_created < 1:
            page_created = 1
        if page_size_created < 1:
            page_size_created = 10
        if page_received < 1:
            page_received = 1
        if page_size_received < 1:
            page_size_received = 10

        total_created = tasks_created.count()
        total_pages_created = (total_created + page_size_created - 1) // page_size_created if page_size_created > 0 else 0
        start_created = (page_created - 1) * page_size_created
        end_created = start_created + page_size_created
        total_received = tasks_received.count()
        total_pages_received = (total_received + page_size_received - 1) // page_size_received if page_size_received > 0 else 0
        start_received = (page_received - 1) * page_size_received
        end_received = start_received + page_size_received

        tasks_created = list(tasks_created[start_created:end_created])
        tasks_received = list(tasks_received[start_received:end_received])

        # 转换为JSON格式
        tasks_created_data = []
        for task in tasks_created:
            tasks_created_data.append({
                'task_id': task.task_id,
                'task_code': task.task_code or '',
                'task_name': task.task_name,
                'description': task.description or '',
                'priority': task.priority,
                'project_source': task.project_source or '',
                'creator_id': task.creator.employee_id,
                'creator_name': task.creator.employee_name,
                'assignee_id': task.assignee.employee_id if task.assignee else None,
                'assignee_name': task.assignee.employee_name if task.assignee else None,
                'start_time': task.start_time.strftime('%Y-%m-%d %H:%M') if task.start_time else None,
                'due_time': task.due_time.strftime('%Y-%m-%d %H:%M') if task.due_time else None,
                'estimated_duration': task.estimated_duration,
                'status': task.status,
                'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
                'completion_time': task.completion_time.strftime('%Y-%m-%d %H:%M') if task.completion_time else None,
                'attachment_url': _build_media_url(request, task.attachment_url),
                'version': task.version,  # 返回版本号
            })
        
        tasks_received_data = []
        for task in tasks_received:
            tasks_received_data.append({
                'task_id': task.task_id,
                'task_code': task.task_code or '',
                'task_name': task.task_name,
                'description': task.description or '',
                'priority': task.priority,
                'project_source': task.project_source or '',
                'creator_id': task.creator.employee_id,
                'creator_name': task.creator.employee_name,
                'assignee_id': task.assignee.employee_id if task.assignee else None,
                'assignee_name': task.assignee.employee_name if task.assignee else None,
                'start_time': task.start_time.strftime('%Y-%m-%d %H:%M') if task.start_time else None,
                'due_time': task.due_time.strftime('%Y-%m-%d %H:%M') if task.due_time else None,
                'estimated_duration': task.estimated_duration,
                'status': task.status,
                'creation_time': task.creation_time.strftime('%Y-%m-%d %H:%M'),
                'completion_time': task.completion_time.strftime('%Y-%m-%d %H:%M') if task.completion_time else None,
                'attachment_url': _build_media_url(request, task.attachment_url),
                'version': task.version,  # 返回版本号
            })
        
        return JsonResponse({
            'success': True,
            'tasks_created': tasks_created_data,
            'tasks_received': tasks_received_data,
            'created_total_count': total_created,
            'created_total_pages': total_pages_created,
            'created_page': page_created,
            'created_page_size': page_size_created,
            'received_total_count': total_received,
            'received_total_pages': total_pages_received,
            'received_page': page_received,
            'received_page_size': page_size_received,
            'has_admin_access': has_admin_access,
            'can_view_all_tasks': can_view_all_tasks,
            'is_boss': is_boss,
            'view_mode': view_mode,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def task_take_api(request, task_id):
    """移动端接取任务（仅任务执行人可操作）"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        task = Task.objects.get(pk=task_id)
        if task.assignee_id != int(current_employee_id):
            return JsonResponse({'success': False, 'message': '你无权操作该任务'})
        # 幂等处理：已进行中视为成功
        if task.status == 'IN_PROGRESS':
            return JsonResponse({'success': True, 'status': task.status})
        if task.status != 'TO_DO':
            return JsonResponse({'success': False, 'message': '任务不可接取'})
        task.status = 'IN_PROGRESS'
        task.start_time = timezone.now()
        task.save()
        return JsonResponse({'success': True, 'status': task.status})
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'message': '任务不存在'})


@csrf_exempt
@require_POST
def task_complete_api(request, task_id):
    """移动端完成任务（仅任务执行人可操作）"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        task = Task.objects.get(pk=task_id)
        if task.assignee_id != int(current_employee_id):
            return JsonResponse({'success': False, 'message': '你无权操作该任务'})
        # 幂等处理：已完成视为成功
        if task.status == 'COMPLETED':
            return JsonResponse({'success': True, 'status': task.status})
        if task.status != 'IN_PROGRESS':
            return JsonResponse({'success': False, 'message': '任务不可完成'})
        # 标记任务完成
        task.status = 'COMPLETED'
        task.completion_time = timezone.now()
        task.save()

        # 将所有子任务标记为完成，并为每个子任务写入日志
        incomplete_subtasks = SubTask.objects.filter(task_id=task.task_id).exclude(status='COMPLETED')
        for sub in incomplete_subtasks:
            sub.status = 'COMPLETED'
            sub.completion_time = timezone.now()
            sub.save()
            try:
                LogEntry.objects.create(
                    employee_id=current_employee_id,
                    content=f'完成子任务：{sub.subtask_name}（任务：{task.task_name}）',
                    log_type='WORK',
                    emotion_tag=None,
                    log_time=timezone.now()
                )
            except Exception:
                pass

        # 写入完成任务日志
        try:
            LogEntry.objects.create(
                employee_id=current_employee_id,
                content=f'完成任务：{task.task_name}',
                log_type='WORK',
                emotion_tag=None,
                log_time=timezone.now()
            )
        except Exception:
            pass

        # 通知任务创建人（上级）
        try:
            if task.creator_id and task.creator_id != int(current_employee_id):
                note = TaskNotificationMessage.objects.create(
                    employee_id=task.creator_id,
                    task=task,
                    notification_type='TASK_COMPLETED',
                    message=f'{task.assignee.employee_name if task.assignee else "员工"}已完成任务：{task.task_name}',
                )
                _publish_notification(task.creator_id, {
                    'type': 'TASK_COMPLETED',
                    'message': note.message,
                    'task_id': task.task_id,
                    'task_name': task.task_name,
                    'created_time': timezone.now().strftime('%Y-%m-%d %H:%M')
                })
                
                # 发送IM通知
                send_message(task.creator, '任务完成通知', note.message)
                
        except Exception:
            pass

        return JsonResponse({'success': True, 'status': task.status})
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'message': '任务不存在'})


@csrf_exempt
@require_POST
def task_create_api(request):
    """移动端创建任务（JSON 或表单），尽量与网页端校验一致"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    data = _get_request_data(request)
    attachment_file = request.FILES.get('attachment')

    try:
        creator = Employee.objects.get(pk=current_employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '当前用户不存在'})

    task_name = (data.get('task_name') or '').strip()
    task_name = task_name[:16]
    description = (data.get('description') or '').strip()
    priority = (data.get('priority') or 'MEDIUM').strip() or 'MEDIUM'
    project_source = (data.get('project_source') or '').strip()
    assignee_id = data.get('assignee_id')
    due_time_str = data.get('due_time') or None
    estimated_duration = data.get('estimated_duration') or None

    if not task_name:
        return JsonResponse({'success': False, 'message': '任务名称不能为空'})
    if not description:
        return JsonResponse({'success': False, 'message': '任务描述不能为空'})

    # 执行人必填
    if not assignee_id:
        return JsonResponse({'success': False, 'message': '执行人不能为空'})
    try:
        assignee = Employee.objects.get(pk=int(assignee_id))
    except Exception:
        return JsonResponse({'success': False, 'message': '执行人无效'})

    # 预计时长校验（可选）
    estimated_duration_int = None
    if estimated_duration not in (None, ''):
        try:
            estimated_duration_int = int(estimated_duration)
            if estimated_duration_int <= 0:
                raise ValueError()
        except Exception:
            return JsonResponse({'success': False, 'message': '预计时长必须为大于0的整数（分钟）'})

    # 截止时间校验（可选且不能早于当前时间）
    due_time = None
    if due_time_str:
        try:
            due_time = parse_datetime(due_time_str)
            if due_time and due_time < timezone.now():
                return JsonResponse({'success': False, 'message': '截止时间不能早于当前时间'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'日期格式错误: {str(e)}'})

    try:
        attachment_path = save_uploaded_file(attachment_file, 'tasks') if attachment_file else None
        new_task = Task.objects.create(
            task_name=task_name,
            description=description,
            priority=priority,
            project_source=project_source,
            creator=creator,
            assignee=assignee,
            start_time=None,
            due_time=due_time,
            estimated_duration=estimated_duration_int,
            status='TO_DO',
            attachment_url=attachment_path
        )
        # 新任务通知（有执行人时）
        if assignee:
            try:
                msg = f'您有一个新任务待接取：{task_name}'
                TaskNotificationMessage.objects.create(
                    employee=assignee,
                    task=new_task,
                    notification_type='NEW_TASK',
                    message=msg,
                )
                
                # 发送IM通知
                send_message(assignee, '新任务待接取', msg)
            except Exception:
                pass
        return JsonResponse({'success': True, 'task_id': new_task.task_id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def task_update_api(request, task_id):
    """移动端编辑任务（仅管理员/CEO或创建者可改）"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    try:
        task = Task.objects.get(pk=task_id)
        current_employee = Employee.objects.get(pk=current_employee_id)
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'message': '任务不存在'})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '当前用户不存在'})

    has_admin_access = has_admin_or_ceo_access(current_employee)
    can_manage_all = check_task_permission(current_employee)
    if not has_admin_access and not can_manage_all and task.creator_id != current_employee.employee_id:
        return JsonResponse({'success': False, 'message': '无权编辑此任务'})

    data = _get_request_data(request)
    attachment_file = request.FILES.get('attachment')
    remove_attachment = str(data.get('remove_attachment', request.POST.get('remove_attachment', '0'))).lower() in ('1', 'true', 'yes')

    # 可改字段（状态不由前端编辑；编辑后强制置为 TO_DO）
    if 'task_name' in data:
        task.task_name = (data.get('task_name') or '').strip()[:16]
    if 'description' in data:
        task.description = (data.get('description') or '').strip()
    if 'priority' in data:
        task.priority = (data.get('priority') or 'MEDIUM').strip() or 'MEDIUM'
    if 'project_source' in data:
        task.project_source = (data.get('project_source') or '').strip()
    if 'assignee_id' in data:
        aid = data.get('assignee_id')
        prev_assignee_id = task.assignee_id
        task.assignee = Employee.objects.filter(pk=aid).first() if aid else None
        # 如果更换了执行人，给新执行人发“新任务”通知
        if task.assignee_id and task.assignee_id != prev_assignee_id:
            try:
                msg = f'您有一个新任务待接取：{task.task_name}'
                TaskNotificationMessage.objects.create(
                    employee_id=task.assignee_id,
                    task=task,
                    notification_type='NEW_TASK',
                    message=msg,
                )
                
                # 发送IM通知
                send_message(task.assignee, '新任务待接取', msg)
            except Exception:
                pass
    if 'start_time' in data:
        st = data.get('start_time')
        task.start_time = parse_datetime(st) if st else None
    if 'due_time' in data:
        dt = data.get('due_time')
        task.due_time = parse_datetime(dt) if dt else None
    if 'estimated_duration' in data:
        ed = data.get('estimated_duration')
        task.estimated_duration = int(ed) if str(ed).strip() != '' else None

    # 乐观锁检查
    version = data.get('version')
    if version is not None:
        try:
            if int(version) != task.version:
                return JsonResponse({'success': False, 'message': '当前数据已被他人修改，请刷新页面后重试'})
        except ValueError:
            pass
            
    # 版本号自增
    task.version += 1

    if remove_attachment:
        task.attachment_url = None
    elif attachment_file:
        task.attachment_url = save_uploaded_file(attachment_file, 'tasks')

    # 编辑后状态统一重置为 TO_DO
    task.status = 'TO_DO'

    # 完成时间联动（编辑回 TO_DO，不设置完成时间）
    if task.status == 'COMPLETED' and not task.completion_time:
        task.completion_time = timezone.now()
    if task.status != 'COMPLETED':
        task.completion_time = None

    task.save()
    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def task_delete_api(request, task_id):
    """移动端删除任务（仅管理员/CEO或创建者）"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    try:
        task = Task.objects.get(pk=task_id)
        current_employee = Employee.objects.get(pk=current_employee_id)
    except Task.DoesNotExist:
        return JsonResponse({'success': False, 'message': '任务不存在'})
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '当前用户不存在'})

    has_admin_access = has_admin_or_ceo_access(current_employee)
    can_manage_all = check_task_permission(current_employee)
    if not has_admin_access and not can_manage_all and task.creator_id != current_employee.employee_id:
        return JsonResponse({'success': False, 'message': '无权删除此任务'})

    task.delete()
    return JsonResponse({'success': True})
