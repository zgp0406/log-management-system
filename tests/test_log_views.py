from __future__ import annotations

import json
from types import SimpleNamespace

from django.http import JsonResponse

from log_app import views as log_views
from pandora.models import Employee, EntryTagLink, LogEntry


def test_log_update_rejects_without_permission(rf, attach_session, monkeypatch):
    log = SimpleNamespace(employee_id=2)
    current_employee = SimpleNamespace(employee_id=1)

    def fake_get_object(model, *args, **kwargs):
        if model is LogEntry:
            return log
        if model is Employee:
            return current_employee
        raise AssertionError("Unexpected model access")

    monkeypatch.setattr(log_views, "get_object_or_404", fake_get_object)
    monkeypatch.setattr(log_views, "has_admin_or_ceo_access", lambda employee: False)

    request = attach_session(rf.post("/logs/1/update/", {}))
    request.session["current_employee_id"] = 1

    response = log_views.log_update(request, log_id=1)
    assert isinstance(response, JsonResponse)
    payload = json.loads(response.content)
    assert payload["success"] is False
    assert payload["error"] == "无权编辑此日志"


def test_log_update_accepts_with_admin_permission(rf, attach_session, monkeypatch):
    log = SimpleNamespace(employee_id=1)
    current_employee = SimpleNamespace(employee_id=1)

    def fake_get_object(model, *args, **kwargs):
        if model is LogEntry:
            return log
        if model is Employee:
            return current_employee
        raise AssertionError("Unexpected model access")

    monkeypatch.setattr(log_views, "get_object_or_404", fake_get_object)
    monkeypatch.setattr(log_views, "has_admin_or_ceo_access", lambda employee: True)

    class FormStub:
        def __init__(self, data, instance=None):
            self.data = data
            self.instance = instance

        def is_valid(self):
            return True

        def save(self):
            return self.instance

    monkeypatch.setattr(log_views, "LogEntryForm", FormStub)
    monkeypatch.setattr(
        EntryTagLink,
        "objects",
        SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(delete=lambda: None)),
    )

    request = attach_session(rf.post("/logs/1/update/", {"content": "Updated"}))
    request.session["current_employee_id"] = 1

    response = log_views.log_update(request, log_id=1)
    payload = json.loads(response.content)
    assert payload["success"] is True

