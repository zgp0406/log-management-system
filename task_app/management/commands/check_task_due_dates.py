"""
管理命令：检查任务截止日期并发送提醒
使用方法：python manage.py check_task_due_dates
可以配置为定时任务（cron）每天执行
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from pandora.models import Task, TaskNotificationMessage, Employee
from pandora.message_service import send_message


class Command(BaseCommand):
    help = '检查任务截止日期并发送即将到期和逾期提醒'

    def handle(self, *args, **options):
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        # 检查即将在明天到期的任务（距离截止日期还有1天）
        tasks_due_soon = Task.objects.filter(
            due_time__date=tomorrow,
            status__in=['TO_DO', 'IN_PROGRESS'],
            assignee__isnull=False
        )
        
        for task in tasks_due_soon:
            # 检查是否已经发送过提醒（避免重复发送）
            existing_notification = TaskNotificationMessage.objects.filter(
                employee=task.assignee,
                task=task,
                notification_type='DUE_SOON',
                created_time__date=today
            ).first()
            
            if not existing_notification:
                msg = f'任务"{task.task_name}"距离截止日期还有1天，请及时处理'
                TaskNotificationMessage.objects.create(
                    employee=task.assignee,
                    task=task,
                    notification_type='DUE_SOON',
                    message=msg,
                )
                
                # 发送IM通知
                send_message(task.assignee, '任务即将到期', msg)
                
                self.stdout.write(
                    self.style.SUCCESS(f'已发送即将到期提醒：{task.task_name} - {task.assignee.employee_name}')
                )
        
        # 检查已逾期的任务
        tasks_overdue = Task.objects.filter(
            due_time__lt=timezone.now(),
            status__in=['TO_DO', 'IN_PROGRESS'],
            assignee__isnull=False
        )
        
        for task in tasks_overdue:
            # 检查今天是否已经发送过逾期提醒（每天只发送一次）
            existing_notification = TaskNotificationMessage.objects.filter(
                employee=task.assignee,
                task=task,
                notification_type='OVERDUE',
                created_time__date=today
            ).first()
            
            if not existing_notification:
                msg = f'任务"{task.task_name}"已逾期，请尽快处理'
                TaskNotificationMessage.objects.create(
                    employee=task.assignee,
                    task=task,
                    notification_type='OVERDUE',
                    message=msg,
                )
                
                # 发送IM通知
                send_message(task.assignee, '任务已逾期', msg)
                
                self.stdout.write(
                    self.style.WARNING(f'已发送逾期提醒：{task.task_name} - {task.assignee.employee_name}')
                )
        
        self.stdout.write(self.style.SUCCESS('任务截止日期检查完成'))

