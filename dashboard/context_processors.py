"""
上下文处理器：为所有模板提供导航栏所需的变量
"""
from pandora.models import Employee, EmployeeRole
from pandora.utils import check_admin_role

def navbar_context(request):
    """
    为所有模板提供导航栏上下文
    包括：当前员工信息、管理员权限等
    """
    context = {
        'current_employee_name': None,
        'has_admin_role': False,
        'device_type': request.session.get('device_type') or 'pc',
        'login_token': request.session.get('login_token') or '',
    }
    
    # 如果有登录session，获取员工信息
    current_work_id = request.session.get('current_employee_work_id')
    if current_work_id:
        try:
            current_employee = Employee.objects.get(work_id=current_work_id)
            context['current_employee_name'] = current_employee.employee_name
            context['has_admin_role'] = check_admin_role(current_employee)
        except Employee.DoesNotExist:
            pass
    
    return context
