"""Облік витрат і ліміти (fabrica/ledger.py) — тимчасова SQLite, без мережі. Кожна знахідка рев'ю PR #11 має тест."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fabrica import config
from fabrica.ledger import AutomationDisabled, BudgetExceeded, BudgetNotConfigured, Ledger, Limits

pytestmark = pytest.mark.usefixtures("automation_on")   # платний шлях — явно

UTC = timezone.utc
T0 = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "out" / "fabrica.sqlite"


@pytest.fixture
def ledger(db: Path) -> Ledger:
    lg = Ledger(db, Limits.of(per_episode=150, daily=60, monthly=500))
    yield lg
    lg.close()


def rec(lg: Ledger, amount: float, part: int = 1, when: datetime = T0, **kw) -> bool:
    return lg.record("la-garganta", part, "video", "seedance", 10, "second", amount, when=when, **kw)


# ------------------------------------------------------------ облік і ліміти


def test_record_and_spent(ledger: Ledger) -> None:
    rec(ledger, 4.6, input_hash="h1")
    rec(ledger, 1.1, part=2, when=T0 + timedelta(days=1))
    assert ledger.spent("la-garganta", 1) == 4.6
    assert ledger.spent(day="2026-10-06") == 4.6
    assert ledger.spent(month="2026-10") == pytest.approx(5.7)
    assert ledger.already_paid("h1") and not ledger.already_paid("nope") and not ledger.already_paid("")


def test_warning_from_80_percent(ledger: Ledger) -> None:
    rec(ledger, 40)
    warnings = ledger.check("la-garganta", 1, 10, when=T0)          # день: 50 з 60 = 83,3 %
    assert len(warnings) == 1 and "день 2026-10-06" in warnings[0] and "83.3%" in warnings[0]


def test_exactly_100_percent_allowed_over_is_stop(ledger: Ledger) -> None:
    for _ in range(9):
        rec(ledger, 0.23, part=2)
    ledger.check("la-garganta", 1, 60 - 9 * 0.23, when=T0)         # рівно 60,00 — можна
    with pytest.raises(BudgetExceeded, match=r"день 2026-10-06 \(UTC\): \$60.00 з \$60.00"):
        ledger.check("la-garganta", 1, 60 - 9 * 0.23 + 0.000001, when=T0)


def test_force_and_new_day(ledger: Ledger) -> None:
    rec(ledger, 55)
    with pytest.raises(BudgetExceeded):
        ledger.check("la-garganta", 1, 10, when=T0)
    assert "ПЕРЕВИЩЕНО" in ledger.check("la-garganta", 1, 10, when=T0, force=True)[-1]
    assert ledger.check("la-garganta", 1, 10, when=T0 + timedelta(days=1)) == []


def test_episode_limit_spans_days(ledger: Ledger) -> None:
    for d in range(3):
        rec(ledger, 50, when=T0 + timedelta(days=d))
    with pytest.raises(BudgetExceeded, match="серія la-garganta ч.1"):
        ledger.check("la-garganta", 1, 1, when=T0 + timedelta(days=5))
    assert ledger.check("la-garganta", 2, 1, when=T0 + timedelta(days=5)) == []


def test_month_boundary_is_utc_and_tz_independent(db: Path) -> None:
    lg = Ledger(db, Limits.of(per_episode=None, daily=None, monthly=10))
    kyiv = timezone(timedelta(hours=3))
    rec(lg, 9, when=datetime(2026, 11, 1, 1, 30, tzinfo=kyiv))       # = 31.10 22:30 UTC → жовтень
    assert lg.spent(month="2026-10") == 9 and lg.spent(month="2026-11") == 0
    with pytest.raises(BudgetExceeded):
        lg.check("la-garganta", 1, 2, when=datetime(2026, 10, 31, 23, 0, tzinfo=UTC))
    assert lg.check("la-garganta", 1, 2, when=datetime(2026, 11, 1, 0, 0, tzinfo=UTC)) == []
    lg.close()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -10, -0.01])
def test_amounts_must_be_finite_and_non_negative(ledger: Ledger, bad: float) -> None:
    with pytest.raises(ValueError):
        ledger.check("la-garganta", 1, bad, when=T0)
    with pytest.raises(ValueError):
        rec(ledger, bad)
    with pytest.raises(ValueError):
        ledger.reserve("la-garganta", 1, "video", "seedance", estimate_usd=bad, units=1, unit="second")


# ------------------------------------------------------------ резервування


def test_reserve_counts_against_limit(ledger: Ledger) -> None:
    """Блокер рев'ю: check + record не атомарні. Тепер друга спроба бачить перший резерв."""
    ledger.reserve("la-garganta", 1, "video", "seedance", estimate_usd=40, units=1, unit="second", when=T0)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("la-garganta", 1, "video", "seedance", estimate_usd=40, units=1, unit="second", when=T0)
    assert ledger.spent(day="2026-10-06") == 40


