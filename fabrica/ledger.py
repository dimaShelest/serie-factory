"""Облік фактичних витрат і ліміти бюджету (Issue #3, docs/ARCHITECTURE.md → «Наскрізне: облік витрат»).

Кожен платний виклик:
    ledger.check(story, part, estimate_usd)     # перед викликом: ≥ 80 % — попередження, > 100 % — BudgetExceeded
    ... виклик провайдера ...
    ledger.record(story, part, stage, provider, units, unit, usd, input_hash)   # після — факт у SQLite

Ліміти — з оточення або `.env`: BUDGET_PER_EPISODE_USD, BUDGET_DAILY_USD, BUDGET_MONTHLY_USD (порожньо — без ліміту).
Перевищити ліміт можна лише явно: check(..., force=True).
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "output" / "fabrica.sqlite"
ENV_FILE = ROOT / ".env"
WARN_SHARE = 0.8

SCHEMA = """
CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,            -- ISO з поясом, локальний час машини
    day TEXT NOT NULL,           -- YYYY-MM-DD (локальний) — для денного ліміту
    story TEXT NOT NULL,
    part INTEGER NOT NULL,
    stage TEXT NOT NULL,
    provider TEXT NOT NULL,
    units REAL NOT NULL,
    unit TEXT NOT NULL,          -- second / image / 1k_chars / 1m_tokens
    usd REAL NOT NULL,
    input_hash TEXT NOT NULL DEFAULT ''
)
"""


class BudgetExceeded(RuntimeError):
    """Виклик перевищив би ліміт. Продовжити — лише check(..., force=True)."""


@dataclass(frozen=True)
class Limits:
    per_episode: float | None = None
    daily: float | None = None
    monthly: float | None = None

    @classmethod
    def from_env(cls, env_file: Path = ENV_FILE) -> Limits:
        values = _read_env(env_file)

        def get(key: str) -> float | None:
            raw = (os.environ.get(key) or values.get(key) or "").strip()
            try:
                return float(raw.replace(",", ".")) if raw else None
            except ValueError:
                raise ValueError(f"{key}={raw!r}: має бути число в USD або порожньо") from None

        return cls(get("BUDGET_PER_EPISODE_USD"), get("BUDGET_DAILY_USD"), get("BUDGET_MONTHLY_USD"))


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():   # PowerShell 5.1 пише .env з BOM
        key, sep, value = line.strip().partition("=")
        if sep and key.startswith("BUDGET_"):
            out[key.strip()] = value.strip().strip("'\"")
    return out


class Ledger:
    def __init__(self, path: Path = DB_PATH, limits: Limits | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.limits = limits if limits is not None else Limits.from_env()

    def close(self) -> None:
        self.db.close()

    def record(self, story: str, part: int, stage: str, provider: str, units: float, unit: str, usd: float,
               input_hash: str = "", when: datetime | None = None) -> None:
        when = (when or datetime.now()).astimezone()
        self.db.execute(
            "INSERT INTO costs (at, day, story, part, stage, provider, units, unit, usd, input_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (when.isoformat(timespec="seconds"), when.strftime("%Y-%m-%d"), story, part, stage, provider,
             units, unit, usd, input_hash))
        self.db.commit()

    def spent(self, story: str | None = None, part: int | None = None, day_prefix: str | None = None) -> float:
        """USD за серію (story+part), за день («2026-10-06») або місяць («2026-10»)."""
        sql, args = "SELECT COALESCE(SUM(usd), 0) FROM costs WHERE 1=1", []
        if story is not None:
            sql, args = sql + " AND story = ?", [*args, story]
        if part is not None:
            sql, args = sql + " AND part = ?", [*args, part]
        if day_prefix is not None:
            sql, args = sql + " AND day LIKE ?", [*args, day_prefix + "%"]
        return round(self.db.execute(sql, args).fetchone()[0], 4)

    def already_paid(self, input_hash: str) -> bool:
        """Ідемпотентність етапів: той самий вхід уже оплачено — не генеруємо вдруге."""
        return bool(input_hash) and self.db.execute(
            "SELECT 1 FROM costs WHERE input_hash = ? LIMIT 1", (input_hash,)).fetchone() is not None

    def check(self, story: str, part: int, usd: float, when: datetime | None = None,
              force: bool = False) -> list[str]:
        """Перевірка перед платним викликом на usd. Повертає попередження (≥ 80 %); > 100 % → BudgetExceeded."""
        when = (when or datetime.now()).astimezone()
        scopes = [
            (f"серія {story} ч.{part}", self.limits.per_episode, self.spent(story, part)),
            (f"день {when:%Y-%m-%d}", self.limits.daily, self.spent(day_prefix=f"{when:%Y-%m-%d}")),
            (f"місяць {when:%Y-%m}", self.limits.monthly, self.spent(day_prefix=f"{when:%Y-%m}")),
        ]
        warnings, over = [], []
        for name, limit, spent in scopes:
            if limit is None:
                continue
            after = spent + usd
            text = f"{name}: ${after:.2f} з ${limit:.2f} ({after / limit:.0%})" if limit else f"{name}: ліміт $0"
            if after > limit:
                over.append(text)
            elif after >= WARN_SHARE * limit:
                warnings.append(text)
        if over and not force:
            raise BudgetExceeded("Ліміт бюджету буде перевищено — зупинка. " + "; ".join(over)
                                 + ". Продовжити можна лише явним прапорцем (force).")
        return warnings + [f"⚠️ ПЕРЕВИЩЕНО (force): {o}" for o in over]
