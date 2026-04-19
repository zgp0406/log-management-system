from urllib.parse import urlencode


MOBILE_UA_KEYWORDS = [
    'Mobile', 'Android', 'iPhone', 'iPad', 'iPod', 'Windows Phone', 'webOS'
]


MOBILE_REDIRECT_MAP = {
    '/dashboard/': '/m/',
    '/tasks/': '/m/tasks/',
    '/logs/': '/m/logs/',
    '/ai/': '/m/ai/',
}


class MobileRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # 跳过API与移动端路径、静态资源、登录相关
        # 以及任务的JSON端点（任务详情、子任务、通知等），避免被重定向
        if (path.startswith('/logs/api') or path.startswith('/tasks/api') or path.startswith('/dashboard/api') or path.startswith('/ai/api')
            or path.startswith('/dashboard/get_') or path.startswith('/dashboard/update_')
            or path.startswith('/employee/') or path.startswith('/employee_list/')
            or (path.startswith('/tasks/') and (
                path.endswith('/') and any(seg in path for seg in ['/subtasks/', '/notifications/'])
                or _is_task_json_detail(path)
            ))):
            return self.get_response(request)
        if path.startswith('/m/') or path.startswith('/static/') or path.startswith('/login_app/'):
            return self.get_response(request)

        ua = request.META.get('HTTP_USER_AGENT', '')
        is_mobile = any(k in ua for k in MOBILE_UA_KEYWORDS)

        if is_mobile:
            # 根路径重定向到移动首页
            if path == '/' or path == '':
                return _redirect_with_query('/m/', request)
            # 匹配映射的前缀
            for src_prefix, dst_prefix in MOBILE_REDIRECT_MAP.items():
                if path.startswith(src_prefix):
                    # 保留子路径（目前只对精确页面做入口跳转，避免复杂嵌套路由）
                    return _redirect_with_query(dst_prefix, request)

        return self.get_response(request)


def _redirect_with_query(target_path, request):
    from django.shortcuts import redirect
    query = request.META.get('QUERY_STRING', '')
    if query:
        return redirect(f"{target_path}?{query}")
    return redirect(target_path)


# 判断是否为 /tasks/<int:task_id>/ 这样的任务详情JSON端点
def _is_task_json_detail(path: str) -> bool:
    try:
        if not path.startswith('/tasks/'):
            return False
        # 形如 /tasks/123/ （末尾带斜杠）
        parts = path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'tasks':
            int(parts[1])  # 可转为数字即视为任务详情JSON
            return True
        return False
    except Exception:
        return False

