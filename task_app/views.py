from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from pandora.models import Task, Employee, SubTask, LogEntry, TaskNotificationMessage
from pandora.message_service import send_message
from django.db.models import Q, Case, When, IntegerField
from django.utils import timezone
from pandora.utils import (
    check_admin_role,
    check_ceo_role,
    has_admin_or_ceo_access,
    check_boss_role,
    check_task_permission,  # 新增
    save_uploaded_file,
)


def _build_media_url(request, relative_path):
    if relative_path:
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")
    return ''


def task_page(request):
    """任务主页：展示发布的任务和收到的任务"""
    work_id = request.session.get('current_employee_work_id')
    current_employee = Employee.objects.filter(work_id=work_id).first() if work_id else None

    if not current_employee:
        return redirect('/login_app/login_page/')

    # 检查权限
    is_admin = check_admin_role(current_employee)
    is_ceo = check_ceo_role(current_employee)
    is_boss = check_boss_role(current_employee)
    has_admin_access = has_admin_or_ceo_access(current_employee)
    can_view_all_tasks = check_task_permission(current_employee) # 新增：检查细粒度权限

    # 获取视图切换参数（boss/管理员/有查看所有任务权限者可以切换“我的/全部”）
    view_mode = request.GET.get('view_mode', 'mine')
    search = (request.GET.get('search') or '').strip()
    
    # 如果是boss或有权限，默认显示自己的任务，但可以切换查看所有
    status_order = Case(
        When(status='TO_DO', then=0),
        When(status='IN_PROGRESS', then=1),
        When(status='COMPLETED', then=2),
        default=3,
        output_field=IntegerField()
    )
    if can_view_all_tasks: # 使用细粒度权限判断
        if view_mode == 'all':
            tasks_created = Task.objects.select_related('creator', 'assignee').all().annotate(status_rank=status_order).order_by('status_rank', '-task_id')
            tasks_received = Task.objects.none()
        else:
            tasks_created = Task.objects.filter(creator=current_employee).annotate(status_rank=status_order).order_by('status_rank', '-task_id')
            tasks_received = Task.objects.filter(assignee=current_employee).exclude(creator=current_employee).annotate(status_rank=status_order).order_by('status_rank', '-task_id')
    else:
        tasks_created = Task.objects.filter(creator=current_employee).annotate(status_rank=status_order).order_by('status_rank', '-task_id')
        tasks_received = Task.objects.filter(assignee=current_employee).exclude(creator=current_employee).annotate(status_rank=status_order).order_by('status_rank', '-task_id')

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

    if search:
        name_q = Q(task_name__icontains=search) | Q(description__icontains=search) | Q(project_source__icontains=search) | Q(creator__employee_name__icontains=search) | Q(assignee__employee_name__icontains=search)
        tasks_created = tasks_created.filter(name_q)
        tasks_received = tasks_received.filter(name_q)

    # 当前员工下属（用于普通员工创建任务时选择执行人）
    subordinates = Employee.objects.filter(manager_id=current_employee.employee_id)
    
    # 管理员和CEO可以指定所有执行人
    all_employees = Employee.objects.filter(status='ACTIVE').order_by('employee_name') if has_admin_access else []

    if request.method == 'POST' and current_employee:
        # 创建任务
        task_name = request.POST.get('task_name')
        description = request.POST.get('description', '').strip()
        priority = request.POST.get('priority', 'MEDIUM')
        project_source = request.POST.get('project_source', '')
        assignee_id = request.POST.get('assignee_id') or None
        assignee = Employee.objects.filter(pk=assignee_id).first() if assignee_id else None
        due_time_str = request.POST.get('due_time') or None
        estimated_duration = request.POST.get('estimated_duration') or None

        # 必填项校验
        from django.contrib import messages

        if not assignee:
            messages.error(request, '执行人不能为空')
            return redirect('task_page')
        if not description:
            messages.error(request, '任务描述不能为空')
            return redirect('task_page')
        if not due_time_str:
            messages.error(request, '截止时间不能为空')
            return redirect('task_page')
        try:
            estimated_duration_int = int(estimated_duration)
            if estimated_duration_int <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, '预计时长必须为大于0的整数（分钟）')
            return redirect('task_page')

        # 验证截止日期不能早于创建日期
        due_time = None
        if due_time_str:
            try:
                from django.utils import timezone
                due_time = parse_datetime(due_time_str)
                # 检查截止日期是否早于今天
                if due_time and due_time < timezone.now():
                    messages.error(request, '截止日期不能早于今天')
                    return redirect('task_page')
            except Exception as e:
                messages.error(request, f'日期格式错误: {str(e)}')
                return redirect('task_page')

        attachment_path = save_uploaded_file(request.FILES.get('attachment'), 'tasks')

        new_task = Task.objects.create(
            task_name=task_name,
            description=description,
            priority=priority,
            project_source=project_source,
            creator=current_employee,
            assignee=assignee,
            start_time=None,  # 不需要开始日期
            due_time=due_time,
            estimated_duration=estimated_duration_int,
            status='TO_DO',
            attachment_url=attachment_path
        )
        
        # 如果任务有指定执行人，发送新任务通知
        if assignee:
            try:
                msg = f'您有一个新任务待接取：{task_name}'
                notification = TaskNotificationMessage.objects.create(
                    employee=assignee,
                    task=new_task,
                    notification_type='NEW_TASK',
                    message=msg,
                )
                # 打印调试信息（开发时使用）
                print(f'Notification created: ID={notification.notification_id}, Employee={assignee.employee_name}, Task={task_name}')
                
                # 发送IM通知
                send_message(assignee, '新任务待接取', msg)
            except Exception as e:
                # 如果通知创建失败，打印详细错误信息
                import traceback
                print(f'Failed to create notification for task {task_name}: {e}')
                traceback.print_exc()
        
        return redirect('task_page')

    context = {
        'current_employee': current_employee,
        'subordinates': subordinates,
        'all_employees': all_employees,  # 管理员和CEO可用的所有员工列表
        'tasks_created': tasks_created,
        'tasks_received': tasks_received,
        'has_admin_access': has_admin_access,  # 是否有管理员或CEO权限
        'is_boss': is_boss,  # 是否是boss（CEO+管理员）
        'can_view_all_tasks': can_view_all_tasks, # 是否有查看所有任务权限
        'view_mode': view_mode,  # 当前视图模式（mine/all）
        'search': search,
    }
    return render(request, 'task_page.html', context)

