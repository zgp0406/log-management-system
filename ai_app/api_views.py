import json
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from pandora.models import Employee, Task, LogEntry, Department
from datetime import timedelta
from pandora.models import AiAnalysisProfile, AiDeptAnalysisProfile, AiMbtiCache, EmployeeRole
from pandora.message_service import send_message


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _check_ai_config() -> tuple[bool, str]:
    """检查AI服务配置状态，返回(是否可用, 状态消息)"""
    api_key = getattr(settings, 'AI_API_KEY', '')
    if not api_key:
        return False, 'AI服务未配置'
    
    provider = getattr(settings, 'AI_PROVIDER', 'zhipu')
    if provider not in ['zhipu']:
        return False, f'不支持的AI服务提供商: {provider}'
    
    return True, '配置正常'


def _call_ai(prompt: str) -> str:
    provider = getattr(settings, 'AI_PROVIDER', 'zhipu')
    model = getattr(settings, 'AI_MODEL', 'glm-4')
    api_key = getattr(settings, 'AI_API_KEY', '')
    if not api_key:
        return 'AI服务未配置'

    if provider == 'zhipu':
        import urllib.request
        import urllib.error
        url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
        body = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ]
        }
        data = json.dumps(body).encode('utf-8')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req) as resp:
                    payload = json.loads(resp.read())
                    content = (
                        payload.get('choices', [{}])[0]
                        .get('message', {})
                        .get('content')
                    )
                    if isinstance(content, list):
                        try:
                            return ''.join([item.get('text', '') for item in content])
                        except Exception:
                            pass
                    return content or 'AI建议生成失败'
            except Exception as e:
                if attempt == 1:
                    return 'AI建议生成失败'
                continue

    return 'AI服务未配置'


def _generate_personal_profile(emp):
    """基于员工近 30 天的数据生成个人 AI 画像并写回数据库。"""
    now = timezone.now()
    start_30d = now - timedelta(days=30)

    task_qs = Task.objects.filter(assignee=emp, creation_time__gte=start_30d)
    log_qs = LogEntry.objects.filter(employee=emp, log_time__gte=start_30d)

    task_stats = {
        'recent_total': task_qs.count(),
        'completed': task_qs.filter(status='COMPLETED').count(),
        'in_progress': task_qs.filter(status='IN_PROGRESS').count(),
        'pending': task_qs.filter(status='TO_DO').count(),
    }

    log_types = {}
    emotions = {}
    for log in log_qs:
        key = log.get_log_type_display()
        log_types[key] = log_types.get(key, 0) + 1
        emo = log.get_emotion_tag_display() if log.emotion_tag else '未标注'
        emotions[emo] = emotions.get(emo, 0) + 1

    dept_task_stats = {}
    if emp.department_id:
        dept_qs = Task.objects.filter(assignee__department_id=emp.department_id, creation_time__gte=start_30d)
        dept_task_stats = {
            'completed': dept_qs.filter(status='COMPLETED').count(),
            'in_progress': dept_qs.filter(status='IN_PROGRESS').count(),
            'pending': dept_qs.filter(status='TO_DO').count(),
        }

    prof = AiAnalysisProfile.objects.filter(employee=emp).first()
    prompt = (
        '你是一个企业数据分析顾问。以下为近30天任务与日志统计，'
        '请用中文给出简短的可执行建议。'
        '请务必返回纯JSON格式，不要包含Markdown标记。'
        '格式：{"trend": "趋势(50字内)", "risk": "风险(50字内)", "actions": ["建议1", "建议2", "建议3"]}\n'
        f"个人任务统计(30天)：{task_stats}.\n"
        f"日志类型分布(30天)：{log_types}. 情绪分布：{emotions}.\n"
        f"部门任务统计(30天)：{dept_task_stats}"
    )
    advice = _call_ai(prompt).replace('```json', '').replace('```', '').strip()

    failed = (
        (advice or '').startswith('AI建议生成失败')
        or (advice or '').startswith('网络错误')
        or (advice in ('AI服务未配置', '未配置 AI 密钥', 'AI服务未配置', 'AI建议生成失败'))
    )
    if failed:
        if prof and prof.ai_advice:
            advice = prof.ai_advice
        else:
            advice = json.dumps({
                "trend": f"近30天参与任务{task_stats.get('recent_total', 0)}个，整体表现稳定。",
                "risk": "需注意任务优先级管理，避免积压。",
                "actions": ["每日早晨规划今日待办", "大任务拆解为小步骤", "及时同步进度给主管"]
            }, ensure_ascii=False)

    if advice and not advice.startswith('AI建议生成失败') and not advice.startswith('网络错误') and advice not in ('AI服务未配置', 'AI服务未配置'):
        obj, _ = AiAnalysisProfile.objects.get_or_create(employee=emp)
        obj.ai_advice = advice
        obj.save()

    return {
        'task_stats': task_stats,
        'log_types': log_types,
        'emotions': emotions,
        'dept_task_stats': dept_task_stats,
        'ai_advice': advice,
    }


