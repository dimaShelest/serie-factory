"""Біблія серіалу (series/<slug>/bible.yaml + clues.md) — те, що з неї потрібно фабриці.

Зміст біблії — зона Claude A. Тут лише читання ID, на які посилаються script.json і shots.json.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "series"
CLUE_ROW = re.compile(r"^\|\s*(C\d{2}|F\d+)\s*\|", re.M)


@dataclass(frozen=True)
class Bible:
    slug: str
    character_ids: frozenset[str]
    supporting_ids: frozenset[str]
    location_ids: frozenset[str]
    clue_ids: frozenset[str]        # C01… з clues.md і хибні сліди F1…
    data: dict                      # увесь bible.yaml — для етапів refs / voice / qc


def load(slug: str, series_dir: Path = SERIES) -> Bible:
    folder = series_dir / slug
    data = yaml.safe_load((folder / "bible.yaml").read_text(encoding="utf-8-sig"))
    clues = folder / "clues.md"
    clue_text = clues.read_text(encoding="utf-8-sig") if clues.exists() else ""
    return Bible(
        slug=data["slug"],
        character_ids=frozenset(c["id"] for c in data.get("characters", [])),
        supporting_ids=frozenset(c["id"] for c in data.get("supporting", [])),
        location_ids=frozenset(loc["id"] for loc in data.get("locations", [])),
        clue_ids=frozenset(CLUE_ROW.findall(clue_text)),
        data=data,
    )