def mobile_task_page(request):
    """移动端任务页面（数据由 /tasks/api/ 提供）"""
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return redirect('/login_app/login_page/')
    return render(request, 'mobile_task_page.html', {})

def mobile_task_detail_page(request, task_id):
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return redirect('/login_app/login_page/')
    return render(request, 'mobile_task_detail_page.html', {'task_id': task_id})

def mobile_task_new_page(request):
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return redirect('/login_app/login_page/')
    # 使用现有 /tasks/ POST 创建任务（简化：不选执行人）
    return render(request, 'mobile_task_new_page.html', {})

def mobile_task_notifications_page(request):
    work_id = request.session.get('current_employee_work_id')
    if not work_id:
        return redirect('/login_app/login_page/')
    return render(request, 'mobile_task_notifications_page.html', {})

def task_detail(request, task_id):
    task = get_object_or_404(Task.objects.select_related('creator', 'assignee'), task_id=task_id)
    attachment_url = _build_media_url(request, getattr(task, 'attachment_url', None))
    
    session = getattr(request, 'session', None)
    current_employee_id = session.get('current_employee_id') if session else None
    is_creator = False
    is_assignee = False
    if current_employee_id:
        current_id = int(current_employee_id)
        is_creator = (task.creator_id == current_id)
        is_assignee = (task.assignee_id == current_id)

    data = {
        'task_code': task.task_code,
        'task_name': task.task_name,
        'description': task.description,
        'priority': task.priority,
        'project_source': task.project_source,
        'creator': task.creator.employee_name,
        'assignee': task.assignee.employee_name if task.assignee else '-',
        'start_time': task.start_time.strftime('%Y-%m-%d %H:%M') if task.start_time else '',
        'completion_time': (getattr(task, 'completion_time', None).strftime('%Y-%m-%d %H:%M') if getattr(task, 'completion_time', None) else ''),
        'estimated_duration': task.estimated_duration,
        'status': task.status,
        'assignee_id': getattr(task, 'assignee_id', None),
        'start_time_iso': task.start_time.strftime('%Y-%m-%dT%H:%M') if task.start_time else '',
        'due_time_iso': task.due_time.strftime('%Y-%m-%dT%H:%M') if task.due_time else '',
        'attachment_url': attachment_url,
        'is_creator': is_creator,
        'is_assignee': is_assignee,
    }
    return JsonResponse(data)

