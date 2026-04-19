from __future__ import annotations

from types import SimpleNamespace

import pytest

from pandora import utils
from pandora.models import EmployeeRole, Role


def test_check_role_returns_true(monkeypatch, sample_employee):
    role = SimpleNamespace(role_id=10)

    monkeypatch.setattr(Role, "objects", SimpleNamespace(get=lambda role_name: role))

    def fake_filter(**kwargs):
        assert kwargs["employee_id"] == sample_employee.employee_id
        assert kwargs["role_id"] == role.role_id
        return SimpleNamespace(exists=lambda: True)

    monkeypatch.setattr(EmployeeRole, "objects", SimpleNamespace(filter=fake_filter))

    assert utils.check_role(sample_employee, "管理员") is True


def test_check_role_handles_missing_role(monkeypatch, sample_employee):
    class _DoesNotExist(Exception):
        pass

    monkeypatch.setattr(Role, "DoesNotExist", _DoesNotExist)

    def fake_get(role_name):
        raise _DoesNotExist()

    monkeypatch.setattr(Role, "objects", SimpleNamespace(get=fake_get))

    assert utils.check_role(sample_employee, "不存在的角色") is False


@pytest.mark.parametrize(
    "is_admin,is_ceo,expected",
    [
        (True, False, True),
        (False, True, True),
        (True, True, True),
        (False, False, False),
    ],
)
def test_has_admin_or_ceo_access(monkeypatch, sample_employee, is_admin, is_ceo, expected):
    monkeypatch.setattr(utils, "check_admin_role", lambda employee: is_admin)
    monkeypatch.setattr(utils, "check_ceo_role", lambda employee: is_ceo)

    assert utils.has_admin_or_ceo_access(sample_employee) is expected

