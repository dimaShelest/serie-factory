"""Кошторис генерації відео (Issue #3, частина «оцінка перед викликом»).

Два джерела ставок, і хто важить більше:
- ціна ОДНОГО виклику (call_usd: черга fabrica/video.py і estimate_items) — каталог маршрутів
  (prompts/providers.yaml, providers.price: точна ставка маршруту, роздільності й тривалості з payload);
  немає ціни в каталозі — ставка COSTS.md × тривалість; немає й там — None (ставку не вигадуємо).
- кошторис за shots.json (estimate, load_rates) — docs/COSTS.md (таблиця «Тарифи провайдерів»: її оновлюють
  люди за рахунком); роздільності, якої там немає, — каталог (VIDEO_ROUTE).
Рахунок прийшов з іншою ставкою — виправ price у providers.yaml (черга) і рядок у COSTS.md (люди).
estimate_items — кошторис за скомпільованими кліпами (профіль генерації, напр. 5 с на кліп, уже в payload);
estimate — старий, за екранними секундами shots.json. Планувальний коефіцієнт — × ATTEMPTS спроби.
Мінімальна оплачувана тривалість кліпу (min_clip_s, лише estimate): 0 — екранні секунди, 5 — кожен кліп ≥ 5 с.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from fabrica import providers as providers_mod
from fabrica.models import Shots

if TYPE_CHECKING:
    from fabrica.prompts import Item

ROOT = Path(__file__).resolve().parents[1]
COSTS_MD = ROOT / "docs" / "COSTS.md"
ATTEMPTS = 2
TIER_RESOLUTION = {"hero": "720p", "secondary": "480p", "found_footage": "480p"}
VIDEO_ROUTE = "replicate:bytedance/seedance-2.5"


def load_rates(path: Path = COSTS_MD, provider: str = "Seedance", route: str | None = VIDEO_ROUTE) -> dict[str, float]:
    """{"720p": 0.23, "480p": 0.11} з рядків таблиці тарифів: «| Seedance 2.5 | … 720p … | ≈ 0,23 | …»;
    роздільності без рядка (або без файлу) — з providers.video_rates(route). route=None — лише COSTS.md."""
    rates = {}
    rows = path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].startswith(provider):
            continue
        res = re.search(r"(\d{3,4}p)", cells[2])
        price = re.search(r"(\d+(?:[.,]\d+)?)", cells[3])
        if res and price:
            rates[res.group(1)] = float(price.group(1).replace(",", "."))
    catalog, why = {}, ""
    if route:
        try:
            catalog = providers_mod.video_rates(route)
        except providers_mod.ProviderError as e:
            why = f"; каталог маршрутів: {e}"
    if not rates and not catalog:
        raise ValueError(f"У {path} немає ставок {provider} (рядки «| {provider} … | … 720p … | ≈ 0,23 |»){why}")
    return {**catalog, **rates}


def field_value(route: str, payload: dict, name: str):
    """Значення поля payload; немає — типове маршруту (те, що візьме API); duration -1 — максимум маршруту."""
    try:
        spec = providers_mod.route(route).fields.get(name) or {}
    except providers_mod.ProviderError:
        spec = {}
    v = payload.get(name, spec.get("default"))
    return spec.get("max") if name == "duration" and isinstance(v, (int, float)) and v < 0 else v


def call_usd(route: str, payload: dict, path: Path = COSTS_MD) -> float | None:
    """USD за один виклик: каталог (providers.price) → ставка COSTS.md за роздільністю × тривалість → None.
    None — ціни немає: виклик не плануємо як безкоштовний (ліміти бюджету тоді нічого не захищають)."""
    try:
        usd = providers_mod.price(route, payload)
    except providers_mod.ProviderError:
        usd = None
    if usd is None:
        try:
            rate_ = load_rates(path, route=route).get(str(field_value(route, payload, "resolution")))
        except ValueError:
            rate_ = None
        dur = field_value(route, payload, "duration")
        usd = rate_ * float(dur) if rate_ is not None and isinstance(dur, (int, float)) and dur > 0 else None
    return None if usd is None else round(usd, 4)


def rate(provider: str, path: Path = COSTS_MD) -> float:
    """Ставка провайдера з одним рядком у таблиці тарифів («| ElevenLabs | voice | 1K символів | ≈ 0,30 |»).
    TODO або кілька рядків — помилка: ставку не вигадуємо і не беремо навмання."""
    found = []
    for row in path.read_text(encoding="utf-8-sig").splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0].startswith(provider):
            found.append(cells[3])
    if len(found) != 1:
        raise ValueError(f"У {path.name} має бути рівно один рядок «{provider}» у тарифах, а знайдено {len(found)}")
    price = re.search(r"(\d+(?:[.,]\d+)?)", found[0])
    if not price:
        raise ValueError(f"Ставку {provider} у {path.name} не задано ({found[0]!r}) — впиши ціну за одиницю з рахунку")
    return float(price.group(1).replace(",", "."))


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
    unpriced: list[str] = field(default_factory=list)   # estimate_items: кліпи без ціни (у суму не ввійшли)

    @property
    def usd(self) -> float:
        return round(sum(t.usd for t in self.tiers.values()), 2)


def estimate(shots: Shots, rates: dict[str, float], attempts: int = ATTEMPTS, min_clip_s: float = 0.0) -> Estimate:
    est = Estimate()
    for sh in shots.shots:
        t = est.tiers.setdefault(sh.tier, TierCost())
        t.shots += 1
        t.screen_s += sh.duration_s
        billed = sh.billable_seconds
        if billed <= 0:
            continue
        billed = max(billed, min_clip_s)
        t.billed_s += billed
        t.usd += billed * rates[TIER_RESOLUTION[sh.tier]] * attempts
    for t in est.tiers.values():
        t.usd = round(t.usd, 2)
    _reused(est, shots)
    return est


def _reused(est: Estimate, shots: Shots) -> None:
    for sh in shots.shots:
        est.reused_s += sh.duration_s if sh.reuse else 0
        est.lipsync_s += sh.duration_s if sh.has_dialogue_visible else 0


def estimate_items(items: list[Item], attempts: int = ATTEMPTS, shots: Shots | None = None,
                   path: Path = COSTS_MD) -> Estimate:
    """Кошторис за скомпільованими відео-елементами (маршрут + payload — рівно те, що піде в API; профіль кліпу,
    напр. 5 с, уже враховано): call_usd × attempts за тирами. screen_s — вікна монтажу кліпів, billed_s —
    тривалості генерації. Без ціни — est.unpriced (у суму не входять). shots — лише для ♻ і lip-sync секунд."""
    est, seen = Estimate(), set()
    for it in items:
        if it.kind != "video" or not it.route or not it.payload:
            continue
        tier = str(it.extra.get("tier") or "—")
        t = est.tiers.setdefault(tier, TierCost())
        if (tier, shot := it.extra.get("shot") or it.id) not in seen:
            seen.add((tier, shot))
            t.shots += 1
        dur = field_value(it.route, it.payload, "duration")
        dur = float(dur) if isinstance(dur, (int, float)) and dur > 0 else 0.0
        win = (it.extra.get("clip") or {}).get("window")
        t.screen_s += float(win[1]) - float(win[0]) if isinstance(win, (list, tuple)) and len(win) == 2 else dur
        t.billed_s += dur
        if (usd := call_usd(it.route, it.payload, path)) is None:
            est.unpriced.append(it.id)
        else:
            t.usd += usd * attempts
    for t in est.tiers.values():
        t.usd, t.screen_s = round(t.usd, 2), round(t.screen_s, 3)
    if shots is not None:
        _reused(est, shots)
    return est