@csrf_exempt
def task_update(request, task_id):
    """编辑任务：管理员和CEO可以编辑所有任务，普通用户只能编辑自己创建的任务"""
    task = get_object_or_404(Task, task_id=task_id)
    
    # 检查权限
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    
    current_employee = get_object_or_404(Employee, pk=current_employee_id)
    has_admin_access = has_admin_or_ceo_access(current_employee)
    can_manage_all = check_task_permission(current_employee)
    
    # 如果不是管理员/CEO/授权员工且不是创建者，则无权编辑
    if not has_admin_access and not can_manage_all and task.creator_id != current_employee.employee_id:
        return JsonResponse({'success': False, 'message': '无权编辑此任务'})

    if request.method == 'POST':
        task.task_name = request.POST.get('task_name')
        task.description = request.POST.get('description')
        task.priority = request.POST.get('priority')
        task.project_source = request.POST.get('project_source')
        assignee_id = request.POST.get('assignee_id') or None
        task.assignee = Employee.objects.filter(employee_id=assignee_id).first() if assignee_id else None

        # 管理员和CEO可以修改状态，普通用户编辑时默认为 TO_DO
        if has_admin_access and request.POST.get('status'):
            task.status = request.POST.get('status')
        else:
            task.status = 'TO_DO'

        task.start_time = parse_datetime(request.POST.get('start_time')) if request.POST.get('start_time') else None
        task.due_time = parse_datetime(request.POST.get('due_time')) if request.POST.get('due_time') else None
        task.estimated_duration = request.POST.get('estimated_duration') or None

        if request.POST.get('remove_attachment') == '1':
            task.attachment_url = None
        else:
            attachment_file = request.FILES.get('attachment')
            if attachment_file:
                task.attachment_url = save_uploaded_file(attachment_file, 'tasks')
        
        # 如果状态改为已完成，设置完成时间
        if task.status == 'COMPLETED' and not task.completion_time:
            task.completion_time = timezone.now()
        elif task.status != 'COMPLETED':
            task.completion_time = None
        
        task.save()

        # 编辑后刷新页面
        return redirect('task_page')

    return JsonResponse({'status': 'fail'})

def task_delete(request, task_id):
    task = get_object_or_404(Task, task_id=task_id)
    
    # 检查权限（管理员和CEO可以删除所有任务，普通用户只能删除自己创建的任务）
    current_employee_id = request.session.get('current_employee_id')
    if current_employee_id:
        current_employee = get_object_or_404(Employee, pk=current_employee_id)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        can_manage_all = check_task_permission(current_employee)
        
        if not has_admin_access and not can_manage_all and task.creator_id != current_employee.employee_id:
            return redirect('task_page')  # 无权删除，跳转
    
    task.delete()
    return redirect('task_page')

def task_update_status(request, task_id):
    current_employee_id = request.session.get('current_employee_id')
    current_employee = get_object_or_404(Employee, pk=current_employee_id)
    task = get_object_or_404(Task, pk=task_id)

    if task.assignee_id != current_employee.employee_id:
        return JsonResponse({'success': False, 'msg': '你无权操作该任务！'})

    if task.status == 'TO_DO':
        task.status = 'IN_PROGRESS'
        task.start_time = timezone.now()
        task.save()
        return JsonResponse({'success': True, 'status': task.status, 'msg': '任务已接取'})
    elif task.status == 'IN_PROGRESS':
        task.status = 'COMPLETED'
        task.completion_time = timezone.now()
        task.save()
        
        # 任务完成时，自动添加到日志（标签为空）
        LogEntry.objects.create(
            employee=current_employee,
            content=f'完成任务：{task.task_name}',
            log_type='WORK',
            emotion_tag=None,  # 标签为空
            log_time=timezone.now()
        )
        
        return JsonResponse({'success': True, 'status': task.status, 'msg': '任务已完成'})
    else:
        return JsonResponse({'success': False, 'msg': '任务已完成'})


