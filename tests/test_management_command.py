from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from django.utils import timezone

from pandora.models import Task, TaskNotificationMessage
from task_app.management.commands.check_task_due_dates import Command
from tests.helpers import QuerySetStub


def test_check_task_due_dates_creates_notifications(monkeypatch):
    aware_now = timezone.make_aware(datetime(2024, 1, 6, 10, 0))

    import task_app.management.commands.check_task_due_dates as command_module

    monkeypatch.setattr(command_module.timezone, "now", lambda: aware_now)

    due_task = SimpleNamespace(
        task_name="Due Tomorrow",
        assignee=SimpleNamespace(employee_name="Bob"),
    )
    overdue_task = SimpleNamespace(
        task_name="Overdue",
        assignee=SimpleNamespace(employee_name="Carol"),
    )

    class TaskManagerStub:
        def filter(self, **kwargs):
            if "due_time__date" in kwargs:
                return QuerySetStub([due_task])
            if "due_time__lt" in kwargs:
                return QuerySetStub([overdue_task])
            return QuerySetStub([])

    monkeypatch.setattr(Task, "objects", TaskManagerStub())

    notifications: list[dict] = []

    monkeypatch.setattr(
        TaskNotificationMessage,
        "objects",
        SimpleNamespace(
            filter=lambda **kwargs: QuerySetStub([]),
            create=lambda **kwargs: notifications.append(kwargs),
        ),
    )

    cmd = Command()
    cmd.handle()

    assert len(notifications) == 2
    messages = {note["message"] for note in notifications}
    assert any("距离截止日期还有1天" in msg for msg in messages)
    assert any("已逾期" in msg for msg in messages)

