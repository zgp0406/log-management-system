from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from django.http import JsonResponse
from django.utils import timezone

from dashboard import api_views as dashboard_api
from pandora.models import Employee, LogEntry, LogTag, Task
from tests.helpers import QuerySetStub


def test_dashboard_api_success(rf, attach_session, sample_employee, monkeypatch):
    aware_now = timezone.make_aware(datetime(2024, 1, 5, 9, 0))
    monkeypatch.setattr(dashboard_api.timezone, "now", lambda: aware_now)

    class _DateTimeStub:
        @staticmethod
        def now():
            return datetime(2024, 1, 5, 9, 0)

        @staticmethod
        def weekday():
            return 4

    monkeypatch.setattr(dashboard_api, "datetime", _DateTimeStub)

    current_employee = sample_employee

    monkeypatch.setattr(dashboard_api, "check_admin_role", lambda employee: False)
    monkeypatch.setattr(dashboard_api, "has_admin_or_ceo_access", lambda employee: False)
    completed_task = SimpleNamespace(
        task_id=1,
        task_name="Completed",
        description="",
        priority="HIGH",
        status="COMPLETED",
        assignee=current_employee,
        creation_time=aware_now,
        due_time=aware_now,
    )
    in_progress_task = SimpleNamespace(
        task_id=2,
        task_name="In progress",
        description="",
        priority="MEDIUM",
        status="IN_PROGRESS",
        assignee=current_employee,
        creation_time=aware_now,
        due_time=None,
    )
    todo_task = SimpleNamespace(
        task_id=3,
        task_name="Pending",
        description="",
        priority="LOW",
        status="TO_DO",
        assignee=current_employee,
        creation_time=aware_now,
        due_time=None,
    )
    all_tasks = [completed_task, in_progress_task, todo_task]

    class TaskManagerStub:
        def filter(self, **kwargs):
            return QuerySetStub(all_tasks).filter(**kwargs)

        def all(self):
            return QuerySetStub(all_tasks)

        def select_related(self, *args, **kwargs):
            return QuerySetStub(all_tasks)

    monkeypatch.setattr(Task, "objects", TaskManagerStub())
    monkeypatch.setattr(Employee, "objects", SimpleNamespace(get=lambda **kwargs: current_employee))

    log = SimpleNamespace(
        log_id=10,
        employee=current_employee,
        log_time=aware_now,
        content="Finished work",
        log_type="WORK",
        emotion_tag="ACTIVE",
        get_log_type_display=lambda: "工作",
        get_emotion_tag_display=lambda: "积极",
    )

    monkeypatch.setattr(
        LogEntry,
        "objects",
        SimpleNamespace(filter=lambda **kwargs: QuerySetStub([log])),
    )
    monkeypatch.setattr(
        LogTag,
        "objects",
        SimpleNamespace(filter=lambda **kwargs: QuerySetStub([SimpleNamespace(tag_name="效率")])),
    )

    request = attach_session(rf.get("/dashboard/api/"))
    request.session["current_employee_work_id"] = current_employee.work_id
    request.session["current_employee_name"] = current_employee.employee_name
    request.session["current_employee_id"] = current_employee.employee_id
    request.session["company_top_tasks"] = [1, 2]

    response = dashboard_api.dashboard_api(request)
    assert isinstance(response, JsonResponse)
    payload = json.loads(response.content)
    assert payload["success"] is True
    data = payload["data"]
    assert data["task_stats"]["completed"] == 1
    assert data["task_stats"]["in_progress"] == 1
    assert data["task_stats"]["pending"] == 1
    assert data["company_tasks"][0]["task_name"] == "Completed"
    assert data["personal_logs"][0]["content"] == "Finished work"