def calculate_task_progress(task_id):
    """计算任务进度（仅基于子任务完成比例）"""
    subtasks = SubTask.objects.filter(task_id=task_id)
    try:
        total = subtasks.count()
    except Exception:
        total = len(subtasks) if hasattr(subtasks, '__len__') else 0
    if total == 0:
        return None
    try:
        completed = subtasks.filter(status='COMPLETED').count()
    except Exception:
        completed = len([s for s in subtasks if getattr(s, 'status', '') == 'COMPLETED'])
    return int((completed / total) * 100)


@csrf_exempt
def subtask_list(request, task_id):
    """获取子任务列表"""
    task = get_object_or_404(Task, pk=task_id)
    
    # 检查权限：任务接收者（assignee）或 创建者（creator）都能查看子任务
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
        
    is_assignee = (task.assignee_id == int(current_employee_id))
    is_creator = (task.creator_id == int(current_employee_id))
    
    if not (is_assignee or is_creator):
        return JsonResponse({'success': False, 'message': '无权访问此任务的子任务'})
    
    # 如果是接收者且未接取，返回空列表（视作暂无）
    # 但如果是创建者，应该能看到（如果有的话）
    if is_assignee and task.status == 'TO_DO' and not is_creator:
        return JsonResponse({
            'success': True,
            'subtasks': [],
            'progress': 0
        })
    
    subtasks = SubTask.objects.filter(task_id=task_id).order_by('creation_time')
    subtasks_data = []
    for subtask in subtasks:
        subtasks_data.append({
            'subtask_id': subtask.subtask_id,
            'subtask_name': subtask.subtask_name,
            'description': subtask.description or '',
            'status': subtask.status,
            'creation_time': subtask.creation_time.strftime('%Y-%m-%d %H:%M'),
            'completion_time': subtask.completion_time.strftime('%Y-%m-%d %H:%M') if subtask.completion_time else None,
        })
    
    # 计算任务进度；若任务已完成，则进度强制为100
    progress = calculate_task_progress(task_id)
    if task.status == 'COMPLETED':
        progress = 100
    
    return JsonResponse({
        'success': True,
        'subtasks': subtasks_data,
        'progress': progress
    })


