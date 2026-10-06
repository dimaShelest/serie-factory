"""part1_shotlist.md (розкадровка A) → shots.json без втрат, той самий кошторис (fabrica/shotlist.py, costs.py).

Еталон кошторису беремо з таблиці «Підсумок» самої розкадровки, а не вписуємо в тест: змінить A розкадровку —
тест звірить заново.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fabrica import bible, costs, shotlist
from fabrica.models import Script, Shots, check_refs, check_shots, shots_errors

ROOT = Path(__file__).resolve().parents[1]
SHOTLIST = ROOT / "series" / "la-garganta" / "part1_shotlist.md"
SCRIPT = Script.model_validate_json(
    (ROOT / "tests" / "fixtures" / "la-garganta" / "part1.script.json").read_text(encoding="utf-8"))
BIBLE = bible.load("la-garganta")
RAW, ISSUES = shotlist.convert(SHOTLIST, BIBLE, 1, SCRIPT)
SHOTS = Shots.model_validate(RAW)
TIER_NAMES = {"hero": "hero", "secondary": "secondary", "found-footage": "found_footage", "still": "still",
              "монтаж": "montage"}


def summary() -> dict[str, dict]:
    """Таблиця «Підсумок» розкадровки: tier → шотів, екранні с, $ оптимістично, $ консервативно."""
    text = SHOTLIST.read_text(encoding="utf-8")
    table = text.split("## Підсумок", 1)[1].split("\n\n", 2)[1]
    out = {}
    for row in table.splitlines()[2:]:
        cells = [c.strip().strip("*") for c in row.strip().strip("|").split("|")]
        money = [float(m) for m in re.findall(r"\$(\d+\.\d+)", row)]
        key = TIER_NAMES.get(cells[0], cells[0])
        out[key] = {"shots": int(cells[1]), "screen_s": float(cells[2]), "usd": money}
    return out


def test_converts_without_issues() -> None:
    assert ISSUES == []
    assert check_refs(SHOTS, BIBLE) == []


def test_every_row_is_kept() -> None:
    rows = [r for r in SHOTLIST.read_text(encoding="utf-8").splitlines() if re.match(r"^\| \d+\.\d{2} \|", r)]
    assert [s.id for s in SHOTS.shots] == [r.split("|")[1].strip() for r in rows]
    for sh, row in zip(SHOTS.shots, rows):
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        assert sh.action == cells[6]
        assert [d.text_es for d in sh.dialogue] == re.findall(r"«([^»]+)»", cells[7])
        assert (sh.reuse_note or "") == cells[9]
        assert len(sh.labels) >= len(re.findall(r"`[A-Z_0-9]+`", cells[10]))


def test_same_estimate_as_shotlist() -> None:
    rates = costs.load_rates()
    optimistic = costs.estimate(SHOTS, rates, min_clip_s=0)
    conservative = costs.estimate(SHOTS, rates, min_clip_s=5)
    want = summary()
    for tier, t in optimistic.tiers.items():
        assert (t.shots, t.screen_s) == (want[tier]["shots"], want[tier]["screen_s"]), tier
        if want[tier]["usd"]:
            assert [t.usd, conservative.tiers[tier].usd] == want[tier]["usd"], tier
    assert [optimistic.usd, conservative.usd] == want["Разом"]["usd"]
    assert optimistic.reused_s == 19          # «Без генерації: ♻ 19 с»
    assert optimistic.lipsync_s == 46         # «lip-sync для hero-шотів з реплікою — 46 с»


def test_who_and_dialogue() -> None:
    by_id = {s.id: s for s in SHOTS.shots}
    assert by_id["1.02"].characters == ["lupita", "monica", "ivan"]
    assert by_id["3.07"].characters == ["vale", "diego", "sofia", "mateo"]
    assert by_id["8.11"].characters == ["vale", "beto"] and "Beto: мокрий" in by_id["8.11"].notes
    d = by_id["3.04"].dialogue[0]
    assert (d.character_id, d.offscreen) == ("diego", True)               # «(Diego, за кадром)»
    assert by_id["3.06"].dialogue[0].line_id == "l04"                     # «No tengo hambre.» зі script
    assert by_id["7.08"].has_dialogue_visible is False                    # напарник спиною
    assert by_id["8.17"].dialogue[0].character_id == "vale"               # голос у чорному — зі script


def test_reuse_and_labels() -> None:
    by_id = {s.id: s for s in SHOTS.shots}
    assert by_id["2.01"].reuse == "plate:mina"
    assert by_id["6.08"].reuse == "plate:plaza_reloj"
    assert by_id["7.16"].reuse == "shot:6.04"
    assert by_id["3.07"].reuse is None and by_id["3.07"].reuse_note == "→ ч.3 (шлях у шахту)"
    assert [lb.key for lb in by_id["6.04"].labels] == ["MIDPOINT", "TEASER2_CUT_BEFORE"]
    assert by_id["6.04"].clues.planted == ["C01"]
    assert by_id["1.01"].labels[0].key == "HOOK_OPEN"                     # з заголовка «Біт 1 · HOOK_OPEN»
    assert {f.type for f in by_id["1.07"].sfx} == {"sting"}
    assert by_id["9.01"].segment == "end_card" and by_id["9.01"].film_exclude


# ---------------------------------------------------------------- що розкадровка порушує зараз (для A)


@pytest.mark.xfail(strict=True, reason="T1 у part1_shotlist.md = 28 с (1.01 → 1.07), а PLAYBOOK: 30–40 с")
def test_shotlist_follows_playbook() -> None:
    assert shots_errors(SHOTS) == []


@pytest.mark.xfail(strict=True, reason="1.02: «¡Chuy, graba, graba!…», а story.md: «¡Graba, graba!…»")
def test_shotlist_covers_script() -> None:
    assert check_shots(SHOTS, SCRIPT) == []


def test_current_violations_are_exactly_known() -> None:
    assert shots_errors(SHOTS) == ["TEASER1: 28 с, а має бути 30–40"]
    assert [e for e in check_shots(SHOTS, SCRIPT)] == [
        "репліка l01 (s01) «¡Graba, graba! Esto va para el anuario.» не потрапила в жоден шот"]


def test_shots_json_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "part1.shots.json"
    out.write_text(SHOTS.model_dump_json(indent=2), encoding="utf-8")
    assert Shots.model_validate(json.loads(out.read_text(encoding="utf-8"))) == SHOTS
