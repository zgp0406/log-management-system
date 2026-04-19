from django.core.management.base import BaseCommand
from pandora.message_service import _send_dingtalk, _send_wecom

class Command(BaseCommand):
    help = 'Test IM notification push (DingTalk/WeCom)'

    def add_arguments(self, parser):
        parser.add_argument('platform', type=str, choices=['dingtalk', 'wecom'], help='Platform to test')
        parser.add_argument('webhook_url', type=str, help='Webhook URL')
        parser.add_argument('--mobile', type=str, help='Mobile number to mention', required=False)

    def handle(self, *args, **options):
        platform = options['platform']
        webhook_url = options['webhook_url']
        mobile = options['mobile']
        
        self.stdout.write(f"Testing {platform} push to {webhook_url}...")
        
        try:
            if platform == 'dingtalk':
                _send_dingtalk(webhook_url, "Test Title", "This is a test message from Pandora", mobile)
            elif platform == 'wecom':
                _send_wecom(webhook_url, "This is a test message from Pandora", mobile)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully sent test message to {platform}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to send message: {e}"))
