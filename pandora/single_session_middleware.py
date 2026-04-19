from django.shortcuts import redirect
from pandora.models import Employee

class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 排除登录页面和登出页面
        if request.path.startswith('/login_app/') or request.path.startswith('/static/') or request.path.startswith('/media/'):
            return self.get_response(request)

        # 检查是否已登录
        current_work_id = request.session.get('current_employee_work_id')
        session_token = request.session.get('login_token')
        
        # 优先使用 session 中记录的 device_type，如果没有则实时判断
        session_device_type = request.session.get('device_type')
        
        if not session_device_type:
            user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
            is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent
            session_device_type = 'mobile' if is_mobile else 'pc'

        if current_work_id:
            try:
                employee = Employee.objects.get(work_id=current_work_id)
                
                # 根据设备类型检查对应的 token
                db_token = None
                if session_device_type == 'mobile':
                    db_token = employee.mobile_login_token
                else:
                    db_token = employee.pc_login_token

                # 如果数据库中的 token 存在且与 session 中的不一致，说明在别处登录了
                if db_token and db_token != session_token:
                    request.session.flush()  # 清空当前 session
                    return redirect('/login_app/login_page/?kicked=true')
                    
            except Employee.DoesNotExist:
                request.session.flush()
                return redirect('/login_app/login_page/')

        return self.get_response(request)
