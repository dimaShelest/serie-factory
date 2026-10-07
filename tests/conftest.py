"""Спільні фікстури тестів."""

from __future__ import annotations

import pytest


@pytest.fixture
def automation_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Платний шлях (Ledger.reserve / charge) у тестах: режим лабораторії за замовчуванням його вимикає."""
    monkeypatch.setenv("AUTOMATION_ENABLED", "true")
