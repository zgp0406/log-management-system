from django.shortcuts import render
from django.http import Http404
from django.conf import settings
import os
from pandora.models import Employee
from pandora.utils import check_admin_role


def _base_context(request):
    name = request.session.get('current_employee_name', '')
    work_id = request.session.get('current_employee_work_id')
    has_admin = False
    try:
        if work_id:
            emp = Employee.objects.get(work_id=work_id)
            has_admin = check_admin_role(emp)
    except Exception:
        has_admin = False
    return {
        'current_employee_name': name,
        'has_admin_role': has_admin,
    }


def ai_dashboard_page(request):
    return render(request, 'ai_app/ai_dashboard.html', _base_context(request))


def mobile_ai_dashboard_page(request):
    return render(request, 'ai_app/mobile_ai_dashboard.html', _base_context(request))


def weekly_report_detail(request, filename):
    """
    显示周报详情页
    """
    # 安全检查：只允许访问 reports 目录下的 .md 文件
    # 防止目录遍历攻击
    if '..' in filename or '/' in filename or '\\' in filename:
        raise Http404("Invalid filename")
    
    if not filename.endswith('.md'):
        raise Http404("Invalid file type")

    file_path = os.path.join(settings.MEDIA_ROOT, 'reports', filename)
    
    if not os.path.exists(file_path):
        raise Http404("Report not found")
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        raise Http404("Error reading file")
        
    context = _base_context(request)
    context.update({
        'report_content': content,
        'report_title': filename,
        'download_url': f"{settings.MEDIA_URL}reports/{filename}"
    })
    return render(request, 'ai_app/weekly_report_view.html', context)
