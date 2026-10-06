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
    supporting_ids: frozenset[str]   # supporting[] і їхні members[] (сімка 1994)
    location_ids: frozenset[str]
    clue_ids: frozenset[str]         # C01… з clues.md і хибні сліди F1…
    names: dict[str, str]            # «Sofía», «Rosa Elena», «Chuy», «Saldívar» → id
    data: dict                       # увесь bible.yaml — для етапів refs / voice / qc


def _aliases(name: str) -> set[str]:
    """«Jesús «Chuy» Robles» → повне ім'я, префікси слів, останнє слово, прізвисько в «»."""
    out = set(re.findall(r"«([^»]+)»", name))
    words = name.split()
    out |= {" ".join(words[:k]) for k in range(1, len(words) + 1)}
    out.add(words[-1])
    return {a.strip() for a in out if a.strip()}


def load(slug: str, series_dir: Path = SERIES) -> Bible:
    folder = series_dir / slug
    data = yaml.safe_load((folder / "bible.yaml").read_text(encoding="utf-8-sig"))
    clues = folder / "clues.md"
    clue_text = clues.read_text(encoding="utf-8-sig") if clues.exists() else ""
    supporting = data.get("supporting", [])
    members = [m for s in supporting for m in s.get("members", [])]
    names: dict[str, str] = {}
    for person in [*data.get("characters", []), *members]:
        for alias in _aliases(person["name"]):
            names.setdefault(alias, person["id"])
    return Bible(
        slug=data["slug"],
        character_ids=frozenset(c["id"] for c in data.get("characters", [])),
        supporting_ids=frozenset(s["id"] for s in [*supporting, *members]),
        location_ids=frozenset(loc["id"] for loc in data.get("locations", [])),
        clue_ids=frozenset(CLUE_ROW.findall(clue_text)),
        names=names,
        data=data,
    )
