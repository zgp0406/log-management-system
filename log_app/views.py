from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.forms import ModelForm, Select, CheckboxSelectMultiple, Textarea, DateTimeInput
from pandora.models import LogEntry, LogTag, EntryTagLink, Employee
from datetime import datetime       # 用于字符串解析成日期
from pandora.utils import check_admin_role, check_ceo_role, has_admin_or_ceo_access, check_boss_role, save_uploaded_file


def _build_media_url(request, relative_path):
    if relative_path:
        return request.build_absolute_uri(f"{settings.MEDIA_URL}{relative_path}")
    return ''


# -------------------- 表单定义 --------------------
class LogEntryForm(ModelForm):
    class Meta:
        model = LogEntry
        fields = ['employee', 'content', 'log_type', 'emotion_tag']
        widgets = {
            'content': Textarea(attrs={'rows': 3, 'placeholder': '请输入日志内容...'}),
            'log_type': Select(attrs={'class': 'form-select'}),
            'emotion_tag': Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 确保表单使用正确的选择项
        self.fields['log_type'].choices = LogEntry.LOG_TYPE_CHOICES
        self.fields['emotion_tag'].choices = [('', '请选择情绪')] + LogEntry.EMOTION_CHOICES

# -------------------- 主页面：日志创建 + 列表 --------------------

def log_page(request):
    form = LogEntryForm()
    tags = LogTag.objects.all()

    # 获取当前员工信息
    employee_id = request.session.get('current_employee_id')
    employee_name = request.session.get('current_employee_name')
    work_id = request.session.get('current_employee_work_id')

    if not employee_id:
        # 如果 session 里没有当前员工，重定向到 dashboard 选择员工
        return redirect('/dashboard/')  # 或者你 employee_detail 页面

    current_employee = Employee.objects.filter(pk=employee_id).first()
    if not current_employee:
        return redirect('/dashboard/')

    # 检查权限
    is_admin = check_admin_role(current_employee)
    is_ceo = check_ceo_role(current_employee)
    is_boss = check_boss_role(current_employee)
    has_admin_access = has_admin_or_ceo_access(current_employee)
    
    # 检查额外权限
    can_view_all_logs = False
    try:
        if hasattr(current_employee, 'permissions'):
            can_view_all_logs = current_employee.permissions.can_view_all_logs
    except Exception:
        pass

    # 日期过滤
    date_str = request.GET.get('date')
    if date_str:
        selected_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        selected_date = timezone.now().date()

    # 获取筛选参数（管理员/CEO/有权限者可以使用）
    employee_filter = request.GET.get('employee_id', '')
    
    # 获取视图切换参数
    view_mode = request.GET.get('view_mode', 'mine')
    
    # 根据权限显示日志
    if is_boss or has_admin_access or can_view_all_logs:
        # 只要有其中一种权限，就支持切换查看模式
        if view_mode == 'all':
            # 查看所有日志
            logs = LogEntry.objects.select_related('employee').filter(log_time__date=selected_date)
            # 按员工筛选（如果指定）
            if employee_filter:
                try:
                    filter_employee_id = int(employee_filter)
                    logs = logs.filter(employee_id=filter_employee_id)
                except ValueError:
                    pass
        else:
            # 查看自己的日志（默认）
            logs = LogEntry.objects.filter(employee_id=employee_id, log_time__date=selected_date)
    else:
        # 普通员工：只显示自己的日志
        logs = LogEntry.objects.filter(employee_id=employee_id, log_time__date=selected_date)

    # 搜索过滤
    search = (request.GET.get('search') or '').strip()
    if search:
        logs = logs.filter(
            Q(content__icontains=search) |
            Q(employee__employee_name__icontains=search) |
            Q(entrytaglink__tag__tag_name__icontains=search)
        )

    logs = logs.order_by('-log_time')
    
    # 获取所有员工列表（用于筛选）
    allow_view_all = (is_boss or has_admin_access or can_view_all_logs)
    all_employees = Employee.objects.filter(status='ACTIVE').order_by('employee_name') if (allow_view_all and view_mode == 'all') else []

    # 创建新日志
    if request.method == 'POST':
        log_type_mapping = {
            '工作': 'WORK',
            '会议': 'MEETING',
            '沟通': 'COMMUNICATION',
            '开发': 'DEVELOPMENT',
            '学习': 'STUDY'
        }

        emotion_mapping = {
            '积极': 'ACTIVE',
            '专注': 'FOCUSED',
            '满意': 'SATISFIED',
            '疲惫': 'TIRED'
        }

        post_data = request.POST.copy()
        post_data['employee'] = employee_id  # 自动绑定当前员工

        # 转换 log_type
        if 'log_type' in post_data:
            post_data['log_type'] = log_type_mapping.get(post_data['log_type'], post_data['log_type'])
        # 转换 emotion_tag
        if 'emotion_tag' in post_data:
            post_data['emotion_tag'] = emotion_mapping.get(post_data['emotion_tag'], post_data['emotion_tag'])

        form = LogEntryForm(post_data)
        selected_tags = request.POST.getlist('tags')
        image_file = request.FILES.get('log_image')

        if form.is_valid():
            new_log = form.save(commit=False)
            new_log.log_time = timezone.now()
            # 位置字段（可选）
            try:
                lat = request.POST.get('location_lat')
                lng = request.POST.get('location_lng')
                name = request.POST.get('location_name')
                new_log.location_lat = float(lat) if lat not in (None, '') else None
                new_log.location_lng = float(lng) if lng not in (None, '') else None
                new_log.location_name = (name or '').strip() or None
            except Exception:
                pass
            if image_file:
                image_path = save_uploaded_file(image_file, 'logs')
                if image_path:
                    new_log.image_url = image_path
            new_log.save()
            for tag_id in selected_tags:
                EntryTagLink.objects.create(log_entry=new_log, tag_id=tag_id)
            return redirect('log_app:log_page')

    return render(request, 'log_page.html', {
        'form': form,
        'logs': logs,
        'tags': tags,
        'selected_date': selected_date.strftime("%Y-%m-%d"),
        'has_admin_access': has_admin_access,
        'is_boss': is_boss,
        'can_view_all_logs': can_view_all_logs,
        'all_employees': all_employees,
        'log_type_choices': LogEntry.LOG_TYPE_CHOICES,
        'emotion_choices': LogEntry.EMOTION_CHOICES,
        'current_employee_name': employee_name,
        'view_mode': view_mode,
        'current_employee': current_employee,
        'amap_key': getattr(settings, 'AMAP_WEB_KEY', ''),
        'amap_security_js_code': getattr(settings, 'AMAP_SECURITY_JS_CODE', ''),
        'search': search,
    })


# -------------------- 移动端：日志列表页（轻量响应式） --------------------
def mobile_log_page(request):
    # 简单校验登录态，未登录跳转到登录页
    if not request.session.get('current_employee_work_id'):
        return redirect('/login_app/login_page/')

    # 仅渲染模板，数据通过 /logs/api/ 拉取
    return render(request, 'mobile_log_page.html', {
        'api_base': '',  # 同域
        'amap_key': getattr(settings, 'AMAP_WEB_KEY', ''),
        'amap_security_js_code': getattr(settings, 'AMAP_SECURITY_JS_CODE', ''),
    })


# -------------------- 查看日志详情 --------------------
def log_detail(request, log_id):
    log = get_object_or_404(LogEntry, pk=log_id)
    tags = LogTag.objects.filter(entrytaglink__log_entry=log)
    data = {
        'log_id': log.log_id,
        'employee': log.employee.employee_name,
        'employee_id': log.employee.employee_id,
        'log_time': log.log_time.strftime("%Y-%m-%d %H:%M"),
        'content': log.content,
        'log_type': log.get_log_type_display(),
        'log_type_raw': log.log_type,  # 原始值用于编辑表单
        'emotion_tag': log.get_emotion_tag_display() if log.emotion_tag else '',
        'emotion_tag_raw': log.emotion_tag if log.emotion_tag else '',  # 原始值用于编辑表单
        'tags': [tag.tag_name for tag in tags],
        'tag_ids': [tag.tag_id for tag in tags],
        'image_url': _build_media_url(request, log.image_url),
        'location_lat': float(log.location_lat) if log.location_lat is not None else None,
        'location_lng': float(log.location_lng) if log.location_lng is not None else None,
        'location_name': log.location_name or ''
    }
    return JsonResponse(data)

# -------------------- 更新日志 --------------------
def log_update(request, log_id):
    log = get_object_or_404(LogEntry, pk=log_id)
    
    # 检查权限：管理员和CEO可以编辑所有日志，普通用户只能编辑自己的日志
    current_employee_id = request.session.get('current_employee_id')
    if current_employee_id:
        current_employee = get_object_or_404(Employee, pk=current_employee_id)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        
        if not has_admin_access and log.employee_id != current_employee_id:
            return JsonResponse({'success': False, 'error': '无权编辑此日志'})
    
    if request.method == 'POST':
        # 创建字典来映射前端值到模型值
        log_type_mapping = {
            '工作': 'WORK',
            '会议': 'MEETING',
            '沟通': 'COMMUNICATION',
            '开发': 'DEVELOPMENT',
            '学习': 'STUDY'
        }

        emotion_mapping = {
            '积极': 'ACTIVE',
            '专注': 'FOCUSED',
            '满意': 'SATISFIED',
            '疲惫': 'TIRED'
        }

        # 处理POST数据
        post_data = request.POST.copy()

        # 转换log_type
        if 'log_type' in post_data:
            original_log_type = post_data['log_type']
            if original_log_type in log_type_mapping:
                post_data['log_type'] = log_type_mapping[original_log_type]

        # 转换emotion_tag
        if 'emotion_tag' in post_data:
            original_emotion = post_data['emotion_tag']
            if original_emotion in emotion_mapping:
                post_data['emotion_tag'] = emotion_mapping[original_emotion]

        form = LogEntryForm(post_data, instance=log)
        selected_tags = request.POST.getlist('tags')
        image_file = request.FILES.get('log_image')
        remove_image = request.POST.get('remove_image') == '1'

        if form.is_valid():
            updated_log = form.save()
            if remove_image:
                updated_log.image_url = None
            elif image_file:
                image_path = save_uploaded_file(image_file, 'logs')
                if image_path:
                    updated_log.image_url = image_path
            # 更新位置（可选）
            try:
                lat = request.POST.get('location_lat')
                lng = request.POST.get('location_lng')
                name = request.POST.get('location_name')
                if lat not in (None, ''):
                    updated_log.location_lat = float(lat)
                if lng not in (None, ''):
                    updated_log.location_lng = float(lng)
                if name is not None:
                    updated_log.location_name = (name or '').strip() or None
            except Exception:
                pass
            # 兼容测试桩：如果对象没有 save 方法，忽略
            if hasattr(updated_log, 'save'):
                updated_log.save()
            # 更新标签
            EntryTagLink.objects.filter(log_entry=log).delete()
            for tag_id in selected_tags:
                EntryTagLink.objects.create(log_entry=updated_log, tag_id=tag_id)
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

# -------------------- 删除日志 --------------------
def log_delete(request, log_id):
    log = get_object_or_404(LogEntry, pk=log_id)
    
    # 检查权限：管理员和CEO可以删除所有日志，普通用户只能删除自己的日志
    current_employee_id = request.session.get('current_employee_id')
    if current_employee_id:
        current_employee = get_object_or_404(Employee, pk=current_employee_id)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        
        if not has_admin_access and log.employee_id != current_employee_id:
            return JsonResponse({'success': False, 'error': '无权删除此日志'})
    
    if request.method == 'POST':
        log.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})
