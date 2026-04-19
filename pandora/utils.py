"""
通用工具函数：权限检查、文件存储等
"""
import os
from django.utils import timezone
from django.core.files.storage import default_storage
from pandora.models import Role, EmployeeRole


def check_role(employee, role_name):
    """检查员工是否具有指定角色"""
    try:
        role = Role.objects.get(role_name=role_name)
        return EmployeeRole.objects.filter(
            employee_id=employee.employee_id,
            role_id=role.role_id
        ).exists()
    except Role.DoesNotExist:
        return False


def check_admin_role(employee):
    """检查员工是否具有管理员角色"""
    return check_role(employee, '管理员')


def check_ceo_role(employee):
    """检查员工是否具有CEO角色"""
    return check_role(employee, 'CEO')


def check_boss_role(employee):
    """检查员工是否是boss（同时具有CEO和管理员角色）"""
    return check_admin_role(employee) and check_ceo_role(employee)


def has_admin_or_ceo_access(employee):
    """检查员工是否具有管理员或CEO权限（可以查看所有任务和日志）"""
    return check_admin_role(employee) or check_ceo_role(employee)


def check_task_permission(employee):
    """检查是否有查看所有任务的权限"""
    if has_admin_or_ceo_access(employee):
        return True
    try:
        # 访问 related_name 'permissions'
        return employee.permissions.can_view_all_tasks
    except Exception:
        return False


def check_log_permission(employee):
    """检查是否有查看所有日志的权限"""
    if has_admin_or_ceo_access(employee):
        return True
    try:
        return employee.permissions.can_view_all_logs
    except Exception:
        return False


def save_uploaded_file(file_obj, subdir: str) -> str | None:
    """
    保存上传文件到 MEDIA_ROOT/subdir 下，返回相对路径（供数据库存储）。
    安全增强：
    1. 限制允许的扩展名
    2. 随机化文件名
    """
    if not file_obj:
        return None
        
    # 允许的扩展名白名单
    ALLOWED_EXTENSIONS = {
        # 图片
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
        # 文档
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.md',
        # 压缩包
        '.zip', '.rar', '.7z'
    }
    
    base_name, ext = os.path.splitext(file_obj.name)
    ext = ext.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        # 如果不是允许的类型，抛出异常或记录错误
        # 这里为了用户体验，暂时抛出异常，由调用方捕获
        raise ValueError(f"不支持的文件类型: {ext}")

    timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
    # 再次确保文件名中没有路径遍历字符
    import uuid
    random_suffix = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{random_suffix}{ext}"
    
    relative_path = os.path.join(subdir.strip('/'), filename)
    saved_path = default_storage.save(relative_path, file_obj)
    return saved_path.replace('\\', '/')

