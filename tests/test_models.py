"""Схеми script.json / shots.json (fabrica/models.py) на реальній історії LA GARGANTA.

Готово, коли частина 1 зі story.md лягає в script.json без втрат, а правила міток ловлять порушення.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fabrica import bible, story
from fabrica.models import (
    Script,
    Shots,
    Unit,
    check_refs,
    check_shots,
    script_errors,
    shots_errors,
    teaser_seconds,
)

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "series" / "la-garganta" / "story.md"
PART1 = json.loads((ROOT / "tests" / "fixtures" / "la-garganta" / "part1.script.json").read_text(encoding="utf-8"))
PARTS = story.parse(STORY)


@pytest.fixture
def raw() -> dict:
    return copy.deepcopy(PART1)


def scene(data: dict, sid: str) -> dict:
    return next(s for s in data["scenes"] if s["id"] == sid)


# ---------------------------------------------------------------- story.md і реальний script


@pytest.mark.parametrize("part", [1, 2, 3, 4])
def test_story_parts_follow_label_rules(part: int) -> None:
    assert story.part_errors(PARTS[part]) == []


def test_part3_teaser_skips_recap() -> None:
    """Частина 3, T1: 0:00 → ~0:50 перетинає рекап 0:25–0:35; рекап у тизер не йде."""
    beats = PARTS[3]
    units = [Unit(b.segment, b.start_s, b.end_s, i) for i, b in enumerate(beats)]
    assert beats[1].segment == "recap"
    assert teaser_seconds(units, 0, 50) == 40


def test_part1_script_is_valid_and_lossless() -> None:
    script = Script.model_validate(PART1)
    assert script_errors(script) == []
    assert story.check_script(script, PARTS[1]) == []
    assert check_refs(script, bible.load("la-garganta")) == []


def test_lossless_check_catches_lost_line(raw: dict) -> None:
    scene(raw, "s07")["lines"].pop()
    errors = story.check_script(Script.model_validate(raw), PARTS[1])
    assert any("No toquen nada." in e for e in errors)


def test_lossless_check_catches_lost_clue(raw: dict) -> None:
    scene(raw, "s07")["clues"]["planted"].remove("C05")
    assert story.check_script(Script.model_validate(raw), PARTS[1])


def test_multiple_labels_in_one_beat(raw: dict) -> None:
    keys = [lb.key for lb in Script.model_validate(raw).scenes[0].labels]
    assert keys == ["HOOK_OPEN", "TEASER1_START", "TEASER1_CUT_BEFORE", "SCREAMER"]


def test_json_schema_exports() -> None:
    """Схему можна віддати LLM (local_llm.generate_json) як format."""
    for model in (Script, Shots):
        assert model.model_json_schema()["type"] == "object"


# ---------------------------------------------------------------- script: структура


def broken(raw: dict, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        Script.model_validate(raw)


def test_teaser_needs_n(raw: dict) -> None:
    scene(raw, "s05")["labels"][0].pop("n")
    broken(raw, "n потрібен")


def test_label_outside_scene_time(raw: dict) -> None:
    scene(raw, "s05")["labels"][0]["approx_s"] = 300
    broken(raw, "поза межами сцени")


def test_duplicate_line_ids(raw: dict) -> None:
    scene(raw, "s04")["lines"][0]["id"] = "l01"
    broken(raw, "повторюються ID реплік")


def test_unknown_field_rejected(raw: dict) -> None:
    raw["scenes"][0]["mood"] = "terror"
    broken(raw, "Extra inputs")


# ---------------------------------------------------------------- script: редакторські правила


def rule(raw: dict, match: str) -> None:
    errors = script_errors(Script.model_validate(raw))
    assert any(match in e for e in errors), errors


def test_two_hooks(raw: dict) -> None:
    scene(raw, "s03")["labels"] = [{"label": "HOOK_OPEN"}]
    rule(raw, "HOOK_OPEN: має бути рівно один")


def test_missing_cliff(raw: dict) -> None:
    scene(raw, "s08")["labels"] = []
    rule(raw, "CLIFF: має бути рівно один")


def test_cliff_not_in_last_beat(raw: dict) -> None:
    scene(raw, "s08")["labels"] = []
    scene(raw, "s07")["labels"] = [{"label": "CLIFF"}]
    rule(raw, "CLIFF: має бути в останньому біті")


def test_three_screamers(raw: dict) -> None:
    scene(raw, "s04")["labels"] = [{"label": "SCREAMER"}]
    scene(raw, "s08")["labels"].append({"label": "SCREAMER"})
    rule(raw, "SCREAMER: не більше 2")


def test_screamer_inside_teaser(raw: dict) -> None:
    scene(raw, "s05")["labels"].append({"label": "SCREAMER", "approx_s": 180})
    rule(raw, "TEASER2: містить SCREAMER")


def test_unpaired_teaser(raw: dict) -> None:
    scene(raw, "s06")["labels"] = [{"label": "MIDPOINT"}]
    rule(raw, "TEASER2: потрібна рівно одна пара")


def test_teaser_too_long(raw: dict) -> None:
    scene(raw, "s05")["labels"][0]["approx_s"] = 145      # 145 → 214 = 69 с
    rule(raw, "TEASER2: 69 с")


def test_label_in_recap_or_card(raw: dict) -> None:
    scene(raw, "s02")["labels"] = [{"label": "SCREAMER"}]
    rule(raw, "мітка в сегменті title")


def test_refs_unknown_ids(raw: dict) -> None:
    scene(raw, "s03")["location_id"] = "bar"
    scene(raw, "s03")["lines"][0]["character_id"] = "pedro"
    scene(raw, "s03")["clues"]["planted"].append("C99")
    errors = check_refs(Script.model_validate(raw), bible.load("la-garganta"))
    assert len(errors) == 3 and "bar" in errors[0] and "pedro" in errors[1] and "C99" in errors[2]


# ---------------------------------------------------------------- shots


def shot(sid: str, scene_id: str, dur: float, *labels: dict, segment: str = "main", **kw) -> dict:
    return {"id": sid, "scene_id": scene_id, "segment": segment, "duration_s": dur, "tier": "secondary",
            "action": "—", "labels": list(labels), **kw}


def shots_doc(*items: dict) -> dict:
    return {"story": "la-garganta", "part": 1, "shots": list(items)}


T1S, T1C = {"label": "TEASER_START", "n": 1}, {"label": "TEASER_CUT_BEFORE", "n": 1}
SCREAM = {"label": "SCREAMER"}


def base_shots() -> list[dict]:
    """Тизер 0 → 35 с, обрив перед скрімером; тиша за 5 с до удару; CLIFF у s08, далі чорний монтаж."""
    return [
        shot("sh01", "s01", 10, {"label": "HOOK_OPEN"}, T1S,
             dialogue=[{"text_es": "¡Graba!", "character_id": "chuy", "line_id": "l01"}]),
        shot("sh02", "s01", 10, dialogue=[{"text_es": "¿Oyeron eso?", "line_id": "l02"}]),
        shot("sh03", "s01", 10),
        shot("sh04", "s01", 5, sfx=[{"type": "silence", "at_s": 0}]),
        shot("sh05", "s01", 1.5, T1C, SCREAM, sfx=[{"type": "sting", "at_s": 0}]),
        shot("sh06", "s02", 4, segment="title", tier="still", reuse="plate:mina", overlay_text="LA GARGANTA"),
        shot("sh07", "s06", 8, {"label": "MIDPOINT"}),
        shot("sh08", "s08", 8, {"label": "CLIFF"}),
        shot("sh09", "s08", 3, tier="montage"),
        shot("sh10", "s09", 3, segment="end_card", tier="montage", overlay_text="Continuará…"),
    ]


def test_shots_valid_and_film_exclude() -> None:
    doc = Shots.model_validate(shots_doc(*base_shots()))
    assert shots_errors(doc) == []
    assert [s["film_exclude"] for s in doc.model_dump()["shots"]][-2:] == [False, True]


def test_cliff_counts_by_scene_not_shot() -> None:
    """CLIFF на 8.16, а за ним чорні шоти того самого біта — це нормально."""
    assert shots_errors(Shots.model_validate(shots_doc(*base_shots()))) == []


def test_shots_teaser_skips_recap() -> None:
    items = base_shots()
    items.insert(2, shot("rc1", "s01", 8, segment="recap"))     # +8 с рекапу всередині тизера
    assert shots_errors(Shots.model_validate(shots_doc(*items))) == []


@pytest.mark.parametrize("change, match", [
    (lambda s: s[4].update(duration_s=3), "SCREAMER-шот має тривати"),
    (lambda s: s[4].update(sfx=[]), "без звукового удару"),
    (lambda s: s[3].update(sfx=[]), "потрібна тиша або наростання"),
    (lambda s: s[2].update(duration_s=0.8), "лише для SCREAMER"),
    (lambda s: s[1].update(labels=[T1C]), "TEASER1: потрібна рівно одна пара"),
    (lambda s: [x.update(duration_s=5) for x in s[1:3]], "TEASER1: 25 с"),
])
def test_shots_rules(change, match: str) -> None:
    items = base_shots()
    change(items)
    errors = shots_errors(Shots.model_validate(shots_doc(*items)))
    assert any(match in e for e in errors), errors


@pytest.mark.parametrize("change, match", [
    (lambda s: s[0].update(duration_s=0.4), "greater than or equal to 0.5"),
    (lambda s: s[3].update(sfx=[{"type": "silence", "at_s": 7}]), "після кінця шота"),
    (lambda s: s[5].update(billed_seconds=4), "шот не генерується"),
    (lambda s: s[2].update(has_dialogue_visible=True), "без реплік"),
    (lambda s: s[5].update(reuse="plate:Mina!"), "String should match pattern"),
    (lambda s: s[2].update(tier="hd"), "Input should be"),
])
def test_shots_structure(change, match: str) -> None:
    items = base_shots()
    change(items)
    with pytest.raises(ValidationError, match=match):
        Shots.model_validate(shots_doc(*items))


def test_check_shots_against_script() -> None:
    script = Script.model_validate(PART1)
    shots = Shots.model_validate(shots_doc(*base_shots()))
    errors = check_shots(shots, script)
    assert any("TEASER2_START" in e for e in errors)              # TEASER2 зі script не перенесено
    assert any("репліка l03" in e for e in errors)                # репліки s03 не потрапили в шоти
    assert not any("l01" in e or "l02" in e for e in errors)

    items = base_shots()
    items[1]["dialogue"] = [{"text_es": "¿Cuánto tiempo…?", "line_id": "l05"}]   # репліка з чужої сцени
    items[2]["scene_id"] = "s99"
    errors = check_shots(Shots.model_validate(shots_doc(*items)), script)
    assert any("l05 не з сцени s01" in e for e in errors)
    assert any("невідома сцена s99" in e for e in errors)
