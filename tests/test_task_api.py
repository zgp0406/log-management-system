from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from django.http import JsonResponse

from pandora.models import LogEntry, SubTask, Task, TaskNotificationMessage
from task_app import api_views
from tests.helpers import QuerySetStub


class _TaskStub:
    def __init__(self, *, status: str, assignee_id: int = 1, task_id: int = 1):
        self.status = status
        self.assignee_id = assignee_id
        self.task_id = task_id
        self.start_time = None
        self.completion_time = None
        self.task_name = "Test Task"
        self.creator_id = 2
        self.assignee = SimpleNamespace(employee_name="Worker")

    def save(self):
        return None


def _request_with_session(rf, attach_session, method: str, url: str, data=None):
    request = getattr(rf, method)(url, data or {})
    attach_session(request)
    return request


def test_task_take_api_success(rf, attach_session, monkeypatch):
    task = _TaskStub(status="TO_DO")
    monkeypatch.setattr(Task, "objects", SimpleNamespace(get=lambda pk: task))
    fixed_now = datetime(2024, 1, 1, 8, 0)
    monkeypatch.setattr(api_views.timezone, "now", lambda: fixed_now)

    request = _request_with_session(rf, attach_session, "post", "/tasks/1/take/")
    request.session["current_employee_id"] = 1

    response = api_views.task_take_api(request, task_id=1)
    assert isinstance(response, JsonResponse)
    assert json.loads(response.content)["success"] is True
    assert task.status == "IN_PROGRESS"
    assert task.start_time == fixed_now


def test_task_take_api_wrong_user(rf, attach_session, monkeypatch):
    task = _TaskStub(status="TO_DO", assignee_id=2)
    monkeypatch.setattr(Task, "objects", SimpleNamespace(get=lambda pk: task))

    request = _request_with_session(rf, attach_session, "post", "/tasks/1/take/")
    request.session["current_employee_id"] = 1

    response = api_views.task_take_api(request, task_id=1)
    assert json.loads(response.content)["success"] is False
    assert task.status == "TO_DO"


def test_task_complete_api_sets_status_and_logs(rf, attach_session, monkeypatch):
    task = _TaskStub(status="IN_PROGRESS", assignee_id=1)
    subtasks = [
        SimpleNamespace(
            status="IN_PROGRESS",
            subtask_name="Sub 1",
            completion_time=None,
            save=lambda: None,
        )
    ]

    monkeypatch.setattr(Task, "objects", SimpleNamespace(get=lambda pk: task))
    monkeypatch.setattr(LogEntry, "objects", SimpleNamespace(create=lambda **kwargs: None))
    monkeypatch.setattr(
        SubTask,
        "objects",
        SimpleNamespace(filter=lambda **kwargs: QuerySetStub(subtasks)),
    )

    created_notifications = []

    def fake_create_notification(**kwargs):
        created_notifications.append(kwargs)

    monkeypatch.setattr(TaskNotificationMessage, "objects", SimpleNamespace(create=fake_create_notification, filter=lambda **kwargs: QuerySetStub([])))
    fixed_now = datetime(2024, 1, 2, 9, 0)
    monkeypatch.setattr(api_views.timezone, "now", lambda: fixed_now)

    request = _request_with_session(rf, attach_session, "post", "/tasks/1/complete/")
    request.session["current_employee_id"] = 1

    response = api_views.task_complete_api(request, task_id=1)
    assert json.loads(response.content)["success"] is True
    assert task.status == "COMPLETED"
    assert task.completion_time == fixed_now
    assert created_notifications, "Task completion should create a notification for creator"

