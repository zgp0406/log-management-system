"""
Log API views for mobile app - JSON responses
"""
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from pandora.models import LogEntry, LogTag, EntryTagLink, Employee
from pandora.utils import check_admin_role, check_ceo_role, check_boss_role, has_admin_or_ceo_access, save_uploaded_file
from django.db.models import Q
import json
import urllib.request
import urllib.parse
import socket


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


def _extract_tags_from_payload(data):
    if hasattr(data, '__contains__') and hasattr(data, 'getlist'):
        if 'tags' in data:
            return data.getlist('tags')
        return None
    return data.get('tags')


def _parse_tag_ids(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        if not raw.strip():
            return []
        return [int(x) for x in raw.split(',') if x.strip()]
    return [int(x) for x in raw]


@require_GET
def logs_api(request):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        current_work_id = request.session.get('current_employee_work_id')
        current_employee = Employee.objects.get(work_id=current_work_id)
        employee_id = current_employee.employee_id
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
        if not (selected_date or start_date or end_date):
            selected_date = timezone.now().date()
        employee_filter = request.GET.get('employee_id', '')
        view_mode = request.GET.get('view_mode', 'mine')
        
        # 根据权限显示日志
        if is_boss or has_admin_access or can_view_all_logs:
            if view_mode == 'all':
                logs_query = LogEntry.objects.select_related('employee')
                if employee_filter:
                    try:
                        filter_employee_id = int(employee_filter)
                        logs_query = logs_query.filter(employee_id=filter_employee_id)
                    except ValueError:
                        pass
            else:
                logs_query = LogEntry.objects.filter(employee_id=employee_id)
        else:
            logs_query = LogEntry.objects.filter(employee_id=employee_id)
            
        if selected_date:
            logs_query = logs_query.filter(log_time__date=selected_date)
        else:
            if start_date:
                logs_query = logs_query.filter(log_time__date__gte=start_date)
            if end_date:
                logs_query = logs_query.filter(log_time__date__lte=end_date)
        search = (request.GET.get('search') or '').strip()
        if search:
            logs_query = logs_query.filter(
                Q(content__icontains=search) |
                Q(employee__employee_name__icontains=search) |
                Q(entrytaglink__tag__tag_name__icontains=search)
            )
        logs_query = logs_query.order_by('-log_time')
        try:
            page = int(request.GET.get('page', '1'))
        except ValueError:
            page = 1
        try:
            page_size = int(request.GET.get('page_size', '20'))
        except ValueError:
            page_size = 20
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        total_count = logs_query.count()
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0
        start = (page - 1) * page_size
        end = start + page_size
        logs = list(logs_query[start:end])
        logs_data = []
        for log in logs:
            log_tags = LogTag.objects.filter(entrytaglink__log_entry=log).values_list('tag_name', flat=True)
            logs_data.append({
                'log_id': log.log_id,
                'employee_id': log.employee.employee_id,
                'employee_name': log.employee.employee_name,
                'log_time': log.log_time.strftime('%Y-%m-%d %H:%M'),
                'content': log.content,
                'log_type': log.get_log_type_display(),
                'log_type_raw': log.log_type,
                'emotion_tag': log.get_emotion_tag_display() if log.emotion_tag else None,
                'emotion_tag_raw': log.emotion_tag,
                'tags': list(log_tags),
                'image_url': _build_media_url(request, log.image_url),
                'location_lat': float(log.location_lat) if log.location_lat is not None else None,
                'location_lng': float(log.location_lng) if log.location_lng is not None else None,
                'location_name': log.location_name or ''
            })
        return JsonResponse({
            'success': True,
            'logs': logs_data,
            'date': selected_date.strftime('%Y-%m-%d') if selected_date else None,
            'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
            'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
            'total_count': total_count,
            'total_pages': total_pages,
            'page': page,
            'page_size': page_size,
            'has_admin_access': has_admin_access,
            'is_boss': is_boss,
            'can_view_all_logs': can_view_all_logs,
            'view_mode': view_mode,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': str(e)})



# 其他移动端辅助 API
@require_GET
def tags_api(request):
    """返回可用的日志标签列表（移动端用于创建/编辑时选择）"""
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})

    tags = LogTag.objects.all().order_by('tag_name')
    return JsonResponse({
        'success': True,
        'tags': [{'tag_id': t.tag_id, 'tag_name': t.tag_name} for t in tags]
    })


@csrf_exempt
@require_POST
def log_create_api(request):
    """创建日志（移动端）
    请求体支持 form 或 JSON：
    - content: str
    - log_type: one of ['WORK','MEETING','COMMUNICATION','DEVELOPMENT','STUDY'] 或中文 ['工作','会议','沟通','开发','学习']
    - emotion_tag: optional ['ACTIVE','FOCUSED','SATISFIED','TIRED'] 或中文 ['积极','专注','满意','疲惫']
    - tags: 可选，标签ID数组，例如 [1,2]
    """
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    data = _get_request_data(request)
    attachment_file = request.FILES.get('log_image')

    content = (data.get('content') or '').strip()
    log_type_in = (data.get('log_type') or '').strip()
    emotion_in = (data.get('emotion_tag') or '').strip()
    tags_in = _extract_tags_from_payload(data)
    tag_ids = _parse_tag_ids(tags_in)

    if not content:
        return JsonResponse({'success': False, 'message': '日志内容不能为空'})

    # 映射中/英枚举
    log_type_map = {
        '工作': 'WORK', '会议': 'MEETING', '沟通': 'COMMUNICATION', '开发': 'DEVELOPMENT', '学习': 'STUDY'
    }
    emotion_map = {
        '积极': 'ACTIVE', '专注': 'FOCUSED', '满意': 'SATISFIED', '疲惫': 'TIRED'
    }

    log_type = log_type_map.get(log_type_in, log_type_in or 'WORK')
    emotion_tag = emotion_map.get(emotion_in, emotion_in or None)

    # 位置字段（可选）
    lat = data.get('location_lat')
    lng = data.get('location_lng')
    loc_name = (data.get('location_name') or '').strip() or None

    try:
        employee = Employee.objects.get(pk=current_employee_id)
        new_log = LogEntry.objects.create(
            employee=employee,
            content=content,
            log_type=log_type,
            emotion_tag=emotion_tag if emotion_tag else None,
            log_time=timezone.now(),
            location_lat=float(lat) if lat not in (None, '') else None,
            location_lng=float(lng) if lng not in (None, '') else None,
            location_name=loc_name
        )

        if attachment_file:
            image_path = save_uploaded_file(attachment_file, 'logs')
            if image_path:
                new_log.image_url = image_path
                new_log.save(update_fields=['image_url'])

        # 处理标签
        if tag_ids is not None:
            for tid in tag_ids:
                try:
                    EntryTagLink.objects.create(log_entry=new_log, tag_id=tid)
                except Exception:
                    pass

        return JsonResponse({'success': True, 'log_id': new_log.log_id})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def log_update_api(request, log_id):
    """更新日志（移动端）- 仅本人或管理员/CEO可编辑"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    try:
        log = LogEntry.objects.get(pk=log_id)
        current_employee = Employee.objects.get(pk=current_employee_id)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        if not has_admin_access and log.employee_id != int(current_employee_id):
            return JsonResponse({'success': False, 'message': '无权编辑此日志'})

        data = _get_request_data(request)
        attachment_file = request.FILES.get('log_image')
        remove_image = str(data.get('remove_image', request.POST.get('remove_image', '0'))).lower() in ('1', 'true', 'yes')

        content = data.get('content')
        log_type_in = data.get('log_type')
        emotion_in = data.get('emotion_tag')
        tags_in = _extract_tags_from_payload(data)
        tag_ids = _parse_tag_ids(tags_in) if tags_in is not None else None

        log_type_map = {
            '工作': 'WORK', '会议': 'MEETING', '沟通': 'COMMUNICATION', '开发': 'DEVELOPMENT', '学习': 'STUDY'
        }
        emotion_map = {
            '积极': 'ACTIVE', '专注': 'FOCUSED', '满意': 'SATISFIED', '疲惫': 'TIRED'
        }

        if content is not None:
            log.content = content.strip()
        if log_type_in:
            log.log_type = log_type_map.get(log_type_in, log_type_in)
        if emotion_in is not None:
            mapped = emotion_map.get(emotion_in, emotion_in)
            log.emotion_tag = mapped or None

        if remove_image:
            log.image_url = None
        elif attachment_file:
            image_path = save_uploaded_file(attachment_file, 'logs')
            if image_path:
                log.image_url = image_path

        # 位置字段（可选）
        lat = data.get('location_lat')
        lng = data.get('location_lng')
        loc_name = data.get('location_name')
        if lat not in (None, ''):
            try: log.location_lat = float(lat)
            except Exception: pass
        if lng not in (None, ''):
            try: log.location_lng = float(lng)
            except Exception: pass
        if loc_name is not None:
            log.location_name = (loc_name or '').strip() or None

        log.save()

        # 覆盖式更新标签（可选）
        if tag_ids is not None:
            EntryTagLink.objects.filter(log_entry=log).delete()
            for tid in tag_ids:
                try:
                    EntryTagLink.objects.create(log_entry=log, tag_id=tid)
                except Exception:
                    pass

        return JsonResponse({'success': True})
    except LogEntry.DoesNotExist:
        return JsonResponse({'success': False, 'message': '日志不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@require_POST
def log_delete_api(request, log_id):
    """删除日志（移动端）- 仅本人或管理员/CEO可删"""
    current_employee_id = request.session.get('current_employee_id')
    if not current_employee_id:
        return JsonResponse({'success': False, 'message': '未登录'})

    try:
        log = LogEntry.objects.get(pk=log_id)
        current_employee = Employee.objects.get(pk=current_employee_id)
        has_admin_access = has_admin_or_ceo_access(current_employee)
        if not has_admin_access and log.employee_id != int(current_employee_id):
            return JsonResponse({'success': False, 'message': '无权删除此日志'})
        log.delete()
        return JsonResponse({'success': True})
    except LogEntry.DoesNotExist:
        return JsonResponse({'success': False, 'message': '日志不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
@require_GET
def amap_ip_proxy(request):
    """
    高德IP定位代理，解决前端跨域/HTTPS混用问题
    """
    key = getattr(settings, 'AMAP_WEB_KEY', '')
    if not key:
        return JsonResponse({'status': '0', 'info': 'AMAP_WEB_KEY missing'})
    
    # 获取客户端IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        client_ip = x_forwarded_for.split(',')[0].strip()
    else:
        client_ip = request.META.get('REMOTE_ADDR', '')

    # 构建API URL，如果获取到了外网IP则传递给高德，否则让高德自动识别请求来源
    base_url = "https://restapi.amap.com/v3/ip"
    params = f"key={urllib.parse.quote(key)}"
    
    # 简单的IP验证：如果是内网IP或本地回环，通常不传ip参数，让高德使用服务器出口IP
    # 这里简单判断，如果有值且不是127.0.0.1，尝试传递
    if client_ip and not client_ip.startswith('127.') and not client_ip.startswith('192.168.') and not client_ip.startswith('10.'):
        params += f"&ip={urllib.parse.quote(client_ip)}"
    
    url = f"{base_url}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = resp.read()
            # 验证返回是否为有效JSON
            try:
                json_data = json.loads(data)
                return JsonResponse(json_data)
            except json.JSONDecodeError:
                return JsonResponse({'status': '0', 'info': 'upstream invalid json'})
    except Exception as e:
        return JsonResponse({'status': '0', 'info': str(e)})


@require_GET
def amap_regeo_proxy(request):
    key = getattr(settings, 'AMAP_WEB_KEY', '')
    if not key:
        return JsonResponse({'status': '0', 'info': 'AMAP_WEB_KEY missing'})
    lng = request.GET.get('lng') or request.GET.get('lon') or ''
    lat = request.GET.get('lat') or ''
    if not lng or not lat:
        return JsonResponse({'status': '0', 'info': 'missing coordinates'})
    coordsys = (request.GET.get('coordsys') or '').lower()
    location = f"{lng},{lat}"
    converted_coords = None
    if coordsys == 'gps':
        try:
            conv_qs = urllib.parse.urlencode({'key': key, 'locations': location, 'coordsys': 'gps'})
            conv_url = f"https://restapi.amap.com/v3/assistant/coordinate/convert?{conv_qs}"
            with urllib.request.urlopen(conv_url, timeout=5) as resp:
                conv_data = json.loads(resp.read().decode('utf-8'))
                loc_str = conv_data.get('locations') or ''
                if conv_data.get('status') == '1' and loc_str:
                    location = loc_str
                    converted_coords = loc_str
        except Exception:
            pass
    qs = urllib.parse.urlencode({'key': key, 'location': location, 'radius': '100', 'extensions': 'all'})
    url = f"https://restapi.amap.com/v3/geocode/regeo?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if converted_coords:
                c_lng, c_lat = converted_coords.split(',')
                data['converted_location'] = {'lng': c_lng, 'lat': c_lat}
            return JsonResponse(data)
    except socket.timeout:
        return JsonResponse({'status': '0', 'info': 'timeout'})
    except Exception as e:
        return JsonResponse({'status': '0', 'info': str(e)})
