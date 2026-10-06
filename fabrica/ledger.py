"""Облік витрат і ліміти бюджету (Issue #3, docs/ARCHITECTURE.md → «Наскрізне: облік витрат»).

Кожен платний виклик іде через одну обгортку — атомарне резервування, тож паралельні процеси не перевищать ліміт:

    with ledger.charge("la-garganta", 1, "video", "seedance", estimate_usd=2.30, units=10, unit="second") as c:
        job = seedance.generate(...)          # платний виклик
        c.request_id = job.id                 # id задачі провайдера — для звірки з рахунком
        c.actual_usd = job.cost               # факт (якщо невідомий — лишається оцінка)

- Перед викликом: резерв на оцінку в одній транзакції з перевіркою лімітів (BEGIN IMMEDIATE).
  ≥ 80 % ліміту — попередження, понад 100 % — BudgetExceeded. Рівно 100 % — ще можна.
- Виклик упав → резерв лишається («незвірений») і рахується як витрачений: провайдер міг списати гроші.
  Якщо точно знаєш, що не списав (помилка до відправки), постав `c.not_charged = True` — резерв знімається.
- Ліміти — BUDGET_PER_EPISODE_USD / BUDGET_DAILY_USD / BUDGET_MONTHLY_USD (оточення або `.env`).
  **Не задано → платні виклики заборонені** (BudgetNotConfigured). Без ліміту — лише явно: `none`.
- Гроші — цілі мікродолари (1 USD = 1 000 000), межі дня й місяця — за UTC.
- Журнал локальний для машини (output/fabrica.sqlite): платні виклики робимо лише з однієї машини (Mac A).
- Один Ledger — на один потік.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fabrica import config

DB_PATH = config.ROOT / "output" / "fabrica.sqlite"
WARN_SHARE = 0.8
MICROS = 1_000_000
SCHEMA_VERSION = 2
LIMIT_KEYS = {"BUDGET_PER_EPISODE_USD": "per_episode", "BUDGET_DAILY_USD": "daily",
              "BUDGET_MONTHLY_USD": "monthly"}
UNLIMITED = {"none", "unlimited"}
AMOUNT_RE = re.compile(r"^\d+(?:[.,]\d{1,2})?$")      # «200», «450,5», «99.99»; «1,000» — неоднозначно

DDL = """
CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,                 -- ISO 8601, UTC
    day TEXT NOT NULL,                -- YYYY-MM-DD (UTC) — денний ліміт
    month TEXT NOT NULL,              -- YYYY-MM (UTC) — місячний ліміт
    story TEXT NOT NULL,
    part INTEGER NOT NULL,
    stage TEXT NOT NULL,
    provider TEXT NOT NULL,
    units REAL NOT NULL CHECK (units >= 0),
    unit TEXT NOT NULL,               -- second / image / 1k_chars / 1m_tokens
    usd_micros INTEGER NOT NULL CHECK (usd_micros >= 0),
    status TEXT NOT NULL CHECK (status IN ('reserved', 'settled', 'released')),
    forced INTEGER NOT NULL DEFAULT 0,
    input_hash TEXT NOT NULL DEFAULT '',
    request_id TEXT UNIQUE,           -- id задачі провайдера: повторний запис не дублює витрату
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS costs_day ON costs (day);
CREATE INDEX IF NOT EXISTS costs_month ON costs (month);
CREATE INDEX IF NOT EXISTS costs_part ON costs (story, part);
CREATE INDEX IF NOT EXISTS costs_hash ON costs (input_hash);
"""


class BudgetError(RuntimeError):
    """Платний виклик заборонено."""


class BudgetExceeded(BudgetError):
    """Виклик перевищив би ліміт. Продовжити — лише явно (force)."""


class BudgetNotConfigured(BudgetError):
    """Ліміт не задано — платні виклики заборонені, доки людина не впише число або `none`."""


def to_micros(usd: float) -> int:
    if not isinstance(usd, (int, float)) or isinstance(usd, bool) or not math.isfinite(usd) or usd < 0:
        raise ValueError(f"сума має бути скінченним числом ≥ 0, а не {usd!r}")
    return round(usd * MICROS)


def usd(micros: int) -> float:
    return micros / MICROS


@dataclass(frozen=True)
class Limits:
    """Ліміти в мікродоларах. None — без ліміту (лише якщо людина явно написала `none`)."""

    per_episode: int | None = None
    daily: int | None = None
    monthly: int | None = None
    missing: tuple[str, ...] = ()      # ключі, яких людина не задала

    @classmethod
    def of(cls, per_episode: float | None = None, daily: float | None = None,
           monthly: float | None = None) -> Limits:
        """Для коду й тестів: ліміти в USD; None — без ліміту."""
        conv = (lambda v: None if v is None else to_micros(v))
        return cls(conv(per_episode), conv(daily), conv(monthly))

    @classmethod
    def from_env(cls, env_path: Path | None = None) -> Limits:
        env = config.read_env(env_path)
        unknown = [k for k in env if k.upper().startswith("BUDGET_") and k not in LIMIT_KEYS]
        if unknown:
            raise config.ConfigError(
                f"Невідомий ключ бюджету в .env: {', '.join(unknown)}. Відомі: {', '.join(LIMIT_KEYS)}")
        values, missing = {}, []
        for key, name in LIMIT_KEYS.items():
            raw = config.get(key, env)
            if raw is None:
                missing.append(key)
                values[name] = None
            elif raw.lower() in UNLIMITED:
                values[name] = None
            elif AMOUNT_RE.match(raw):
                values[name] = to_micros(float(raw.replace(",", ".")))
            else:
                raise config.ConfigError(
                    f"{key}={raw!r}: має бути сума в USD (напр. 200 або 99.50) або `none` (без ліміту)")
        return cls(**values, missing=tuple(missing))


@dataclass
class Charge:
    """Що обгортка charge() знає про виклик. Заповнюй після відповіді провайдера."""

    id: int
    estimate_usd: float
    warnings: list[str] = field(default_factory=list)
    actual_usd: float | None = None
    request_id: str | None = None
    not_charged: bool = False


def _utc(when: datetime | None) -> datetime:
    return (when or datetime.now(timezone.utc)).astimezone(timezone.utc)


class Ledger:
    def __init__(self, path: Path = DB_PATH, limits: Limits | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)   # транзакції — вручну
        self.db.execute("PRAGMA journal_mode=WAL")       # читачі не блокують запис
        self.db.execute("PRAGMA busy_timeout=30000")
        self._migrate()
        self.limits = limits if limits is not None else Limits.from_env()

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------ схема

    def _migrate(self) -> None:
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version >= SCHEMA_VERSION:
            return
        with self._tx():
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(costs)")}
            if "usd" in cols:      # v1 (PR #11 до рев'ю): usd REAL, без статусів
                self.db.execute("ALTER TABLE costs RENAME TO costs_v1")
            for stmt in DDL.strip().split(";"):
                if stmt.strip():
                    self.db.execute(stmt)
            if "usd" in cols:
                self.db.execute(
                    "INSERT INTO costs (at, day, month, story, part, stage, provider, units, unit, usd_micros, "
                    "status, input_hash) SELECT at, day, substr(day, 1, 7), story, part, stage, provider, units, "
                    f"unit, CAST(ROUND(usd * {MICROS}) AS INTEGER), 'settled', input_hash FROM costs_v1")
                self.db.execute("DROP TABLE costs_v1")
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _tx(self) -> Iterator[None]:
        self.db.execute("BEGIN IMMEDIATE")       # блокує запис іншим процесам до COMMIT
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        self.db.execute("COMMIT")

    # ------------------------------------------------------------ читання

    def _spent(self, story: str | None = None, part: int | None = None, day: str | None = None,
               month: str | None = None) -> int:
        sql, args = "SELECT COALESCE(SUM(usd_micros), 0) FROM costs WHERE status != 'released'", []
        for col, val in (("story", story), ("part", part), ("day", day), ("month", month)):
            if val is not None:
                sql += f" AND {col} = ?"
                args.append(val)
        return self.db.execute(sql, args).fetchone()[0]

    def spent(self, story: str | None = None, part: int | None = None, day: str | None = None,
              month: str | None = None) -> float:
        """USD (зарезервовано + сплачено) за серію (story, part), день «2026-10-06» або місяць «2026-10» (UTC)."""
        return usd(self._spent(story, part, day, month))

    def unsettled(self) -> list[tuple]:
        """Резерви без підтвердження — звірити з рахунком провайдера вручну."""
        return self.db.execute(
            "SELECT id, at, story, part, stage, provider, usd_micros FROM costs WHERE status = 'reserved' "
            "ORDER BY id").fetchall()

    def already_paid(self, input_hash: str) -> bool:
        """Чи є сплачений виклик з таким входом. Лише облік: ідемпотентність етапів — за артефактом з хешем."""
        return bool(input_hash) and self.db.execute(
            "SELECT 1 FROM costs WHERE input_hash = ? AND status = 'settled' LIMIT 1",
            (input_hash,)).fetchone() is not None

    # ------------------------------------------------------------ ліміти

    def _evaluate(self, story: str, part: int, micros: int, when: datetime) -> tuple[list[str], list[str]]:
        day, month = f"{when:%Y-%m-%d}", f"{when:%Y-%m}"
        scopes = [
            (f"серія {story} ч.{part}", self.limits.per_episode, self._spent(story, part)),
            (f"день {day} (UTC)", self.limits.daily, self._spent(day=day)),
            (f"місяць {month}", self.limits.monthly, self._spent(month=month)),
        ]
        warnings, over = [], []
        for name, limit, spent in scopes:
            if limit is None:
                continue
            after = spent + micros
            share = f" ({after / limit:.1%})" if limit else ""
            text = f"{name}: ${usd(after):.2f} з ${usd(limit):.2f}{share}"
            if after > limit:
                over.append(text)
            elif after >= WARN_SHARE * limit:
                warnings.append(text)
        return warnings, over

    def _gate(self, story: str, part: int, micros: int, when: datetime, force: bool) -> tuple[list[str], bool]:
        warnings, over = self._evaluate(story, part, micros, when)
        if self.limits.missing and not force:
            raise BudgetNotConfigured(
                "Ліміти бюджету не задано: " + ", ".join(self.limits.missing)
                + ". Платні виклики заборонені — впиши суму в USD у .env (або `none`, якщо свідомо без ліміту).")
        if over and not force:
            raise BudgetExceeded("Ліміт бюджету буде перевищено — зупинка. " + "; ".join(over)
                                 + ". Продовжити можна лише явним прапорцем (force).")
        forced = bool(over or self.limits.missing)
        notes = [f"⚠️ ПЕРЕВИЩЕНО (force): {o}" for o in over]
        if self.limits.missing:
            notes.append("⚠️ ліміти не задано (force): " + ", ".join(self.limits.missing))
        return warnings + notes, forced

    def check(self, story: str, part: int, usd_amount: float, when: datetime | None = None,
              force: bool = False) -> list[str]:
        """Суха перевірка (нічого не записує): попередження або BudgetExceeded / BudgetNotConfigured."""
        warnings, _ = self._gate(story, part, to_micros(usd_amount), _utc(when), force)
        return warnings

    # ------------------------------------------------------------ запис

    def reserve(self, story: str, part: int, stage: str, provider: str, *, estimate_usd: float, units: float,
                unit: str, input_hash: str = "", force: bool = False, when: datetime | None = None,
                note: str = "") -> Charge:
        """Атомарно: перевірити ліміти з урахуванням чужих резервів і зарезервувати оцінку."""
        micros, when = to_micros(estimate_usd), _utc(when)
        if not math.isfinite(units) or units < 0:
            raise ValueError(f"units має бути ≥ 0, а не {units!r}")
        with self._tx():
            warnings, forced = self._gate(story, part, micros, when, force)
            cur = self.db.execute(
                "INSERT INTO costs (at, day, month, story, part, stage, provider, units, unit, usd_micros, status, "
                "forced, input_hash, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?, ?)",
                (when.isoformat(timespec="seconds"), f"{when:%Y-%m-%d}", f"{when:%Y-%m}", story, part, stage,
                 provider, units, unit, micros, int(forced), input_hash, note))
        return Charge(id=cur.lastrowid, estimate_usd=estimate_usd, warnings=warnings)

    def settle(self, charge_id: int, actual_usd: float | None = None, request_id: str | None = None) -> None:
        """Підтвердити витрату (факт замість оцінки). Повторний виклик для того самого резерву — без змін."""
        with self._tx():
            row = self.db.execute("SELECT status, usd_micros FROM costs WHERE id = ?", (charge_id,)).fetchone()
            if row is None:
                raise KeyError(f"резерву {charge_id} немає")
            if row[0] == "settled":
                return
            if row[0] == "released":
                raise ValueError(f"резерв {charge_id} уже знято — підтвердити не можна")
            micros = row[1] if actual_usd is None else to_micros(actual_usd)
            try:
                self.db.execute("UPDATE costs SET status = 'settled', usd_micros = ?, request_id = ? WHERE id = ?",
                                (micros, request_id, charge_id))
            except sqlite3.IntegrityError:
                raise ValueError(f"request_id {request_id!r} уже записано в іншому рядку журналу") from None

    def release(self, charge_id: int) -> None:
        """Зняти резерв — лише якщо провайдер точно нічого не списав."""
        with self._tx():
            self.db.execute("UPDATE costs SET status = 'released' WHERE id = ? AND status = 'reserved'",
                            (charge_id,))

    @contextmanager
    def charge(self, story: str, part: int, stage: str, provider: str, *, estimate_usd: float, units: float,
               unit: str, input_hash: str = "", force: bool = False, note: str = "") -> Iterator[Charge]:
        """Одна обгортка для платних викликів: резерв → виклик → підтвердження (див. docstring модуля)."""
        c = self.reserve(story, part, stage, provider, estimate_usd=estimate_usd, units=units, unit=unit,
                         input_hash=input_hash, force=force, note=note)
        try:
            yield c
        except BaseException:
            if c.not_charged:
                self.release(c.id)
            raise                      # інакше резерв лишається «незвіреним» і рахується як витрата
        if c.not_charged:
            self.release(c.id)
        else:
            self.settle(c.id, c.actual_usd, c.request_id)

    def record(self, story: str, part: int, stage: str, provider: str, units: float, unit: str, usd_amount: float,
               input_hash: str = "", when: datetime | None = None, request_id: str | None = None,
               note: str = "") -> bool:
        """Записати вже сплачений факт без перевірки лімітів (імпорт із рахунку, ручні витрати).
        З request_id — ідемпотентно: повтор не дублює. Повертає True, якщо рядок додано."""
        micros, when = to_micros(usd_amount), _utc(when)
        with self._tx():
            cur = self.db.execute(
                "INSERT OR IGNORE INTO costs (at, day, month, story, part, stage, provider, units, unit, usd_micros, "
                "status, input_hash, request_id, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'settled', ?, ?, ?)",
                (when.isoformat(timespec="seconds"), f"{when:%Y-%m-%d}", f"{when:%Y-%m}", story, part, stage,
                 provider, units, unit, micros, input_hash, request_id, note))
        return cur.rowcount == 1