def test_parallel_processes_cannot_overspend(db: Path) -> None:
    """10 з'єднань (як 10 процесів) по $10 при ліміті $50 — пройдуть рівно 5."""
    Ledger(db, Limits.of(per_episode=50, daily=None, monthly=None)).close()
    ok, refused, lock = [], [], threading.Lock()

    def worker() -> None:
        lg = Ledger(db, Limits.of(per_episode=50, daily=None, monthly=None))
        try:
            lg.reserve("la-garganta", 1, "video", "seedance", estimate_usd=10, units=1, unit="second")
            with lock:
                ok.append(1)
        except BudgetExceeded:
            with lock:
                refused.append(1)
        finally:
            lg.close()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ok) == 5 and len(refused) == 5


def test_charge_settles_actual_and_request_id(ledger: Ledger) -> None:
    with ledger.charge("la-garganta", 1, "video", "seedance", estimate_usd=2.3, units=10, unit="second") as c:
        c.actual_usd, c.request_id = 2.1, "job-1"
    assert ledger.spent("la-garganta", 1) == 2.1 and ledger.unsettled() == []
    assert not ledger.record("la-garganta", 1, "video", "seedance", 10, "second", 2.1, request_id="job-1")


def test_crash_mid_call_keeps_reservation(ledger: Ledger) -> None:
    """Процес упав після платного виклику — гроші могли списатись, тож резерв лишається витратою."""
    with pytest.raises(KeyboardInterrupt):
        with ledger.charge("la-garganta", 1, "video", "seedance", estimate_usd=2.3, units=10, unit="second"):
            raise KeyboardInterrupt
    assert ledger.spent("la-garganta", 1) == 2.3 and len(ledger.unsettled()) == 1


def test_not_charged_releases(ledger: Ledger) -> None:
    with pytest.raises(ConnectionError):
        with ledger.charge("la-garganta", 1, "video", "seedance", estimate_usd=2.3, units=10, unit="second") as c:
            c.not_charged = True
            raise ConnectionError("провайдер недоступний — запит не пішов")
    assert ledger.spent("la-garganta", 1) == 0 and ledger.unsettled() == []


def test_forced_is_recorded(ledger: Ledger, db: Path) -> None:
    rec(ledger, 59)
    c = ledger.reserve("la-garganta", 1, "video", "seedance", estimate_usd=5, units=1, unit="second", force=True,
                       when=T0)
    assert any("ПЕРЕВИЩЕНО" in w for w in c.warnings)
    assert ledger.db.execute("SELECT forced FROM costs WHERE id = ?", (c.id,)).fetchone()[0] == 1


def test_record_is_idempotent(ledger: Ledger) -> None:
    assert rec(ledger, 2.3, request_id="r1") is True
    assert rec(ledger, 2.3, request_id="r1") is False      # повтор після збою — без дубля
    assert ledger.spent("la-garganta", 1) == 2.3


def test_reader_does_not_block_writer(db: Path) -> None:
    """WAL: відкрита читальна транзакція іншого процесу не блокує запис витрати."""
    lg = Ledger(db, Limits.of(per_episode=None, daily=None, monthly=None))
    reader = sqlite3.connect(db)
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM costs").fetchone()
    rec(lg, 1.0)
    reader.rollback()
    reader.close()
    assert lg.spent() == 1.0
    lg.close()


