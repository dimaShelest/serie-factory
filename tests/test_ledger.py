"""Облік витрат і ліміти (fabrica/ledger.py) — на тимчасовій SQLite, без мережі."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fabrica.ledger import BudgetExceeded, Ledger, Limits

KYIV = timezone(timedelta(hours=3))
T0 = datetime(2026, 10, 6, 12, 0, tzinfo=KYIV)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    lg = Ledger(tmp_path / "out" / "fabrica.sqlite", Limits(per_episode=150, daily=60, monthly=500))
    yield lg
    lg.close()


def test_record_and_spent(ledger: Ledger) -> None:
    ledger.record("la-garganta", 1, "video", "seedance", 10, "second", 4.6, "h1", when=T0)
    ledger.record("la-garganta", 2, "video", "seedance", 5, "second", 1.1, "h2", when=T0 + timedelta(days=1))
    assert ledger.spent("la-garganta", 1) == 4.6
    assert ledger.spent(day_prefix="2026-10-06") == 4.6
    assert ledger.spent(day_prefix="2026-10") == 5.7
    assert ledger.already_paid("h1") and not ledger.already_paid("nope") and not ledger.already_paid("")


def test_under_limits_no_warnings(ledger: Ledger) -> None:
    assert ledger.check("la-garganta", 1, 10, when=T0) == []


def test_warning_from_80_percent(ledger: Ledger) -> None:
    ledger.record("la-garganta", 1, "video", "seedance", 100, "second", 40, when=T0)
    warnings = ledger.check("la-garganta", 1, 10, when=T0)          # день: 50 з 60 = 83 %
    assert len(warnings) == 1 and "день 2026-10-06" in warnings[0] and "83%" in warnings[0]


def test_stop_over_limit_and_force(ledger: Ledger) -> None:
    ledger.record("la-garganta", 1, "video", "seedance", 100, "second", 55, when=T0)
    with pytest.raises(BudgetExceeded, match="день 2026-10-06: \\$65.00 з \\$60.00"):
        ledger.check("la-garganta", 1, 10, when=T0)
    assert "ПЕРЕВИЩЕНО" in ledger.check("la-garganta", 1, 10, when=T0, force=True)[-1]
    assert ledger.check("la-garganta", 1, 10, when=T0 + timedelta(days=1)) == []   # новий день


def test_episode_limit_spans_days(ledger: Ledger) -> None:
    for d in range(3):
        ledger.record("la-garganta", 1, "video", "seedance", 100, "second", 50, when=T0 + timedelta(days=d))
    with pytest.raises(BudgetExceeded, match="серія la-garganta ч.1"):
        ledger.check("la-garganta", 1, 1, when=T0 + timedelta(days=5))
    assert ledger.check("la-garganta", 2, 1, when=T0 + timedelta(days=5)) == []


def test_limits_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("BUDGET_PER_EPISODE_USD", "BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD"):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / ".env"
    env.write_text("﻿BUDGET_PER_EPISODE_USD=200\nBUDGET_DAILY_USD=\nBUDGET_MONTHLY_USD='450,5'\n"
                   "SEEDANCE_API_KEY=secret\n", encoding="utf-8")
    assert Limits.from_env(env) == Limits(200.0, None, 450.5)
    monkeypatch.setenv("BUDGET_DAILY_USD", "30")
    assert Limits.from_env(env).daily == 30.0
    env.write_text("BUDGET_DAILY_USD=TODO\n", encoding="utf-8")
    monkeypatch.delenv("BUDGET_DAILY_USD")
    with pytest.raises(ValueError, match="BUDGET_DAILY_USD"):
        Limits.from_env(env)


def test_no_limits_never_blocks(tmp_path: Path) -> None:
    lg = Ledger(tmp_path / "f.sqlite", Limits())
    lg.record("x", 1, "video", "seedance", 1, "second", 10_000)
    assert lg.check("x", 1, 10_000) == []
    lg.close()
