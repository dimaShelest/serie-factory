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


# ---------------------------------------------------------------- рев'ю A до PR #10: тест на кожну знахідку

STORY_TEXT = STORY.read_text(encoding="utf-8")
P1_B7 = next(line for line in STORY_TEXT.splitlines() if line.startswith("| 7 | 3:50"))


def parse_variant(tmp_path: Path, old: str, new: str) -> dict:
    assert old in STORY_TEXT, old
    path = tmp_path / "story.md"
    path.write_text(STORY_TEXT.replace(old, new, 1), encoding="utf-8")
    return story.parse(path)


def test_story_crlf_and_bom(tmp_path: Path) -> None:
    path = tmp_path / "story.md"
    path.write_bytes(("﻿" + STORY_TEXT).replace("\n", "\r\n").encode("utf-8"))
    parsed = story.parse(path)
    assert {n: len(b) for n, b in parsed.items()} == {n: len(b) for n, b in PARTS.items()}
    assert parsed[1][6].quotes == PARTS[1][6].quotes


def test_part4_stops_at_next_heading(tmp_path: Path) -> None:
    """(6) Таблиця після ч.4 (фільм, календар) не стає бітами ч.4."""
    path = tmp_path / "story.md"
    path.write_text(STORY_TEXT + "\n## Календар\n\n| 10 | 9:00–9:30 | хибний біт | `CLIFF` | |\n", encoding="utf-8")
    assert len(story.parse(path)[4]) == len(PARTS[4])


def test_pipe_in_beat_text_is_error(tmp_path: Path) -> None:
    """(7) `|` у тексті біта — помилка з рядком, а не тихо зниклий біт."""
    with pytest.raises(story.StoryFormatError, match=r"story\.md:\d+ \(ч\.1\).*комірок"):
        parse_variant(tmp_path, "Renata на виклику", "Renata | на виклику")


def test_label_names_in_comments_ignored(tmp_path: Path) -> None:
    """(8) «до CLIFF ще далеко» у тексті не робить мітку; лише `CLIFF` у бектиках."""
    parsed = parse_variant(tmp_path, P1_B7, P1_B7.replace("| | +C02", "| до CLIFF ще далеко | +C02"))
    assert parsed[1][6].labels == []


def test_unknown_label_in_backticks_is_error(tmp_path: Path) -> None:
    with pytest.raises(story.StoryFormatError, match="невідома мітка `HOT_2`"):
        parse_variant(tmp_path, "| `CLIFF` | +C02 |", "| `CLIFF` · `HOT_2` | +C02 |")


def test_label_time_ignores_3_17(tmp_path: Path) -> None:
    """(9) «(~3:34, перед стрілками на 3:17)» → 214 с, а не 197."""
    parsed = parse_variant(tmp_path, "(перед стрілками на 3:17, ~3:34)", "(~3:34, перед стрілками на 3:17)")
    assert ("TEASER2_CUT_BEFORE", 214) in parsed[1][5].labels


def test_two_approx_times_is_error(tmp_path: Path) -> None:
    with pytest.raises(story.StoryFormatError, match="кілька часів"):
        parse_variant(tmp_path, "(перед стрілками на 3:17, ~3:34)", "(~3:30, ~3:34)")


def test_label_time_outside_beat_is_error(tmp_path: Path) -> None:
    with pytest.raises(story.StoryFormatError, match="поза бітом"):
        parse_variant(tmp_path, "(перед стрілками на 3:17, ~3:34)", "(~4:34)")


def test_underscore_in_text_keeps_lines(tmp_path: Path) -> None:
    """(10) `C_04` у тексті не ковтає наступну репліку; *«…»* теж читається; вкладені «» не ріжуться."""
    parsed = parse_variant(tmp_path, "Mateo підбурює трьох:", "Mateo (код C_04) підбурює трьох:")
    assert parsed[1][2].quotes == PARTS[1][2].quotes
    parsed = parse_variant(tmp_path, "_«No tengo hambre.»_", "*«No tengo hambre.»*")
    assert "No tengo hambre." in parsed[1][2].quotes
    parsed = parse_variant(tmp_path, "_«No tengo hambre.»_", "_«No tengo «hambre».»_")
    assert "No tengo «hambre»." in parsed[1][2].quotes


def test_cyrillic_clue_is_error(tmp_path: Path) -> None:
    """(11) +С05 з кириличною С — помилка, а не тихо зникла підказка."""
    with pytest.raises(story.StoryFormatError, match="кирилична"):
        parse_variant(tmp_path, P1_B7, P1_B7.replace("+C05", "+С05"))


def test_unknown_clue_token_is_error(tmp_path: Path) -> None:
    with pytest.raises(story.StoryFormatError, match="незрозумілий токен"):
        parse_variant(tmp_path, P1_B7, P1_B7.replace("+C05", "+C5"))