@csrf_exempt
def subtask_create(request, task_id):
    """创建子任务"""
    task = get_object_or_404(Task, pk=task_id)
    
    # 检查权限：任务接收者 或 任务创建者 都能创建子任务
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
        
    is_assignee = task.assignee_id == int(current_employee_id)
    is_creator = task.creator_id == int(current_employee_id)
    
    if not (is_assignee or is_creator):
        return JsonResponse({'success': False, 'message': '无权创建此任务的子任务'})
    
    # 检查任务是否已被接取且未完成
    # 只有接收者需要受“先接取”限制；创建者可以在任务开始前规划子任务
    if is_assignee and task.status == 'TO_DO':
        return JsonResponse({'success': False, 'message': '请先接取任务后才能添加子任务'})
        
    if task.status == 'COMPLETED':
        return JsonResponse({'success': False, 'message': '已完成的任务不能再添加子任务'})
    
    if request.method == 'POST':
        subtask_name = request.POST.get('subtask_name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not subtask_name:
            return JsonResponse({'success': False, 'message': '子任务名称不能为空'})
        
        subtask = SubTask.objects.create(
            task=task,
            subtask_name=subtask_name,
            description=description if description else None,
            status='IN_PROGRESS'  # 默认状态为处理中
        )
        
        # 计算并返回新的进度
        progress = calculate_task_progress(task_id)
        
        return JsonResponse({
            'success': True,
            'message': '子任务创建成功',
            'subtask_id': subtask.subtask_id,
            'progress': progress
        })
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@csrf_exempt
def subtask_update(request, task_id, subtask_id):
    """更新子任务"""
    task = get_object_or_404(Task, pk=task_id)
    subtask = get_object_or_404(SubTask, pk=subtask_id, task=task)
    
    # 检查权限：只有任务接收者才能更新子任务
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id or task.assignee_id != int(current_employee_id):
        return JsonResponse({'success': False, 'message': '无权更新此任务的子任务'})
    
    # 获取当前员工对象
    try:
        current_employee = Employee.objects.get(pk=current_employee_id)
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '员工不存在'})
    
    # 检查任务是否已被接取
    if task.status == 'TO_DO':
        return JsonResponse({'success': False, 'message': '请先接取任务后才能更新子任务'})
    
    if request.method == 'POST':
        try:
            old_status = subtask.status
            
            subtask_name = request.POST.get('subtask_name', '').strip()
            description = request.POST.get('description', '').strip()
            status = request.POST.get('status', '').strip()
            
            # 如果没有传递status，保持原状态
            if not status:
                status = old_status
            
            # 更新子任务字段
            if subtask_name:
                subtask.subtask_name = subtask_name
            if description is not None:
                subtask.description = description if description else None
            
            # 更新状态
            subtask.status = status
            
            # 如果状态改为已完成，设置完成时间
            if status == 'COMPLETED' and not subtask.completion_time:
                subtask.completion_time = timezone.now()
            elif status != 'COMPLETED':
                subtask.completion_time = None
            
            subtask.save()
            
            # 如果子任务状态改为已完成，自动添加到日志
            if status == 'COMPLETED' and old_status != 'COMPLETED':
                LogEntry.objects.create(
                    employee=current_employee,
                    content=f'完成子任务：{subtask.subtask_name}（任务：{task.task_name}）',
                    log_type='WORK',
                    emotion_tag=None,  # 标签为空
                    log_time=timezone.now()
                )
            
            # 如果子任务状态改变，更新父任务进度
            progress = calculate_task_progress(task_id)
            
            # 如果所有子任务都完成，自动将父任务标记为进行中（如果还是TO_DO状态）
            if progress == 100 and task.status == 'TO_DO':
                task.status = 'IN_PROGRESS'
                task.start_time = timezone.now()
                task.save()
            
            return JsonResponse({
                'success': True,
                'message': '子任务更新成功',
                'progress': progress
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'更新失败: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@require_GET
def get_notifications(request):
    """获取当前用户的通知列表"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    
    notifications = TaskNotificationMessage.objects.filter(
        employee_id=current_employee_id
    ).order_by('-created_time')[:20]  # 获取最近20条
    
    notification_list = []
    for notif in notifications:
        notification_list.append({
            'notification_id': notif.notification_id,
            'message': notif.message,
            'notification_type': notif.get_notification_type_display(),
            'is_read': notif.is_read,
            'created_time': notif.created_time.strftime('%Y-%m-%d %H:%M'),
            'task_id': notif.task.task_id if notif.task else None,
            'task_name': notif.task.task_name if notif.task else None,
        })
    
    unread_count = TaskNotificationMessage.objects.filter(
        employee_id=current_employee_id,
        is_read=False
    ).count()
    
    return JsonResponse({
        'success': True,
        'notifications': notification_list,
        'unread_count': unread_count
    })


@csrf_exempt
def mark_notification_read(request, notification_id):
    """标记通知为已读"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    
    try:
        notification = TaskNotificationMessage.objects.get(
            notification_id=notification_id,
            employee_id=current_employee_id
        )
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True, 'message': '已标记为已读'})
    except TaskNotificationMessage.DoesNotExist:
        return JsonResponse({'success': False, 'message': '通知不存在'})


@csrf_exempt
def mark_all_notifications_read(request):
    """标记所有通知为已读"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})
    
    TaskNotificationMessage.objects.filter(
        employee_id=current_employee_id,
        is_read=False
    ).update(is_read=True)
    
    return JsonResponse({'success': True, 'message': '已标记全部为已读'})


@csrf_exempt
def subtask_delete(request, task_id, subtask_id):
    """删除子任务"""
    task = get_object_or_404(Task, pk=task_id)
    subtask = get_object_or_404(SubTask, pk=subtask_id, task=task)
    
    # 检查权限：只有任务接收者才能删除子任务
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id or task.assignee_id != int(current_employee_id):
        return JsonResponse({'success': False, 'message': '无权删除此任务的子任务'})
    
    # 检查任务是否已被接取
    if task.status == 'TO_DO':
        return JsonResponse({'success': False, 'message': '请先接取任务后才能删除子任务'})
    
    if request.method == 'POST':
        subtask.delete()
        
        # 计算并返回新的进度
        progress = calculate_task_progress(task_id)
        
        return JsonResponse({
            'success': True,
            'message': '子任务删除成功',
            'progress': progress
        })
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})
