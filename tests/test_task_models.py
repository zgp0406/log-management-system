from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.db import models as django_models

from pandora.models import Task
from tests.helpers import QuerySetStub


@pytest.mark.usefixtures("fixed_now")
def test_task_save_generates_incremental_code(monkeypatch):
    count_stub = QuerySetStub([object(), object()])

    class TaskManagerStub(SimpleNamespace):
        def filter(self, **kwargs):
            return count_stub

    monkeypatch.setattr(Task, "objects", TaskManagerStub())
    monkeypatch.setattr(django_models.Model, "save", lambda *args, **kwargs: None)

    task = Task(task_name="Demo", creator=None)
    task.save()

    assert task.task_code == "240120003"


@pytest.mark.usefixtures("fixed_now")
def test_task_save_keeps_existing_code(monkeypatch):
    class TaskManagerStub(SimpleNamespace):
        def filter(self, **kwargs):
            return QuerySetStub([])

    monkeypatch.setattr(Task, "objects", TaskManagerStub())
    monkeypatch.setattr(django_models.Model, "save", lambda *args, **kwargs: None)

    task = Task(task_name="Demo", task_code="manual-code", creator=None)
    task.save()

    assert task.task_code == "manual-code"

