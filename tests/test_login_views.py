from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from django.http import JsonResponse

from login_app import views as login_views
from pandora.models import Employee


def _setup_manager(employee: SimpleNamespace | None = None, *, raises: bool = False):
    if raises:
        def _get(**kwargs):
            raise Employee.DoesNotExist()
    else:
        def _get(**kwargs):
            return employee

    return SimpleNamespace(get=_get)


def test_employee_login_success(rf, attach_session, sample_employee, monkeypatch):
    monkeypatch.setattr(Employee, "objects", _setup_manager(sample_employee))

    request = attach_session(rf.post("/login/", {"work_id": sample_employee.work_id, "password": sample_employee.password}))
    response = login_views.employee_login(request)

    assert isinstance(response, JsonResponse)
    payload = json.loads(response.content)
    assert payload["success"] is True
    assert request.session["current_employee_work_id"] == sample_employee.work_id
    assert request.session["current_employee_name"] == sample_employee.employee_name
    assert request.session["current_employee_id"] == sample_employee.employee_id


def test_employee_login_wrong_password(rf, attach_session, sample_employee, monkeypatch):
    monkeypatch.setattr(Employee, "objects", _setup_manager(sample_employee))

    request = attach_session(rf.post("/login/", {"work_id": sample_employee.work_id, "password": "wrong"}))
    response = login_views.employee_login(request)

    assert json.loads(response.content) == {"success": False, "message": "密码错误"}


def test_employee_login_unknown_user(rf, attach_session, monkeypatch):
    monkeypatch.setattr(Employee, "objects", _setup_manager(raises=True))

    request = attach_session(rf.post("/login/", {"work_id": "E999", "password": "irrelevant"}))
    response = login_views.employee_login(request)

    assert json.loads(response.content) == {"success": False, "message": "工号不存在"}


def test_employee_login_missing_fields(rf):
    request = rf.post("/login/", {})
    response = login_views.employee_login(request)
    assert json.loads(response.content) == {"success": False, "message": "请输入工号和密码"}

