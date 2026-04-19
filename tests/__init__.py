"""Test package bootstrap for Pandora project."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pandora.settings")

try:  # pragma: no cover - defensive bootstrap
    import django

    django.setup()
except Exception:
    # Allow tests to continue even when Django isn't fully configured during collection.
    pass

