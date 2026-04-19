import json
import logging
import urllib.request
import urllib.error
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 使用线程池异步发送消息，避免阻塞主线程
executor = ThreadPoolExecutor(max_workers=2)

def send_message(employee, title, content, url=None):
    """
    统一发送消息入口
    :param employee: Employee对象，包含phone_number
    :param title: 消息标题
    :param content: 消息内容
    :param url: 相关链接（可选）
    """
    # 异步执行发送逻辑
    executor.submit(_send_message_sync, employee, title, content, url)

def _send_message_sync(employee, title, content, url=None):
    """
    同步发送消息逻辑
    """
    wecom_webhook = getattr(settings, 'WECOM_WEBHOOK_URL', '')
    dingtalk_webhook = getattr(settings, 'DINGTALK_WEBHOOK_URL', '')
    
    if not wecom_webhook and not dingtalk_webhook:
        return

    mobile = employee.phone_number if employee and employee.phone_number else None
    
    # 构造完整消息内容
    full_content = f"【Pandora任务通知】\n标题：{title}\n内容：{content}"
    if url:
        full_content += f"\n链接：{url}"

    if wecom_webhook:
        _send_wecom(wecom_webhook, full_content, mobile)
    
    if dingtalk_webhook:
        # 钉钉使用 markdown 格式以支持更好排版（如果 title 不为空）
        if title:
            _send_dingtalk_markdown(dingtalk_webhook, title, content, url, mobile)
        else:
            _send_dingtalk(dingtalk_webhook, title, full_content, mobile)

def send_announcement(title, content, url=None):
    """
    发送全员公告
    :param title: 公告标题
    :param content: 公告内容
    :param url: 相关链接
    """
    executor.submit(_send_announcement_sync, title, content, url)

def _send_announcement_sync(title, content, url=None):
    wecom_webhook = getattr(settings, 'WECOM_WEBHOOK_URL', '')
    dingtalk_webhook = getattr(settings, 'DINGTALK_WEBHOOK_URL', '')
    
    if not wecom_webhook and not dingtalk_webhook:
        return

    full_content = f"【系统公告】\n标题：{title}\n内容：{content}"
    if url:
        full_content += f"\n链接：{url}"

    if wecom_webhook:
        # 企业微信 @all
        _send_wecom(wecom_webhook, full_content, is_at_all=True)
    
    if dingtalk_webhook:
        # 钉钉 @all
        safe_title = f"【Pandora公告】{title}"
        md_text = f"### {safe_title}\n\n{content}"
        if url:
            md_text += f"\n\n[查看详情]({url})"
        md_text += "\n\n@all" # Markdown 中 @all 只是文本，实际触发需要 at 参数
        
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": safe_title,
                "text": md_text
            },
            "at": {
                "isAtAll": True
            }
        }
        try:
            _post_json(dingtalk_webhook, data)
        except Exception as e:
            logger.error(f"Failed to send DingTalk announcement: {e}")

def _send_wecom(webhook, content, mobile=None, is_at_all=False):
    """
    发送企业微信群机器人消息
    """
    data = {
        "msgtype": "text",
        "text": {
            "content": content,
        }
    }
    
    if is_at_all:
        data["text"]["mentioned_list"] = ["@all"]
    elif mobile:
        data["text"]["mentioned_mobile_list"] = [mobile]
        
    try:
        _post_json(webhook, data)
    except Exception as e:
        logger.error(f"Failed to send WeCom message: {e}")

def _send_dingtalk_markdown(webhook, title, content, url=None, mobile=None):
    """
    发送钉钉 Markdown 消息
    """
    # 构造 Markdown 内容，务必包含关键字 "Pandora" 以通过安全检查
    safe_title = f"【Pandora】{title}"
    md_text = f"### {safe_title}\n\n{content}"
    if url:
        md_text += f"\n\n[查看详情/下载文档]({url})"
        
    if mobile:
        md_text += f"\n\n@{mobile}"

    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": safe_title,
            "text": md_text
        },
        "at": {
            "isAtAll": False
        }
    }
    
    if mobile:
        data["at"]["atMobiles"] = [mobile]
        
    try:
        _post_json(webhook, data)
    except Exception as e:
        logger.error(f"Failed to send DingTalk Markdown message: {e}")

def _send_dingtalk(webhook, title, content, mobile=None):
    """
    发送钉钉群机器人消息
    文档：https://open.dingtalk.com/document/robots/custom-robot-access
    """
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        },
        "at": {
            "isAtAll": False
        }
    }
    
    if mobile:
        data["at"]["atMobiles"] = [mobile]
        
    try:
        _post_json(webhook, data)
    except Exception as e:
        logger.error(f"Failed to send DingTalk message: {e}")

def _post_json(url, data):
    headers = {'Content-Type': 'application/json'}
    json_data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=json_data, headers=headers)
    
    with urllib.request.urlopen(req, timeout=5) as resp:
        response = resp.read().decode('utf-8')
        # 简单检查响应
        return response