@require_GET
def ai_dashboard_api(request):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        work_id = request.session.get('current_employee_work_id')
        emp = Employee.objects.get(work_id=work_id)
        scope = (request.GET.get('scope') or 'personal').lower()
        dept_id = request.GET.get('department_id')

        now = timezone.now()
        start_30d = now - timedelta(days=30)
        is_admin = False
        try:
            from pandora.utils import has_admin_or_ceo_access
            is_admin = has_admin_or_ceo_access(emp)
        except Exception:
            is_admin = False

        if scope == 'department':
            # 非管理员仅允许查看自己所属部门
            if not is_admin:
                dept_id_int = emp.department_id or 0
            else:
                try:
                    dept_id_int = int(dept_id) if dept_id else (emp.department_id or 0)
                except Exception:
                    dept_id_int = emp.department_id or 0
            task_qs = Task.objects.filter(assignee__department_id=dept_id_int, creation_time__gte=start_30d)
            recent_tasks = task_qs
        else:
            if is_admin:
                task_qs = Task.objects.filter(creation_time__gte=start_30d)
                recent_tasks = task_qs
            else:
                task_qs = Task.objects.filter(assignee=emp, creation_time__gte=start_30d)
                recent_tasks = task_qs

        task_stats = {
            'recent_total': recent_tasks.count(),
            'completed': recent_tasks.filter(status='COMPLETED').count(),
            'in_progress': recent_tasks.filter(status='IN_PROGRESS').count(),
            'pending': recent_tasks.filter(status='TO_DO').count(),
        }

        if scope == 'department':
            dept_id_int = (emp.department_id or 0) if not is_admin else (int(dept_id) if dept_id and dept_id.isdigit() else (emp.department_id or 0))
            log_qs = LogEntry.objects.filter(employee__department_id=dept_id_int, log_time__gte=start_30d)
        else:
            log_qs = LogEntry.objects.filter(employee=emp, log_time__gte=start_30d)
        log_types = {}
        emotions = {}
        for log in log_qs:
            key = log.get_log_type_display()
            log_types[key] = log_types.get(key, 0) + 1
            emo = log.get_emotion_tag_display() if log.emotion_tag else '未标注'
            emotions[emo] = emotions.get(emo, 0) + 1

        dept_task_stats = {}
        if emp.department_id:
            base_dept_id = emp.department_id
            dept_qs = Task.objects.filter(assignee__department_id=base_dept_id, creation_time__gte=start_30d)
            dept_task_stats = {
                'completed': dept_qs.filter(status='COMPLETED').count(),
                'in_progress': dept_qs.filter(status='IN_PROGRESS').count(),
                'pending': dept_qs.filter(status='TO_DO').count(),
            }

        refresh = (request.GET.get('refresh') in ('1','true','True'))
        
        # 部门AI建议刷新权限检查：仅部门主管(3)、CEO(1)、管理员(2)可以刷新
        if refresh and scope == 'department':
            has_role = EmployeeRole.objects.filter(
                employee_id=emp.employee_id, 
                role_id__in=[1, 2, 3]
            ).exists()
            if not has_role:
                refresh = False
        
        advice = None
        if scope == 'department':
            dept_id_int = (emp.department_id or 0) if not is_admin else (int(dept_id) if dept_id and dept_id.isdigit() else (emp.department_id or 0))
            dprof = None
            if not refresh:
                dprof = AiDeptAnalysisProfile.objects.filter(department_id=dept_id_int).first()
                if dprof and dprof.ai_advice:
                    advice = dprof.ai_advice
            if not advice:
                prompt = (
                    '你是企业运营分析顾问。以下为近30天某部门的任务与日志统计，'
                    '请用中文给出部门层面的趋势解读、风险点与三条行动建议。'
                    '请务必返回纯JSON格式，不要包含Markdown标记。'
                    '格式：{"trend": "趋势(50字内)", "risk": "风险(50字内)", "actions": ["建议1", "建议2", "建议3"]}\n'
                    f"部门任务统计(30天)：{task_stats}.\n"
                    f"日志类型分布(30天)：{log_types}. 情绪分布：{emotions}."
                )
                advice = _call_ai(prompt)
                # 清理可能的Markdown标记
                if advice:
                    advice = advice.replace('```json', '').replace('```', '').strip()
                
                failed = (
                    (advice or '').startswith('AI建议生成失败')
                    or (advice or '').startswith('网络错误')
                    or (advice in ('AI服务未配置', '未配置 AI 密钥', 'AI服务未配置', 'AI建议生成失败'))
                )
                if failed:
                    # 保留旧缓存
                    if dprof and dprof.ai_advice:
                        advice = dprof.ai_advice
                        print(f"使用缓存的部门AI建议: {advice[:50]}...")
                    else:
                        # 提供友好的默认建议 (JSON格式)
                        advice = json.dumps({
                            "trend": f"任务总数{task_stats.get('recent_total',0)}，完成率需关注。",
                            "risk": "存在任务积压或沟通滞后风险。",
                            "actions": ["明确任务截止时间", "定期召开进度会", "关注员工情绪变化"]
                        }, ensure_ascii=False)
                        print(f"使用默认部门AI建议，长度: {len(advice)}")
                else:
                    print(f"AI调用成功，生成新部门建议，长度: {len(advice)}")
                
                # 只有非错误信息才保存到数据库
                if advice and not advice.startswith('AI建议生成失败') and not advice.startswith('网络错误') and advice not in ('AI服务未配置', 'AI服务未配置'):  # 确保有内容且不包含错误信息才保存
                    dobj, created = AiDeptAnalysisProfile.objects.get_or_create(department_id=dept_id_int)
                    dobj.ai_advice = advice
                    dobj.save()
                    print(f"部门AI建议已保存: department_id={dept_id_int}, created={created}, advice_length={len(advice)}")
                else:
                    print(f"跳过保存错误建议: {advice[:30]}...")
        else:
            prof = None
            if not refresh:
                prof = AiAnalysisProfile.objects.filter(employee=emp).first()
                if prof and prof.ai_advice:
                    advice = prof.ai_advice
            if not advice:
                prompt = (
                    '你是一个企业数据分析顾问。以下为近30天任务与日志统计，'
                    '请用中文给出简短的可执行建议。'
                    '请务必返回纯JSON格式，不要包含Markdown标记。'
                    '格式：{"trend": "趋势(50字内)", "risk": "风险(50字内)", "actions": ["建议1", "建议2", "建议3"]}\n'
                    f"个人任务统计(30天)：{task_stats}.\n"
                    f"日志类型分布(30天)：{log_types}. 情绪分布：{emotions}.\n"
                    f"部门任务统计(30天)：{dept_task_stats}"
                )
                advice = _call_ai(prompt)
                # 清理可能的Markdown标记
                if advice:
                    advice = advice.replace('```json', '').replace('```', '').strip()
                
                failed = (
                    (advice or '').startswith('AI建议生成失败')
                    or (advice or '').startswith('网络错误')
                    or (advice in ('AI服务未配置', '未配置 AI 密钥', 'AI服务未配置', 'AI建议生成失败'))
                )
                if failed:
                    if prof and prof.ai_advice:
                        advice = prof.ai_advice
                        print(f"使用缓存的个人AI建议: {advice[:50]}...")
                    else:
                        # 提供友好的默认建议 (JSON格式)
                        advice = json.dumps({
                            "trend": f"近30天参与任务{task_stats.get('recent_total',0)}个，整体表现稳定。",
                            "risk": "需注意任务优先级管理，避免积压。",
                            "actions": ["每日早晨规划今日待办", "大任务拆解为小步骤", "及时同步进度给主管"]
                        }, ensure_ascii=False)
                        print(f"使用默认个人AI建议，长度: {len(advice)}")
                else:
                    print(f"AI调用成功，生成新个人建议，长度: {len(advice)}")
                
                # 只有非错误信息才保存到数据库
                if advice and not advice.startswith('AI建议生成失败') and not advice.startswith('网络错误') and advice not in ('AI服务未配置', 'AI服务未配置'):  # 确保有内容且不包含错误信息才保存
                    obj, created = AiAnalysisProfile.objects.get_or_create(employee=emp)
                    obj.ai_advice = advice
                    obj.save()
                    print(f"个人AI建议已保存: employee_id={emp.employee_id}, created={created}, advice_length={len(advice)}")
                else:
                    print(f"跳过保存错误建议: {advice[:30]}...")

        # 调试信息：记录返回的AI建议
        print(f"返回AI建议: {advice[:100]}..." if advice else "返回AI建议: 空")
        
        return JsonResponse({
            'success': True,
            'data': {
                'task_stats': task_stats,
                'log_types': log_types,
                'emotions': emotions,
                'dept_task_stats': dept_task_stats,
                'ai_advice': advice,
                'scope': scope,
                'department_id': dept_id if is_admin else (emp.department_id or None),
                'ai_configured': _check_ai_config()[0],  # 添加AI配置状态
                'debug_advice_length': len(advice) if advice else 0,  # 调试信息
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def employee_analysis_api(request, employee_id: int):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        current = Employee.objects.get(work_id=request.session.get('current_employee_work_id'))
        target = Employee.objects.get(employee_id=employee_id)
        from pandora.utils import has_admin_or_ceo_access
        if not (has_admin_or_ceo_access(current) or (target.manager and target.manager.employee_id == current.employee_id)):
            return JsonResponse({'success': False, 'message': '无权查看'})
        prof = AiAnalysisProfile.objects.filter(employee=target).first()
        if not prof or not (prof.ai_advice or '').strip():
            generated = _generate_personal_profile(target)
            return JsonResponse({
                'success': True,
                'employee_id': employee_id,
                'exists': True,
                'ai_advice': generated['ai_advice'] or '',
                'mbti_type': prof.mbti_type if prof else '',
                'mbti_analysis': prof.mbti_analysis if prof else ''
            })
        return JsonResponse({
            'success': True,
            'employee_id': employee_id,
            'exists': True,
            'ai_advice': prof.ai_advice or '',
            'mbti_type': prof.mbti_type or '',
            'mbti_analysis': prof.mbti_analysis or ''
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
def mbti_analysis_api(request):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})

    work_id = request.session.get('current_employee_work_id')
    emp = Employee.objects.get(work_id=work_id)

    # GET 请求：尝试获取缓存
    if request.method == 'GET':
        mbti = (request.GET.get('mbti') or '').upper()
        if mbti:
            cache = AiMbtiCache.objects.filter(employee=emp, mbti_type=mbti).order_by('-created_at').first()
            if cache:
                 return JsonResponse({'success': True, 'mbti': mbti, 'advice': cache.content, 'cached': True})
            else:
                 return JsonResponse({'success': False, 'message': '无缓存'})
        return JsonResponse({'success': False, 'message': '缺少MBTI参数'})

    # POST 请求：生成新建议
    if request.method == 'POST':
        try:
            body = json.loads(request.body or '{}')
            mbti = (body.get('mbti') or '').upper()
            scope = (body.get('scope') or 'personal').lower()
            summary = (body.get('summary') or '').strip()

            if not mbti:
                return JsonResponse({'success': False, 'message': '请提供MBTI类型'})

            if not summary:
                tasks = Task.objects.filter(assignee=emp).order_by('-creation_time')[:10]
                logs = LogEntry.objects.filter(employee=emp).order_by('-log_time')[:5]
                task_briefs = [f"{t.task_name}-{t.status}" for t in tasks]
                log_briefs = [l.content[:80] for l in logs]
                summary = (
                    f"近期任务：{'; '.join(task_briefs)}。近期日志片段：{'; '.join(log_briefs)}。"
                )

            if scope == 'department' and emp.department_id:
                dept_qs = Task.objects.filter(assignee__department_id=emp.department_id)
                dept_stats = {
                    'completed': dept_qs.filter(status='COMPLETED').count(),
                    'in_progress': dept_qs.filter(status='IN_PROGRESS').count(),
                    'pending': dept_qs.filter(status='TO_DO').count(),
                }
            else:
                dept_stats = {}

            prompt = (
                '你是资深职业发展与团队协作顾问。'
                f"已知MBTI类型：{mbti}。"
                f"工作内容概述：{summary}。"
                f"部门任务概况：{dept_stats}。"
                '请用中文给出4-6条建议，涵盖：优势发挥、潜在盲区、沟通协作、时间管理与优先级。'
                '每条建议尽量具体、可执行。'
            )
            advice = _call_ai(prompt)

            try:
                # 保存到历史缓存
                if advice and not advice.startswith('AI建议生成失败'):
                    AiMbtiCache.objects.create(employee=emp, mbti_type=mbti, content=advice)

                # 更新当前Profile
                emp_profile, _ = AiAnalysisProfile.objects.get_or_create(employee=emp)
                emp_profile.mbti_type = mbti
                emp_profile.mbti_analysis = advice or ''
                emp_profile.save()
            except Exception as e:
                print(f"保存MBTI建议失败: {e}")

            return JsonResponse({'success': True, 'mbti': mbti, 'scope': scope, 'advice': advice})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': '不支持的方法'})


@require_GET
def mbti_detect_api(request):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        work_id = request.session.get('current_employee_work_id')
        emp = Employee.objects.get(work_id=work_id)
        logs = LogEntry.objects.filter(employee=emp, log_time__gte=timezone.now()-timedelta(days=30)).order_by('-log_time')[:20]
        tasks = Task.objects.filter(assignee=emp, creation_time__gte=timezone.now()-timedelta(days=30)).order_by('-creation_time')[:20]
        log_briefs = [f"[{l.get_log_type_display()}]{(l.content or '')[:80]}" for l in logs]
        task_briefs = [f"{t.task_name}-{t.status}" for t in tasks]
        prompt = (
            '你是资深MBTI人格分析师。根据以下员工近期任务与日志内容，推断其MBTI类型。'
            '只在16种类型中选择一个：INTJ, INTP, ENTJ, ENTP, INFJ, INFP, ENFJ, ENFP, ISTJ, ISFJ, ESTJ, ESFJ, ISTP, ISFP, ESTP, ESFP。'
            '请先给出类型，再给出简短理由与职场建议。'
            '输出格式示例：类型：INTJ\n理由：...\n建议：1)... 2)... 3)...\n'
            f"任务概述：{'；'.join(task_briefs)}。"
            f"日志片段：{'；'.join(log_briefs)}。"
        )
        refresh = (request.GET.get('refresh') in ('1','true','True'))
        analysis = None
        mbti_type = None
        if not refresh:
            prof = AiAnalysisProfile.objects.filter(employee=emp).first()
            if prof and prof.mbti_analysis:
                analysis = prof.mbti_analysis
                mbti_type = prof.mbti_type
        if not analysis:
            analysis = _call_ai(prompt)
        import re
        m = re.search(r"\b(?:INTJ|INTP|ENTJ|ENTP|INFJ|INFP|ENFJ|ENFP|ISTJ|ISFJ|ESTJ|ESFJ|ISTP|ISFP|ESTP|ESFP)\b", analysis or '')
        if m:
            mbti_type = m.group(0)
        failed = (
            (analysis or '').startswith('AI建议生成失败')
            or (analysis or '').startswith('网络错误')
            or (analysis in ('AI服务未配置', '未配置 AI 密钥', 'AI服务未配置', 'AI建议生成失败'))
        )
        if failed:
            prof2 = AiAnalysisProfile.objects.filter(employee=emp).first()
            if prof2 and prof2.mbti_analysis:
                analysis = prof2.mbti_analysis
                mbti_type = prof2.mbti_type
        else:
            obj, _ = AiAnalysisProfile.objects.get_or_create(employee=emp)
            obj.mbti_type = mbti_type or ''
            obj.mbti_analysis = analysis or ''
            obj.save()
        return JsonResponse({'success': True, 'type': mbti_type, 'analysis': analysis})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@require_GET
def departments_api(request):
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})
    try:
        work_id = request.session.get('current_employee_work_id')
        emp = Employee.objects.get(work_id=work_id)
        from pandora.utils import has_admin_or_ceo_access
        if has_admin_or_ceo_access(emp):
            depts = Department.objects.all().order_by('department_name')
        else:
            depts = Department.objects.filter(department_id=emp.department_id) if emp.department_id else Department.objects.none()
        data = [{'department_id': d.department_id, 'department_name': d.department_name} for d in depts]
        return JsonResponse({'success': True, 'departments': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


import os
import uuid
from django.conf import settings

# ... (other imports)

def _save_report_as_file(content, employee):
    """保存周报为 Markdown 文件"""
    try:
        report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        filename = f"weekly_report_{employee.work_id}_{timezone.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}.md"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # 构造访问 URL (假设 request.build_absolute_uri 在 view 中处理，这里只返回相对路径)
        # 注意：这里需要配合 MEDIA_URL
        return filename
    except Exception as e:
        print(f"Failed to save report file: {e}")
        return None

@csrf_exempt
@require_POST
def weekly_report_api(request):
    """生成智能周报API
    支持参数(JSON body):
    - action: 'generate' (默认) | 'push'
    - content: 可选。如果action='push'且提供了content，则直接推送该内容；否则生成新周报。
    """
    if not request.session.get('current_employee_work_id'):
        return JsonResponse({'success': False, 'message': '未登录'})

    try:
        body = json.loads(request.body or '{}')
        action = body.get('action', 'generate')
        content = body.get('content')

        work_id = request.session.get('current_employee_work_id')
        emp = Employee.objects.get(work_id=work_id)
        
        # 如果没有提供内容，或者显式要求生成，则执行生成逻辑
        # 但如果action='push'且没有content，也需要生成
        if not content:
            # 获取本周数据（近7天）
            now = timezone.now()
            start_date = now - timedelta(days=7)
            
            # 1. 已完成任务
            completed_tasks = Task.objects.filter(
                assignee=emp,
                status='COMPLETED',
                completion_time__gte=start_date
            )
            
            # 2. 进行中任务（作为下周计划参考）
            ongoing_tasks = Task.objects.filter(
                assignee=emp,
                status='IN_PROGRESS'
            )
            
            # 3. 工作日志
            logs = LogEntry.objects.filter(
                employee=emp,
                log_time__gte=start_date
            ).order_by('log_time')
            
            # 构造Prompt数据
            completed_str = "; ".join([f"{t.task_name}({t.completion_time.strftime('%m-%d')})" for t in completed_tasks]) or "无"
            ongoing_str = "; ".join([f"{t.task_name}(截止:{t.due_time.strftime('%m-%d') if t.due_time else '待定'})" for t in ongoing_tasks]) or "无"
            logs_str = "; ".join([f"[{l.log_time.strftime('%m-%d')}]{l.content[:50]}" for l in logs]) or "无"
            
            prompt = (
                "你是专业的职场助手。请根据以下员工本周（近7天）的工作数据，生成一份结构清晰、语气专业的周报。\n"
                "周报结构要求：\n"
                "1. **本周工作总结**：基于已完成任务和日志，概括主要产出。\n"
                "2. **工作成效与亮点**：提取关键成果，适当润色。\n"
                "3. **下周工作计划**：基于进行中任务和未完成事项规划。\n"
                "4. **问题与风险**：如果有逾期或困难，请委婉提出；如果没有，可省略。\n\n"
                f"【数据输入】\n"
                f"- 已完成任务：{completed_str}\n"
                f"- 进行中任务：{ongoing_str}\n"
                f"- 工作日志片段：{logs_str}\n\n"
                "请直接输出周报内容，不需要JSON格式，使用Markdown格式以便阅读。"
            )
            
            content = _call_ai(prompt)
        
        if action == 'push':
            # 保存为文件
            filename = _save_report_as_file(content, emp)
            if filename:
                # 生成在线预览链接
                view_url = reverse('weekly_report_detail', args=[filename])
                full_url = request.build_absolute_uri(view_url)
            else:
                full_url = None
            
            # 仅推送简短提示和链接，不推送全文
            short_msg = f"**{emp.employee_name}** 的本周智能周报已生成。\n\n请点击下方链接查看在线预览（支持下载）。"
            send_message(emp, "智能周报", short_msg, url=full_url)
            
            return JsonResponse({
                'success': True, 
                'message': '周报已推送到IM（包含文档链接）', 
                'report': content
            })
        
        return JsonResponse({
            'success': True,
            'report': content
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
