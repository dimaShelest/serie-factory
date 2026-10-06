"""Кошторис генерації відео за shots.json (Issue #3, частина «оцінка перед викликом»).

Ставки — з docs/COSTS.md (таблиця «Тарифи провайдерів»): там їх оновлюють люди, коли приходить рахунок.
Планувальний коефіцієнт — × ATTEMPTS спроби. Мінімальну оплачувану тривалість кліпу (min_clip_s) ще
перевіряємо тест-паком Seedance, тож це параметр: 0 — платимо за екранні секунди, 5 — кожен кліп ≥ 5 с.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.models import Shots

ROOT = Path(__file__).resolve().parents[1]
COSTS_MD = ROOT / "docs" / "COSTS.md"
ATTEMPTS = 2
TIER_RESOLUTION = {"hero": "720p", "secondary": "480p", "found_footage": "480p"}


def load_rates(path: Path = COSTS_MD, provider: str = "Seedance") -> dict[str, float]:
    """{"720p": 0.23, "480p": 0.11} з рядків таблиці тарифів: «| Seedance 2.5 | … 720p … | ≈ 0,23 | …»."""
    rates = {}
    for row in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].startswith(provider):
            continue
        res = re.search(r"(\d{3,4}p)", cells[2])
        price = re.search(r"(\d+(?:[.,]\d+)?)", cells[3])
        if res and price:
            rates[res.group(1)] = float(price.group(1).replace(",", "."))
    if not rates:
        raise ValueError(f"У {path} немає ставок {provider} (рядки «| {provider} … | … 720p … | ≈ 0,23 |»)")
    return rates


@dataclass
class TierCost:
    shots: int = 0
    screen_s: float = 0.0     # екранні секунди
    billed_s: float = 0.0     # оплачувані за одну спробу (з урахуванням min_clip_s)
    usd: float = 0.0          # × ATTEMPTS


@dataclass
class Estimate:
    tiers: dict[str, TierCost] = field(default_factory=dict)
    reused_s: float = 0.0     # секунди, які не генеруємо (♻)
    lipsync_s: float = 0.0    # секунди з видимою реплікою — для Sync (ставка поки TODO)

    @property
    def usd(self) -> float:
        return round(sum(t.usd for t in self.tiers.values()), 2)


def estimate(shots: Shots, rates: dict[str, float], attempts: int = ATTEMPTS, min_clip_s: float = 0.0) -> Estimate:
    est = Estimate()
    for sh in shots.shots:
        t = est.tiers.setdefault(sh.tier, TierCost())
        t.shots += 1
        t.screen_s += sh.duration_s
        if sh.reuse:
            est.reused_s += sh.duration_s
        if sh.has_dialogue_visible:
            est.lipsync_s += sh.duration_s
        billed = sh.billable_seconds
        if billed <= 0:
            continue
        billed = max(billed, min_clip_s)
        t.billed_s += billed
        t.usd += billed * rates[TIER_RESOLUTION[sh.tier]] * attempts
    for t in est.tiers.values():
        t.usd = round(t.usd, 2)
    return est
