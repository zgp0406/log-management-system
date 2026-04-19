from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Callable

import pytest
from django.test import RequestFactory
from django.utils import timezone


@pytest.fixture
def rf() -> RequestFactory:
    return RequestFactory()


@pytest.fixture
def attach_session() -> Callable:
    def _attach(request):
        # Use a lightweight dictionary-backed session to avoid hitting the real
        # session store (which requires a database connection in this project).
        request.session = {}
        return request

    return _attach


@pytest.fixture
def sample_employee() -> SimpleNamespace:
    return SimpleNamespace(
        employee_id=1,
        employee_name="Alice",
        work_id="E001",
        password="secret",
        status="ACTIVE",
        manager=None,
    )


@pytest.fixture
def fixed_now(monkeypatch) -> datetime:
    aware_now = timezone.make_aware(datetime(2024, 1, 20, 10, 30))
    monkeypatch.setattr(
        "pandora.models.timezone",
        SimpleNamespace(now=lambda: aware_now, make_aware=timezone.make_aware),
    )
    return aware_now

