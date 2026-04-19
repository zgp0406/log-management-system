from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import check_password, make_password
from pandora.models import Employee
import uuid

# 渲染登录页面
def login_page(request):
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = 'mobile' in ua or 'android' in ua or 'iphone' in ua
    device_type = request.session.get('device_type') or ('mobile' if is_mobile else 'pc')
    current_work_id = request.session.get('current_employee_work_id')
    session_token = request.session.get('login_token')
    already_logged_in = False
    redirect_url = '/m/' if device_type == 'mobile' else '/dashboard/'
    if current_work_id and session_token:
        try:
            employee = Employee.objects.get(work_id=current_work_id)
            db_token = employee.mobile_login_token if device_type == 'mobile' else employee.pc_login_token
            if db_token and db_token == session_token:
                already_logged_in = True
        except Employee.DoesNotExist:
            pass
    kicked = request.GET.get('kicked') == 'true'
    return render(request, 'login.html', {
        'already_logged_in': already_logged_in,
        'redirect_url': redirect_url,
        'kicked': kicked,
        'current_employee_name': request.session.get('current_employee_name', '')
    })

@csrf_exempt
@require_POST
def employee_login(request):
    work_id = request.POST.get('work_id')
    password = request.POST.get('password')
    force_login = request.POST.get('force_login', 'false') == 'true'

    if not work_id or not password:
        return JsonResponse({'success': False, 'message': '请输入工号和密码'})

    try:
        employee = Employee.objects.get(work_id=work_id)
        
        # 验证密码（支持哈希密码和明文密码自动升级）
        if check_password(password, employee.password):
            # 密码正确 (Hash)
            pass
        elif employee.password == password:
            # 密码正确 (明文) -> 自动升级为哈希
            employee.password = make_password(password)
            employee.save()
        else:
            return JsonResponse({'success': False, 'message': '密码错误'})

        # 检测设备类型
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent

        # 检查是否已有同类型设备登录
        # 如果 force_login 为 False，且数据库中有对应 token
        existing_token = employee.mobile_login_token if is_mobile else employee.pc_login_token
        
        if not force_login and existing_token:
            device_name = "移动端" if is_mobile else "PC端"
            return JsonResponse({
                'success': False, 
                'code': 'ALREADY_LOGGED_IN',
                'message': f'当前账号已在其他{device_name}设备登录，是否继续登录？（继续登录将使对方下线）'
            })

        # 执行登录
        # 1. 生成新 Token
        new_token = str(uuid.uuid4())
        
        # 2. 更新数据库
        if is_mobile:
            employee.mobile_login_token = new_token
        else:
            employee.pc_login_token = new_token
        employee.save()
        
        # 3. 设置 Session
        request.session['current_employee_work_id'] = employee.work_id
        request.session['current_employee_name'] = employee.employee_name
        request.session['current_employee_id'] = employee.employee_id
        request.session['login_token'] = new_token  # 保存 Token 到 Session
        request.session['device_type'] = 'mobile' if is_mobile else 'pc' # 记录设备类型
        
        return JsonResponse({'success': True, 'message': '登录成功'})

    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'message': '工号不存在'})


def employee_logout(request):
    try:
        # 清除数据库中的 token
        if request.session.get('current_employee_work_id'):
            employee = Employee.objects.get(work_id=request.session['current_employee_work_id'])
            # 根据当前 session 记录的设备类型清除对应 token
            device_type = request.session.get('device_type')
            if device_type == 'mobile':
                employee.mobile_login_token = None
            elif device_type == 'pc':
                employee.pc_login_token = None
            else:
                # 如果没有记录类型，尝试根据 session 中的 token 匹配并清除（兜底）
                token = request.session.get('login_token')
                if token:
                    if employee.mobile_login_token == token:
                        employee.mobile_login_token = None
                    if employee.pc_login_token == token:
                        employee.pc_login_token = None
            
            employee.save()
    except Exception:
        pass
        
    request.session.flush()
    return redirect('/login_app/login_page/')
