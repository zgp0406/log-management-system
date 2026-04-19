from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.http import JsonResponse
from django.utils import timezone

from pandora.models import Employee, LogEntry, SubTask, Task
from task_app import views as task_views
from tests.helpers import QuerySetStub


def test_calculate_task_progress(monkeypatch):
    subtasks = [
        SimpleNamespace(status="COMPLETED"),
        SimpleNamespace(status="IN_PROGRESS"),
        SimpleNamespace(status="COMPLETED"),
    ]
    monkeypatch.setattr(SubTask, "objects", SimpleNamespace(filter=lambda **kwargs: QuerySetStub(subtasks)))

    progress = task_views.calculate_task_progress(task_id=1)
    assert progress == 66


def test_calculate_task_progress_without_subtasks(monkeypatch):
    monkeypatch.setattr(SubTask, "objects", SimpleNamespace(filter=lambda **kwargs: QuerySetStub([])))
    assert task_views.calculate_task_progress(task_id=1) is None


def test_task_detail_returns_json(monkeypatch, rf):
    task = SimpleNamespace(
        task_code="240120001",
        task_name="Demo Task",
        description="Details",
        priority="HIGH",
        project_source="Project X",
        creator=SimpleNamespace(employee_name="Alice"),
        assignee=SimpleNamespace(employee_name="Bob"),
        start_time=timezone.now(),
        due_time=timezone.now(),
        estimated_duration=60,
        status="TO_DO",
    )

    def fake_get_object(model, **kwargs):
        return task

    monkeypatch.setattr(task_views, "get_object_or_404", fake_get_object)

    response = task_views.task_detail(rf.get("/tasks/1/"), task_id=1)
    assert isinstance(response, JsonResponse)
    payload = json.loads(response.content)
    assert payload["task_name"] == "Demo Task"
    assert payload["creator"] == "Alice"


class _TaskState:
    def __init__(self, status: str):
        self.status = status
        self.assignee_id = 1
        self.creator_id = 2
        self.start_time = None
        self.completion_time = None
        self.task_name = "Task Name"

    def save(self):
        return None


@pytest.mark.parametrize(
    ("initial_status", "expected_status", "log_called"),
    [
        ("TO_DO", "IN_PROGRESS", False),
        ("IN_PROGRESS", "COMPLETED", True),
    ],
)
def test_task_update_status(monkeypatch, rf, attach_session, initial_status, expected_status, log_called):
    task_state = _TaskState(initial_status)
    employee = SimpleNamespace(employee_id=1)

    def fake_get_object(model, *args, **kwargs):
        if model is Task:
            return task_state
        if model is Employee:
            return employee
        raise AssertionError("Unexpected model access")

    monkeypatch.setattr(task_views, "get_object_or_404", fake_get_object)

    captured = {}

    def fake_create(**kwargs):
        captured["called"] = True

    monkeypatch.setattr(LogEntry, "objects", SimpleNamespace(create=fake_create))
    request = attach_session(rf.post("/tasks/1/status/"))
    request.session["current_employee_id"] = 1

    response = task_views.task_update_status(request, task_id=1)
    assert json.loads(response.content)["success"] is True
    assert task_state.status == expected_status
    assert bool(captured.get("called")) is log_called
    if initial_status == "TO_DO":
        assert task_state.start_time is not None
        assert task_state.completion_time is None
    else:
        assert task_state.completion_time is not None