def test_recap_word_in_comment_is_not_segment(tmp_path: Path) -> None:
    parsed = parse_variant(tmp_path, "| `HOOK_OPEN` · `TEASER1_START` (0:00) ·",
                           "| `HOOK_OPEN` (до рекапу) · `TEASER1_START` (0:00) ·")
    assert parsed[1][0].segment == "main"


def test_em_dash_in_beat_time(tmp_path: Path) -> None:
    parsed = parse_variant(tmp_path, "| 2 | 0:35–0:40 |", "| 2 | 0:35—0:40 |")
    assert (parsed[1][1].start_s, parsed[1][1].end_s) == (35, 40)


def test_script_and_shots_roundtrip() -> None:
    """(1) Script і Shots читаються назад з власного JSON."""
    script = Script.model_validate(PART1)
    assert Script.model_validate_json(script.model_dump_json()) == script
    shots = Shots.model_validate(shots_doc(*base_shots()))
    assert Shots.model_validate_json(shots.model_dump_json()) == shots


def test_screamer_on_teaser_start(raw: dict) -> None:
    """(3) SCREAMER рівно на TEASER_START — теж усередині тизера."""
    scene(raw, "s05")["labels"].append({"label": "SCREAMER", "approx_s": 175})
    rule(raw, "TEASER2: містить SCREAMER")


def test_untimed_screamer_beat_ending_at_cut(raw: dict) -> None:
    """(3) Біт без часу скрімера, що закінчується рівно на CUT, — усередині тизера."""
    scene(raw, "s05")["labels"] = [{"label": "TEASER_START", "n": 2, "approx_s": 140}, {"label": "SCREAMER"}]
    scene(raw, "s06")["labels"][1]["approx_s"] = 200          # CUT рівно на кінці s05
    rule(raw, "TEASER2: містить SCREAMER")


@pytest.mark.parametrize("durations, ok", [
    ([6.7, 7.0, 9.3, 5.8, 3.6, 2.2, 5.4], True),     # 40,0 з хвостом float
    ([10, 10, 10], True),                           # рівно 30,0
    ([10, 10, 9.9], False),
    ([10, 10, 10, 10, 1], False),                   # 41
])
def test_teaser_float_boundaries(durations: list[float], ok: bool) -> None:
    """(4) Межі 30,0 і 40,0 — включно, без хибних тривог через float."""
    items = [shot(f"t{i}", "s01", d, *([{"label": "HOOK_OPEN"}, T1S] if i == 0 else []))
             for i, d in enumerate(durations)]
    items[-1]["sfx"] = [{"type": "riser", "at_s": 0}]
    items += [shot("cut", "s01", 1.5, T1C, SCREAM, sfx=[{"type": "sting", "at_s": 0}]),
              shot("mid", "s06", 5, {"label": "MIDPOINT"}), shot("end", "s08", 5, {"label": "CLIFF"})]
    errors = shots_errors(Shots.model_validate(shots_doc(*items)))
    teaser = [e for e in errors if e.startswith("TEASER1:")]
    assert (teaser == []) == ok, teaser


def test_teasers_in_time_order(raw: dict) -> None:
    for sid, idx, n in (("s01", 1, 2), ("s01", 2, 2), ("s05", 0, 1), ("s06", 1, 1)):
        scene(raw, sid)["labels"][idx]["n"] = n
    rule(raw, "тизери мають іти в часі по порядку")


def test_scene_gaps_and_target(raw: dict) -> None:
    scene(raw, "s04")["approx_start_s"] = 105
    scene(raw, "s09")["approx_end_s"] = 480
    errors = script_errors(Script.model_validate(raw))
    assert any("s03 → s04: дірка" in e for e in errors)
    assert any("target_seconds" in e for e in errors)


def test_check_shots_missing_scenes_and_moved_labels() -> None:
    """(5) Сцени без шотів і мітка, перенесена в іншу сцену, — помилки."""
    script = Script.model_validate(PART1)
    errors = check_shots(Shots.model_validate(shots_doc(*base_shots())), script)
    assert any("сцена s03 (main) не має жодного шота" in e for e in errors)
    items = base_shots()
    items[6]["scene_id"] = "s07"                              # MIDPOINT переїхав з s06 у s07
    errors = check_shots(Shots.model_validate(shots_doc(*items)), script)
    assert any("мітка MIDPOINT сцени s06 не перенесена" in e for e in errors)
    assert any("мітка MIDPOINT у шотах сцени s07" in e for e in errors)


def test_label_line_must_be_in_shot() -> None:
    items = base_shots()
    items[7]["labels"] = [{"label": "CLIFF", "line_id": "l11"}]
    errors = check_shots(Shots.model_validate(shots_doc(*items)), Script.model_validate(PART1))
    assert any("на репліці l11, якої в шоті немає" in e for e in errors)