def test_migrates_v1_schema(db: Path) -> None:
    db.parent.mkdir(parents=True)
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE costs (id INTEGER PRIMARY KEY, at TEXT NOT NULL, day TEXT NOT NULL, story TEXT NOT NULL, "
                "part INTEGER NOT NULL, stage TEXT NOT NULL, provider TEXT NOT NULL, units REAL NOT NULL, "
                "unit TEXT NOT NULL, usd REAL NOT NULL, input_hash TEXT NOT NULL DEFAULT '')")
    old.execute("INSERT INTO costs VALUES (1, '2026-10-06T12:00:00+03:00', '2026-10-06', 'la-garganta', 1, 'video', "
                "'seedance', 10, 'second', 4.6, 'h1')")
    old.commit()
    old.close()
    lg = Ledger(db, Limits.of())
    assert lg.spent("la-garganta", 1) == 4.6 and lg.already_paid("h1")
    assert lg.db.execute("PRAGMA user_version").fetchone()[0] == 2
    lg.close()


# ------------------------------------------------------------ ліміти з .env


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in ("BUDGET_PER_EPISODE_USD", "BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    monkeypatch.setenv("FABRICA_ENV_FILE", str(path))
    return path


def test_limits_from_env_file(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env.write_text("﻿export BUDGET_PER_EPISODE_USD=200\nBUDGET_DAILY_USD=none  # свідомо\n"
                   "BUDGET_MONTHLY_USD='450,5'\nSEEDANCE_API_KEY=secret\n", encoding="utf-8")
    lim = Limits.from_env()
    assert (lim.per_episode, lim.daily, lim.monthly, lim.missing) == (200_000_000, None, 450_500_000, ())
    monkeypatch.setenv("BUDGET_DAILY_USD", "30")
    assert Limits.from_env().daily == 30_000_000


def test_missing_limits_block_paid_calls(env: Path, db: Path) -> None:
    env.write_text("BUDGET_PER_EPISODE_USD=200\n", encoding="utf-8")
    lg = Ledger(db)
    assert lg.limits.missing == ("BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD")
    with pytest.raises(BudgetNotConfigured, match="BUDGET_DAILY_USD"):
        lg.check("la-garganta", 1, 1)
    with pytest.raises(BudgetNotConfigured):
        lg.reserve("la-garganta", 1, "video", "seedance", estimate_usd=1, units=1, unit="second")
    assert lg.spent() == 0
    assert any("не задано" in w for w in lg.check("la-garganta", 1, 1, force=True))
    lg.close()


@pytest.mark.parametrize("line, match", [
    ("BUDGET_DAILY_USD=TODO", "BUDGET_DAILY_USD"),
    ("BUDGET_DAILY_USD=1,000", "BUDGET_DAILY_USD"),
    ("BUDGET_DAILY_USD=-5", "BUDGET_DAILY_USD"),
    ("BUDGET_DAILY_USD=nan", "BUDGET_DAILY_USD"),
    ("BUDGET_DAILY_USD=10 USD", "BUDGET_DAILY_USD"),
    ("BUDGET_DAYLY_USD=30", "Невідомий ключ"),
    ("budget_daily_usd=30", "Невідомий ключ"),
])
def test_bad_env_values_are_errors(env: Path, line: str, match: str) -> None:
    env.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match=match):
        Limits.from_env()


def test_utf16_env_is_clear_error(env: Path) -> None:
    env.write_text("BUDGET_DAILY_USD=30\n", encoding="utf-16")
    with pytest.raises(config.ConfigError, match="UTF-16"):
        Limits.from_env()


@pytest.mark.parametrize("value", [None, "false", "0", "ні"])
def test_lab_mode_blocks_paid_calls_by_default(ledger: Ledger, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                               value: str | None) -> None:
    """Режим лабораторії: без AUTOMATION_ENABLED=true жоден платний виклик не стартує, навіть з ключами й лімітами."""
    env = tmp_path / "lab.env"
    env.write_text("", encoding="utf-8")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(env))
    if value is None:
        monkeypatch.delenv("AUTOMATION_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AUTOMATION_ENABLED", value)
    with pytest.raises(AutomationDisabled, match="лабораторії"):
        ledger.reserve("la-garganta", 1, "video", "seedance", estimate_usd=1, units=1, unit="second")
    with pytest.raises(AutomationDisabled):
        with ledger.charge("la-garganta", 1, "voice", "elevenlabs", estimate_usd=0.1, units=10, unit="char"):
            pass
    assert ledger.spent() == 0
    rec(ledger, 1.0)                      # ручний факт (імпорт з рахунку) записувати можна
    assert ledger.spent() == 1.0
