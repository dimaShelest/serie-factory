"""Шот-спека (fabrica/shotspec.py): оверлей v2 / v1, успадкування сцени, групи, виведення, тест-пак, помилки."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import fabrica.shotspec as S
from fabrica import bible as bible_mod
from fabrica import prompts as P
from fabrica import shotlist as shotlist_mod
from fabrica.models import Script, Shot, Shots

ROOT = Path(__file__).resolve().parents[1]
SLUG = "la-garganta"
FIX = ROOT / "tests" / "fixtures" / "shotspec"
SCRIPT = ROOT / "tests" / "fixtures" / SLUG / "part1.script.json"


def _data() -> SimpleNamespace:
    """Мінімальна заміна prompts.Data: slug, en (англійський шар), groups."""
    raw = yaml.safe_load((FIX / "data.yaml").read_text(encoding="utf-8"))
    return SimpleNamespace(slug=SLUG, en=raw["en"], groups=raw["groups"])


@pytest.fixture
def data() -> SimpleNamespace:
    return _data()


@pytest.fixture
def out_root(tmp_path: Path) -> Path:
    """output/<slug>/part1 з shots.json і script.json фікстур."""
    folder = tmp_path / "out" / SLUG / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIX / "shots.json", folder / "shots.json")
    shutil.copy(SCRIPT, folder / "script.json")
    return tmp_path / "out"


def _specs(data, out_root: Path, overlay: Path) -> dict[str, S.ShotSpec]:
    return {s.id: s for s in S.part_specs(data, 1, out_root=out_root, overlay=overlay)}


def _write(tmp_path: Path, text: str, name: str = "part1_prompts_en.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _err(fn, *args, **kw) -> str:
    with pytest.raises(S.SpecError) as e:
        fn(*args, **kw)
    return str(e.value)


# ---------------------------------------------------------------- чисті функції


@pytest.mark.parametrize(("edit", "gen"), [(0.5, 4), (1, 4), (4.0, 4), (4.2, 5), (5.0, 5), (8, 8), (10, 10), (40, 30)])
def test_gen_seconds(edit: float, gen: int) -> None:
    assert S.gen_seconds(edit) == gen


def test_gen_seconds_route_max_and_float_noise() -> None:
    assert S.gen_seconds(14.5, route_max=12) == 12
    assert S.gen_seconds(5.0000000001) == 5                 # хвіст float не додає секунду


@pytest.mark.parametrize(("tier", "reuse", "mode", "want"), [
    ("hero", None, None, "i2v"), ("hero", None, "t2v", "t2v"), ("secondary", None, "first_last", "first_last"),
    ("still", None, None, "still"), ("still", None, "t2v", "still"), ("still", "plate:mina", None, "none"),
    ("montage", None, "i2v", "none"), ("hero", "shot:6.04", None, "none"),
    ("found_footage", "asset:props", None, "none"),
])
def test_derive_mode(tier: str, reuse: str | None, mode: str | None, want: str) -> None:
    assert S.derive_mode(tier, reuse, mode) == want


@pytest.mark.parametrize(("views", "size", "want"), [
    (["face"], "medium", "clear"), (["three_quarter"], None, "clear"), (["face"], "close-up", "clear"),
    # анфас на загальному — теж clear: Replicate відхиляє фронтальне обличчя будь-якого розміру (§6.2 п.3, C1)
    (["face"], "wide", "clear"), (["face"], "extreme wide", "clear"),
    (["three_quarter"], "Wide, seen from the doorway", "clear"),
    (["back", "face"], "wide", "clear"), (["back", "face"], "medium close-up", "clear"),
    (["profile"], "medium", "partial"), (["distant"], "close-up", "partial"), (["back", "profile"], "wide", "partial"),
    (["distant", "back"], "extreme wide", "partial"),
    (["back"], "medium", "none"), (["silhouette", "blurred", "hidden"], "close-up", "none"), ([], "medium", "none"),
])
def test_derive_face(views: list[str], size: str | None, want: str) -> None:
    people = [S.Person(id=f"p{i}", view=v) for i, v in enumerate(views)]
    assert S.derive_face(people, S.Camera(size=size)) == want == S.derive_face(people)


@pytest.mark.parametrize(("text", "want"), [
    ("¡Chuy, graba, graba! Esto va para el anuario.", "shout"), ("¡¿Lo están grabando?!", "shout"),
    ("¿Oyeron eso?", "normal"), ("…encontraron sin vida a don Rufino Castillo…", "normal"), ("Bueno...", "normal"),
    ("Yo voy.", None), ("No toquen nada.", None),
])
def test_guess_delivery_never_whisper(text: str, want: str | None) -> None:
    assert S.guess_delivery(text) == want


def test_expand_people_groups_state_and_dedupe() -> None:
    groups = {"los_cuatro": ["vale", "diego", "sofia", "mateo"]}
    entries = [S.Person(id="vale", view="back", screen="left"),
               S.Person(id="los_cuatro", view="profile", screen="right", state=["dusty"])]
    out = S.expand_people(entries, groups, {"los_cuatro": ["nosebleed"], "vale": ["wet"], "mateo": []})
    assert [p.id for p in out] == ["vale", "diego", "sofia", "mateo"]
    assert (out[0].view, out[0].screen) == ("back", "left")                    # явний запис виграє в групи
    assert all(p.view == "profile" and p.screen is None for p in out[1:])     # учасники групи — без screen
    assert out[0].state == ["nosebleed", "wet"] and out[1].state == ["nosebleed", "dusty"]
    # «четвірка, але Vale спиною»: група перша — явний запис однаково виграє
    out = S.expand_people([S.Person(id="los_cuatro", view="profile"), S.Person(id="vale", view="back", screen="left")],
                          groups)
    assert [(p.id, p.view, p.screen) for p in out] == [
        ("diego", "profile", None), ("sofia", "profile", None), ("mateo", "profile", None), ("vale", "back", "left")]
    assert S.derive_face(out) == "partial"


def test_person_state_string_and_camera_text() -> None:
    assert S.Person(id="beto", state="wet").state == ["wet"]
    shot = S.ShotIn.model_validate({"camera": "slow steady push-in", "people": ["vale", {"id": "beto"}]})
    assert shot.camera.text == "slow steady push-in" and shot.camera.move == "static"
    assert [p.id for p in shot.people] == ["vale", "beto"] and shot.people[0].view == "face"
    assert S.Camera(text="slow pan", size="wide", angle="low angle").size == "wide"     # статичні поля — можна
    for bad in ({"text": "slow pan", "move": "pan_left"}, {"text": "x", "speed": "slow"},
                {"text": "x", "endpoint": "y"}):
        with pytest.raises(ValueError, match="не обидва"):
            S.Camera(**bad)
    with pytest.raises(ValueError, match="рядком або словником"):
        S.ShotIn.model_validate({"camera": 5})


def _shot(**kw) -> Shot:
    return Shot.model_validate({"id": "9.01", "scene_id": "s09", "duration_s": 4, "tier": "hero", "action": "x", **kw})


def test_derive_lines_precedence_and_on_screen() -> None:
    sh = _shot(has_dialogue_visible=True, dialogue=[
        {"text_es": "Ni se te ocurra.", "character_id": "vale", "line_id": "l1"},
        {"text_es": "¡Mírenme!", "character_id": "diego"},
        {"text_es": "Por aquí.", "character_id": "mateo", "line_id": "l3"},
        {"text_es": "¿Quién?", "character_id": "sofia", "offscreen": True},
        {"text_es": "Hola.", "character_id": "renata"}])
    people = [S.Person(id="vale"), S.Person(id="diego", view="back"), S.Person(id="mateo", view="profile"),
              S.Person(id="sofia")]
    lines, warn = S.derive_lines(sh, people, {"l1": "whisper", "l3": "normal"},
                                 {1: S.LineIn(delivery="shout"), 2: S.LineIn(on_screen=True),
                                  3: S.LineIn(delivery="quiet_fear", on_screen=False), 4: S.LineIn(on_screen=True)})
    got = [(ln.n, ln.delivery, ln.delivery_source, ln.on_screen) for ln in lines]
    assert got == [(1, "whisper", "script", True),       # script виграє в оверлею → попередження
                   (2, "shout", "guess", False),         # спиною до камери — on_screen з оверлею неможливий
                   (3, "quiet_fear", "overlay", False),  # script normal = не задано; оверлей вимикає on_screen
                   (4, "normal", "guess", False),        # за кадром — on_screen з оверлею неможливий
                   (5, "normal", "default", False)]      # не в people
    assert lines[3].offscreen and lines[0].line_id == "l1" and lines[0].speaker == "vale"
    assert len(warn) == 3 and "репліка 1" in warn[0] and "whisper" in warn[0]
    assert "репліка 2" in warn[1] and "рота мовця не видно" in warn[1]
    assert "репліка 4" in warn[2] and "за кадром" in warn[2]


def test_derive_lines_needs_visible_dialogue_flag() -> None:
    sh = _shot(dialogue=[{"text_es": "Yo voy.", "character_id": "vale"}])
    lines, _ = S.derive_lines(sh, [S.Person(id="vale")])
    assert not lines[0].on_screen and lines[0].delivery_source == "default"


def test_plate_and_light_time(data) -> None:
    assert S.plate_time(data, "mina") == "night" and S.plate_time(data, "mina", "dawn") == "dawn"
    assert S.plate_time(data, "mina", "tunnel") is None                     # replace без time — інше місце
    assert S.plate_time(data, "casa_minero", "ceiling") == "night"         # стан-рядок v1 → time локації
    assert S.light_time("warm daylight through the broken windows") == "day"
    assert S.light_time("dawn, warm low sunrise light") == "dawn" and S.light_time("night, phone lights") == "night"
    assert S.light_time("a single cold flashlight beam") is None and S.light_time(None) is None


def test_time_clash_points_to_existing_variant(data) -> None:
    t, w = S._time(data, "casa_vale", "living", None, "daylight through the window")
    assert t == "day" and "casa_vale.living" in w[0] and "візьми variant living_day" in w[0]
    _, w = S._time(data, "mina", "dawn", "night", None)                     # плита mina — ніч
    assert "візьми плиту без variant" in w[0]
    _, w = S._time(data, "casa_minero", "ceiling", None, "warm daylight")    # денного стану немає
    assert "потрібен окремий денний стан локації" in w[0]
    assert S._time(data, "mina", "dawn", None, "dawn light") == ("dawn", [])


def test_spec_refs_and_edit_window(data, out_root: Path) -> None:
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    sp = by["1.07"]
    assert (sp.prefix, sp.frame_ref, sp.end_ref) == ("p1-1.07", "p1.1.07.frame", "p1.1.07.end")
    assert S.edit_window(sp) == "кліп 4 с → у монтаж 1 с" and S.edit_window(by["3.13"]) is None


# ---------------------------------------------------------------- оверлей v2


def test_load_overlay_v2_shape() -> None:
    ov = S.load_overlay(SLUG, 1, FIX / "overlay_v2.yaml")
    assert ov["version"] == 2 and ov["path"].name == "overlay_v2.yaml"
    assert set(ov["scenes"]) == {"4", "s08"} and "4.03" in ov["shots"]
    assert ov["scenes"]["4"].state["sofia"] == ["nosebleed"]                 # рядок → список
    assert ov["shots"]["1.04"].lines[1].delivery == "shout"


def test_load_overlay_missing_or_empty(tmp_path: Path) -> None:
    assert S.load_overlay(SLUG, 1, tmp_path / "nope.yaml") == {}
    assert S.load_overlay(SLUG, 1, _write(tmp_path, "# порожньо\n")) == {}


def test_part_specs_v2_scene_inheritance(data, out_root: Path) -> None:
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    assert list(by) == [sh["id"] for sh in yaml.safe_load((FIX / "shots.json").read_text(encoding="utf-8"))["shots"]]
    sp = by["4.03"]
    assert (sp.set, sp.title, sp.scene_id, sp.tier, sp.beat, sp.mode) == (
        "1", "Ч.1 · 4.03", "s04", "hero", "establish", "i2v")
    assert (sp.edit_s, sp.gen_s, sp.location, sp.variant, sp.time) == (8, 8, "mina", "dawn", "dawn")
    assert sp.light == "warm low sunrise light through thin mist"
    assert [(p.id, p.view, p.screen) for p in sp.people] == [
        ("vale", "back", "left"), ("mateo", "face", None), ("diego", "face", None), ("sofia", "face", None)]
    assert {p.id: p.state for p in sp.people} == {"vale": ["nosebleed"], "mateo": [], "diego": ["nosebleed"],
                                                  "sofia": ["nosebleed"]}
    assert sp.camera.size == "wide" and sp.camera.move == "push_in" and sp.camera.speed == "very slow"
    assert sp.face == "clear"                          # анфас на загальному → маршрут з обличчям (§6.2 п.3)
    assert sp.sound.ambience == ["soft mountain wind"] and sp.sound.sfx == ["a low rumble from the mountain"]
    assert sp.continuity == ["hundreds of small grey pebbles hang motionless in the air at different heights",
                             "the mine entrance stays dark"]
    assert sp.end_state == "The pebbles still hang in the air." and sp.end_frame is None
    assert sp.warnings == [] and sp.footage is None and sp.lines == []


def test_part_specs_v2_null_overrides_scene_and_first_last(data, out_root: Path) -> None:
    sp = _specs(data, out_root, FIX / "overlay_v2.yaml")["4.06"]
    assert (sp.mode, sp.variant, sp.face, sp.gen_s, sp.edit_s) == ("first_last", None, "none", 5, 4.2)
    assert sp.end_frame.startswith("Mateo stands") and sp.people[0].state == []
    assert sp.time == "dawn" and any("візьми variant dawn" in w and "mina.plate" in w for w in sp.warnings)


def test_part_specs_v2_lines_and_people(data, out_root: Path) -> None:
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    ln = by["4.04"].lines[0]                                                 # l05 у script без delivery
    assert (ln.delivery, ln.delivery_source, ln.on_screen, ln.line_id) == ("quiet_fear", "overlay", True, "l05")
    ln = by["1.04"].lines[0]                                                 # l02: script whisper > оверлей shout
    assert (ln.delivery, ln.delivery_source, ln.on_screen) == ("whisper", "script", False)
    assert by["1.04"].people == [] and any("не діє" in w for w in by["1.04"].warnings)
    assert any("people порожній" in w and "los_siete" in w for w in by["1.04"].warnings) and by["1.04"].face == "none"
    ln = by["8.12"].lines[0]
    assert (ln.delivery, ln.delivery_source, ln.on_screen) == ("whisper", "script", False)   # оверлей вимкнув
    sp = by["8.06"]
    assert sp.light == "daylight through the window" and sp.time == "day" and sp.face == "none"
    assert any("візьми variant living_day" in w for w in sp.warnings)        # плита living — ніч
    assert sp.lines[0].offscreen and not sp.lines[0].on_screen and sp.lines[0].delivery_source == "guess"
    sp = by["1.07"]
    assert sp.people[0].state == ["wet"] and sp.face == "clear" and sp.footage == "vhs" and sp.beat == "scare"
    assert sp.camera.size == "extreme close-up" and sp.camera.shake == "strong" and sp.camera.move == "handheld"


def test_part_specs_no_overlay_entry_falls_back_to_ukrainian(data, out_root: Path) -> None:
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    sp = by["1.02"]
    assert sp.frame.startswith("[UA → EN] ") and sp.action.startswith("[UA → EN] ")
    assert sp.camera.text == "[UA → EN] VHS, з рук" and sp.camera.size is None
    assert any("немає англійського опису" in w for w in sp.warnings)
    assert [p.id for p in sp.people] == ["lupita", "monica", "ivan"] and sp.face == "clear"
    assert (sp.lines[0].delivery, sp.lines[0].delivery_source) == ("shout", "script")
    sp = by["7.08"]                                                          # напарник без опису в prompt_en
    assert sp.people == [] and any("policia_companero" in w for w in sp.warnings)


def test_part_specs_not_generated_shots(data, out_root: Path) -> None:
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    for sid in ("2.01", "3.13", "8.17"):
        sp = by[sid]
        assert (sp.mode, sp.gen_s, sp.frame, sp.action, sp.warnings) == ("none", 0, "", "", []), sid
    assert by["3.13"].notes == ["лише звук"] and by["3.13"].location == ""
    ln = by["8.17"].lines[0]
    assert (ln.text_es, ln.offscreen, ln.on_screen, ln.delivery_source) == ("Hola.", True, False, "default")


def test_script_written_by_code_keeps_overlay_delivery(data, out_root: Path) -> None:
    """script.json з model_dump_json() має delivery: normal у кожній репліці — це «не задано», діє оверлей."""
    path = out_root / SLUG / "part1" / "script.json"
    path.write_text(Script.model_validate_json(path.read_text(encoding="utf-8")).model_dump_json(),
                    encoding="utf-8", newline="\n")
    assert '"delivery":"normal"' in path.read_text(encoding="utf-8")
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    ln = by["4.04"].lines[0]
    assert (ln.delivery, ln.delivery_source) == ("quiet_fear", "overlay")
    assert not any("не діє" in w for w in by["4.04"].warnings)
    assert (by["1.04"].lines[0].delivery, by["1.04"].lines[0].delivery_source) == ("whisper", "script")


def test_on_screen_line_forces_face_route(data, out_root: Path, tmp_path: Path) -> None:
    """Рот у кадрі → face clear навіть у профіль (§6.2 п.4); on_screen оверлею всупереч рядку — попередження."""
    text = ("version: 2\nshots:\n"
            "  \"4.04\": {people: [{id: sofia, view: profile}], frame: a, action: b}\n"
            "  \"8.12\": {people: [{id: vale, view: three_quarter}], frame: a, action: b, face: partial}\n"
            "  \"8.06\": {variant: living_day, people: [{id: vale, view: back}], frame: a, action: b,\n"
            "           lines: {1: {on_screen: true}}}\n")
    by = _specs(data, out_root, _write(tmp_path, text))
    assert by["4.04"].lines[0].on_screen and by["4.04"].face == "clear"
    sp = by["8.12"]
    assert sp.lines[0].on_screen and sp.face == "partial"                   # явний face лишається, але
    assert any("on_screen" in w and "face clear" in w for w in sp.warnings)  # з попередженням
    sp = by["8.06"]
    assert not sp.lines[0].on_screen and sp.face == "none"
    assert any("on_screen з оверлею неможливий" in w and "за кадром" in w for w in sp.warnings)


def test_not_generated_shots_ignore_overlay_fields(data, out_root: Path, tmp_path: Path) -> None:
    """Шот без відео: end_frame / action / §12 не йдуть у спеку (з попередженням); місце й час не перевіряються."""
    text = ("version: 2\nscenes:\n  \"2\": {time: day, variant: sunset}\n"
            "shots:\n  \"2.01\": {mode: first_last, frame: a, end_frame: b, action: c, window: [0, 1]}\n")
    sp = _specs(data, out_root, _write(tmp_path, text))["2.01"]                # still + plate:mina → none
    assert (sp.mode, sp.frame, sp.end_frame, sp.action, sp.window, sp.time) == ("none", "", None, "", None, "day")
    assert sp.variant == "sunset" and len(sp.warnings) == 1
    assert sp.warnings[0].startswith("mode, frame, end_frame, action, window з оверлею не діють: шот не генерується")
    path = out_root / SLUG / "part1" / "shots.json"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["shots"][3]["reuse"] = None                                           # 2.01 → still
    path.write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8", newline="\n")
    text = "version: 2\nshots:\n  \"2.01\": {mode: first_last, frame: a, end_frame: b, action: c, end_state: d}\n"
    sp = _specs(data, out_root, _write(tmp_path, text))["2.01"]
    assert (sp.mode, sp.frame, sp.end_frame, sp.action, sp.end_state, sp.gen_s) == ("still", "a", None, "", None, 0)
    assert any(w.startswith("mode, end_frame, action, end_state з оверлею не діють: шот still") for w in sp.warnings)


def test_clip_fields_pass_to_spec(data, out_root: Path, tmp_path: Path) -> None:
    """§12: window / event_s / clips / handoff читаються й ідуть у спеку (розбивка на кліпи — окрема фаза)."""
    text = ("version: 2\nshots:\n  \"1.07\": {variant: tunnel, frame: a, action: b, window: [1.5, 2.5], event_s: 2,\n"
            "    handoff: continue, clips: [{action: c, camera: handheld jolt}, {action: d, end_state: e,\n"
            "    camera: {move: pull_out}}]}\n")
    sp = _specs(data, out_root, _write(tmp_path, text))["1.07"]
    assert (sp.window, sp.event_s, sp.handoff) == ((1.5, 2.5), 2, "continue")
    assert [(c.action, c.end_state) for c in sp.clips] == [("c", None), ("d", "e")]
    assert sp.clips[0].camera.text == "handheld jolt" and sp.clips[1].camera.move == "pull_out"
    assert (sp.window, sp.clips, sp.handoff) != (None, [], "cut")
    by = _specs(data, out_root, FIX / "overlay_v2.yaml")
    assert (by["4.03"].window, by["4.03"].event_s, by["4.03"].clips, by["4.03"].handoff) == (None, None, [], "cut")


def test_supporting_with_look_can_be_in_people(data, out_root: Path, tmp_path: Path) -> None:
    """supporting з tag / look — у people (лише текстом); лише з голосом — невідомий для кадру."""
    data.en["supporting"] = {"policia_companero": {"tag": "the heavy-set policeman", "look": "heavy-set"},
                             "conductora_noticias": {"voice_design": "Native Spanish (Mexico City)."}}
    sp = _specs(data, out_root, FIX / "overlay_v2.yaml")["7.08"]
    assert [p.id for p in sp.people] == ["policia_companero"] and not any("без опису" in w for w in sp.warnings)
    text = "version: 2\nshots:\n  \"7.08\": {people: [{id: policia_companero, view: back}], frame: a, action: b}\n"
    assert _specs(data, out_root, _write(tmp_path, text))["7.08"].people[0].view == "back"
    msg = _err(S.part_specs, data, 1, out_root=out_root, overlay=_write(
        tmp_path, "version: 2\nshots:\n  \"8.06\": {people: [conductora_noticias]}\n"))
    assert "«conductora_noticias»" in msg


def test_part_specs_missing_overlay_file(data, out_root: Path, tmp_path: Path) -> None:
    by = _specs(data, out_root, tmp_path / "absent.yaml")
    assert all("немає англійського опису" in " ".join(s.warnings) for s in by.values() if s.mode != "none")
    assert by["4.03"].people[0].id == "vale" and by["4.03"].variant is None


def test_part_specs_missing_shots(data, tmp_path: Path) -> None:
    assert "fabrica shotlist" in _err(S.part_specs, data, 1, out_root=tmp_path)


# ---------------------------------------------------------------- оверлей v1


def test_overlay_v1_converts(data, out_root: Path) -> None:
    ov = S.load_overlay(SLUG, 1, FIX / "overlay_v1.yaml")
    assert ov["version"] == 1 and ov["scenes"] == {}
    by = _specs(data, out_root, FIX / "overlay_v1.yaml")
    sp = by["1.07"]
    assert sp.frame.startswith("In the flashlight beam") and sp.people[0].state == ["wet"]
    assert sp.camera.size == "extreme close-up" and sp.camera.text == "handheld VHS camcorder, a sharp jolt backwards"
    sp = by["4.03"]
    assert [p.id for p in sp.people] == ["vale", "diego", "sofia", "mateo"] and sp.variant == "dawn"
    assert sp.camera.size == "wide" and sp.camera.text == "slow steady push-in" and sp.face == "clear"
    assert by["8.06"].camera.size == "over the shoulder" and by["8.06"].light == "daylight through the window"


def test_real_overlay_and_shotlist_part1() -> None:
    """Справжні part1_shotlist.md + part1_prompts_en.yaml (v1 або v2): кожен шот, що генерується, має frame і action."""
    data = P.Data(SLUG)
    script = Script.model_validate_json(SCRIPT.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(ROOT / "series" / SLUG / "part1_shotlist.md", bible_mod.load(SLUG), 1, script)
    shots = Shots.model_validate(raw)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / SLUG / "part1"
        folder.mkdir(parents=True)
        (folder / "shots.json").write_text(shots.model_dump_json(), encoding="utf-8", newline="\n")
        shutil.copy(SCRIPT, folder / "script.json")
        specs = S.part_specs(data, 1, out_root=Path(tmp))
    assert [s.id for s in specs] == [sh.id for sh in shots.shots]
    for sp in specs:
        if sp.mode != "none":
            assert sp.frame and "[UA" not in sp.frame and sp.location, sp.id
        if sp.mode in S.VIDEO_MODES:
            assert sp.action and "[UA" not in sp.action and sp.gen_s >= 4, sp.id
    assert sum(len(s.lines) for s in specs) == sum(len(sh.dialogue) for sh in shots.shots)
    chuy = next(ln for s in specs for ln in s.lines if ln.text_es.startswith("¡Chuy"))
    assert (chuy.delivery, chuy.delivery_source) == ("shout", "script")


# ---------------------------------------------------------------- помилки оверлею


@pytest.mark.parametrize(("text", "needles"), [
    ("version: 2\nshots:\n  \"4.03\": {composition: x}\n", ["шот 4.03", "composition", "зайве поле"]),
    ("version: 2\nshots:\n  \"4.03\": {camera: {move: zoom}}\n", ["шот 4.03", "camera.move", "«zoom»", "push_in"]),
    ("version: 2\nshots:\n  \"4.03\": {people: [{id: vale, view: front}]}\n",
     ["people.0.view", "«front»", "three_quarter"]),
    ("version: 2\nshots:\n  \"4.03\": {mode: first_last}\n", ["шот 4.03", "end_frame"]),
    ("version: 2\nshots:\n  \"4.03\": {end_frame: x}\n", ["end_frame лише для mode first_last"]),
    ("version: 2\nshots:\n  \"4.03\": {mode: still}\n", ["mode", "«still»"]),
    ("version: 2\nshots:\n  \"4.03\": {lines: {1: {delivery: mumble}}}\n", ["lines.1.delivery", "«mumble»"]),
    ("version: 2\nshots:\n  \"4.03\": {camera: {lens_mm: wide}}\n", ["camera.lens_mm", "цілим числом"]),
    ("version: 2\nshots:\n  \"4.03\": {continuity: one fact}\n", ["continuity", "списком"]),
    ("version: 2\nshots:\n  \"4.03\": nope\n", ["шот 4.03", "словником"]),
    ("version: 2\nshots:\n  4.10: {frame: x}\n", ["«4.1»", "без лапок"]),
    ("version: 2\nscenes:\n  \"4\": {time: noon}\n", ["сцена 4", "time", "«noon»"]),
    ("version: 2\nscenes:\n  \"4\": {frame: x}\n", ["сцена 4", "frame", "зайве поле"]),
    ("version: 2\nshot: {}\n", ["зайві ключі", "shot"]),
    ("version: 2\nshots: [a, b]\n", ["shots має бути словником"]),
    ("version: 3\nshots: {}\n", ["version 3"]),
    ("\"4.03\": {beat: scare, composition: x}\n", ["шот 4.03", "beat", "version: 2"]),
    ("- just\n- a list\n", ["очікую словник"]),
    ("version: 2\nshots: {\"4.03\": [unclosed\n", ["зламаний YAML"]),
    # змішані типи ключів YAML (4.03 без лапок — число) — SpecError, не TypeError
    ("shots:\n  4.03: {frame: x}\n  \"4.04\": {frame: y}\n", ["є shots", "немає version: 2"]),
    ("\"4.03\": {1: x, composition: y}\n", ["шот 4.03", "[1]", "не з v1"]),
    ("version: 2\nshots: {}\n4.03: {frame: x}\n\"4.04\": {frame: y}\n", ["зайві ключі", "4.03", "4.04"]),
    ("version: 2\nshots:\n  \"4.03\": {camera: 5}\n", ["шот 4.03", "camera: має бути рядком або словником"]),
    ("\"4.03\": {composition: x, framing: Wide, camera: 5}\n", ["шот 4.03", "рядком або словником"]),
    ("version: 2\nshots:\n  \"4.03\": {camera: {text: slow push, move: push_in}}\n",
     ["шот 4.03", "camera", "не обидва"]),
    ("version: 2\nshots:\n  \"4.03\": {window: [2, 1]}\n", ["шот 4.03", "window", "початок < кінець"]),
    ("version: 2\nshots:\n  \"4.03\": {window: [1, 2], event_s: 3}\n", ["шот 4.03", "event_s 3 поза window"]),
    ("version: 2\nshots:\n  \"4.03\": {clips: [{end_state: x}]}\n", ["шот 4.03", "clips.0.action", "бракує поля"]),
    ("version: 2\nshots:\n  \"4.03\": {handoff: fade}\n", ["шот 4.03", "«fade»", "continue"]),
])
def test_overlay_errors_name_file_and_shot(tmp_path: Path, text: str, needles: list[str]) -> None:
    msg = _err(S.load_overlay, SLUG, 1, _write(tmp_path, text))
    assert "part1_prompts_en.yaml" in msg
    for n in needles:
        assert n in msg, (n, msg)


def test_overlay_v1_dict_camera_is_validated(tmp_path: Path) -> None:
    """v1 знав лише рядок camera; словник у v1 перевіряється як v2-камера."""
    text = "\"4.03\": {composition: x, framing: Wide, camera: {move: push_in}}\n"
    ov = S.load_overlay(SLUG, 1, _write(tmp_path, text))
    cam = ov["shots"]["4.03"].camera
    assert (cam.move, cam.size) == ("push_in", "wide")


def test_overlay_errors_are_collected(tmp_path: Path) -> None:
    msg = _err(S.load_overlay, SLUG, 1, _write(tmp_path, (
        "version: 2\nshots:\n  \"4.03\": {beat: boo}\n  \"4.04\": {face: hidden}\n")))
    assert "шот 4.03" in msg and "шот 4.04" in msg and len(msg.splitlines()) == 2


@pytest.mark.parametrize(("text", "needles"), [
    ("version: 2\nshots:\n  \"9.99\": {frame: x}\n", ["шот 9.99", "немає в shots.json"]),
    ("version: 2\nscenes:\n  \"5\": {time: day}\n", ["сцена 5", "немає в shots.json", "s04"]),
    ("version: 2\nscenes:\n  \"4\": {time: day}\n  s04: {time: dawn}\n", ["сцена s04 задана двічі"]),
    ("version: 2\nshots:\n  \"4.03\": {people: [vael]}\n", ["шот 4.03", "невідомий персонаж «vael»"]),
    ("version: 2\nscenes:\n  \"4\": {state: {vael: [wet]}}\n", ["сцена 4", "«vael»"]),
    ("version: 2\nscenes:\n  \"4\": {state: {vale: [bleeding]}}\n",
     ["сцена 4", "невідомий стан «bleeding»", "nosebleed"]),
    ("version: 2\nshots:\n  \"4.03\": {people: [{id: beto, state: [soaked]}]}\n", ["шот 4.03", "«soaked»"]),
    ("version: 2\nshots:\n  \"4.03\": {variant: sunset}\n", ["шот 4.03", "немає стану «sunset»", "dawn, tunnel"]),
    ("version: 2\nscenes:\n  \"4\": {variant: sunset}\n", ["шот 4.03", "шот 4.04", "«sunset»"]),
    ("version: 2\nshots:\n  \"4.03\": {location: atlantis}\n", ["шот 4.03", "локації «atlantis»"]),
    ("version: 2\nshots:\n  \"4.04\": {lines: {2: {delivery: shout}}}\n", ["шот 4.04", "lines [2]"]),
    ("version: 2\nshots:\n  \"4.03\": {lines: {1: {delivery: shout}}}\n", ["шот 4.03", "lines [1]", "0 реплік"]),
    ("version: 2\nshots:\n  \"4.03\": {people: [vale, {id: vale, view: back}]}\n",
     ["шот 4.03", "«vale» у people двічі"]),
    ("version: 2\nshots:\n  \"7.08\": {people: [policia_companero]}\n", ["шот 7.08", "«policia_companero»"]),
])
def test_part_specs_cross_checks(data, out_root: Path, tmp_path: Path, text: str, needles: list[str]) -> None:
    msg = _err(S.part_specs, data, 1, out_root=out_root, overlay=_write(tmp_path, text))
    assert "part1_prompts_en.yaml" in msg
    for n in needles:
        assert n in msg, (n, msg)


def test_unknown_state_reported_once(data, out_root: Path, tmp_path: Path) -> None:
    """Стан сцени перевіряється на сцені, не ще раз у кожному шоті; стан групи — один раз, не на кожного."""
    msg = _err(S.part_specs, data, 1, out_root=out_root, overlay=_write(tmp_path, (
        "version: 2\nscenes:\n  \"4\": {state: {vale: [bleeding]}}\n"
        "shots:\n  \"4.03\": {people: [{id: los_cuatro, state: [soaked]}]}\n")))
    assert msg.count("«bleeding»") == 1 and "сцена 4" in msg
    assert msg.count("«soaked»") == 1 and "у los_cuatro" in msg


def test_states_unchecked_without_states_in_prompt_en(data, out_root: Path, tmp_path: Path) -> None:
    """Старий prompt_en.yaml без states: стан не перевіряємо (міграція), спека будується."""
    del data.en["states"]
    text = "version: 2\nshots:\n  \"4.03\": {people: [{id: vale, state: wet}]}\n"
    sp = _specs(data, out_root, _write(tmp_path, text))
    assert sp["4.03"].people[0].state == ["wet"]


def test_generated_shot_without_location(data, out_root: Path, tmp_path: Path) -> None:
    path = out_root / SLUG / "part1" / "shots.json"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["shots"][5]["location_id"] = None                                    # 4.03
    path.write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8", newline="\n")
    msg = _err(S.part_specs, data, 1, out_root=out_root, overlay=FIX / "overlay_v1.yaml")
    assert "шот 4.03" in msg and "без локації" in msg
    text = "version: 2\nshots:\n  \"4.03\": {location: mina, frame: x, action: y}\n"
    sp = _specs(data, out_root, _write(tmp_path, text))
    assert sp["4.03"].location == "mina"


def test_broken_shots_json_is_spec_error(data, out_root: Path) -> None:
    (out_root / SLUG / "part1" / "shots.json").write_text('{"story": "la-garganta", "part": 1, "shots": []}',
                                                          encoding="utf-8")
    assert "shots.json" in _err(S.part_specs, data, 1, out_root=out_root, overlay=FIX / "overlay_v2.yaml")


def test_spec_is_strict() -> None:
    with pytest.raises(ValueError):
        S.Camera(move="push_in", zoom=2)
    with pytest.raises(ValueError):
        S.Person(id="vale", view="front")


# ---------------------------------------------------------------- тест-пак


def test_test_pack_legacy(data) -> None:
    specs = S.test_pack_specs(data, FIX / "test_pack_v1.yaml")
    by = {s.id: s for s in specs}
    assert list(by) == ["T1", "T2", "T3", "T4", "T4-face", "T5"]
    assert all(s.set == "test-pack" and s.scene_id is None and s.lines == [] for s in specs)
    t1 = by["T1"]
    assert (t1.prefix, t1.frame_ref, t1.video_id, t1.tier, t1.mode) == ("tp-T1", "tp.T1.frame", "video", "hero", "i2v")
    assert (t1.edit_s, t1.gen_s, t1.camera.size, t1.camera.text) == (8, 8, "wide", "slow steady push-in")
    assert t1.frame.startswith("Four young adults") and t1.action.startswith("The hundreds")
    assert t1.light == "dawn, warm low sunrise light through mist" and t1.time == "dawn" and t1.face == "clear"
    assert t1.success and t1.success == by["T1"].success
    t4 = by["T4"]
    assert (t4.video_id, t4.tier, t4.footage, t4.face, t4.people) == ("buildup", "found_footage", "vhs", "none", [])
    face = by["T4-face"]
    assert (face.prefix, face.frame_ref, face.edit_s, face.gen_s) == ("tp-T4-face", "tp.T4.face.frame", 2, 4)
    assert face.people[0].id == "beto" and face.people[0].state == ["wet"] and face.face == "clear"
    assert face.title.endswith("(face)") and face.success == t4.success
    assert by["T2"].tier == "hero" and by["T2"].face == "clear" and by["T5"].tier == "found_footage"
    assert by["T5"].footage == "phone" and by["T5"].time == "night"


def test_test_pack_new_keys(data) -> None:
    by = {s.id: s for s in S.test_pack_specs(data, FIX / "test_pack_v2.yaml")}
    t1 = by["T1"]
    assert [(p.id, p.view, p.screen) for p in t1.people] == [
        ("vale", "back", "left"), ("diego", "face", None), ("sofia", "face", None), ("mateo", "face", None)]
    cam = t1.camera
    assert (cam.size, cam.angle, cam.lens_mm, cam.move, cam.speed, cam.text) == (
        "wide", "eye level", 35, "push_in", "very slow", None)
    assert (t1.tier, t1.edit_s, t1.gen_s, t1.time, t1.face) == ("hero", 5.5, 6, "dawn", "clear")
    assert t1.sound.sfx == ["a low rumble"] and t1.end_state and t1.continuity and t1.warnings == []
    t6 = by["T6"]
    assert (t6.mode, t6.tier, t6.face, t6.time, t6.gen_s) == ("first_last", "secondary", "partial", "day", 4)
    assert t6.end_frame == "The empty living room by day." and t6.people[0].state == ["nosebleed"]
    assert t6.camera.text == "static wide shot, locked-off"
    t7 = by["T7"]
    assert (t7.mode, t7.tier, t7.gen_s, t7.edit_s, t7.action, t7.face) == ("still", "still", 0, 0.0, "", "none")
    assert S.edit_window(t7) is None


@pytest.mark.parametrize(("frame", "videos", "needles"), [
    ("{location: mina, composition: a, frame: b}", "[]", ["тест T9", "рівно один опис кадру"]),
    ("{location: mina}", "[]", ["тест T9", "рівно один опис кадру"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x}, {id: b, duration_s: 4, action: y}]",
     ["тест T9", "одне відео"]),
    ("{location: mina, frame: a, id: f}", "[]", ["тест T9", "без id"]),
    ("{location: mina, frame: a}", "[{duration_s: 0, action: x}]", ["videos.0.duration_s", "> 0"]),
    ("{location: mina, frame: a}", "[{duration_s: 4}]", ["videos.0.action", "бракує поля"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x, resolution: 1080p}]", ["«1080p»"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x, mode: first_last}]", ["тест T9", "end_frame"]),
    ("{location: mina, frame: a, end_frame: b}", "[{duration_s: 4, action: x}]", ["end_frame лише"]),
    ("{location: mina, frame: a, camera: wide}", "[]", ["frame.camera", "словником"]),
    ("{location: mina, frame: a, camera: {text: wide}}", "[]", ["camera кадру — лише словник"]),
    ("{location: atlantis, frame: a}", "[]", ["тест T9", "локації «atlantis»"]),
    ("{location: mina, variant: noon, frame: a}", "[]", ["тест T9", "«noon»"]),
    ("{location: mina, frame: a, people: [ghost]}", "[]", ["тест T9", "«ghost»"]),
    ("{location: mina, frame: a, people: [{id: vale, state: [bleeding]}]}", "[]", ["«bleeding»"]),
    ("{location: mina, frame: a, framng: Wide}", "[]", ["framng", "зайве поле"]),
    # одне значення — в одному місці
    ("{location: mina, frame: a, light: x}", "[{duration_s: 4, action: x, light: y}]", ["тест T9", "light і в frame"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x, tier: hero, resolution: 480p}]",
     ["тест T9", "tier hero — це 720p", "480p"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x, tier: still}]", ["videos.0.tier", "«still»"]),
    ("{location: mina, frame: a, framing: Wide, camera: {size: medium}}", "[]", ["тест T9", "framing і camera.size"]),
    ("{location: mina, frame: a, camera: {size: wide}}", "[{duration_s: 4, action: x, camera: {size: close-up}}]",
     ["тест T9", "«wide» у frame", "«close-up» у videos.camera"]),
    ("{location: mina, frame: a, camera: {move: push_in}}", "[{duration_s: 4, action: x, camera: slow pan}]",
     ["тест T9", "camera (frame + videos)", "не обидва"]),
    ("{location: mina, frame: a}", "[{duration_s: 4, action: x, camera: 5}]",
     ["videos.0.camera", "рядком або словником"]),
    ("{location: mina, frame: a, people: [{id: los_cuatro, state: [bleeding]}]}", "[]", ["у los_cuatro", "«bleeding»"]),
])
def test_test_pack_errors(data, tmp_path: Path, frame: str, videos: str, needles: list[str]) -> None:
    path = _write(tmp_path, f"tests:\n  - id: T9\n    title: t\n    frame: {frame}\n    videos: {videos}\n",
                  "test_pack.yaml")
    msg = _err(S.test_pack_specs, data, path)
    assert "test_pack.yaml" in msg
    for n in needles:
        assert n in msg, (n, msg)
    assert msg.count("«bleeding»") <= 1                                     # стан групи — одна помилка


def test_test_pack_same_light_and_matching_tier_are_fine(data, tmp_path: Path) -> None:
    path = _write(tmp_path, "tests:\n  - id: T9\n    title: t\n    frame: {location: mina, frame: a, light: x}\n"
                  "    videos: [{duration_s: 4, action: b, light: x, tier: secondary, resolution: 480p}]\n",
                  "test_pack.yaml")
    sp = S.test_pack_specs(data, path)[0]
    assert (sp.light, sp.tier) == ("x", "secondary")


def test_test_pack_shape_errors(data, tmp_path: Path) -> None:
    assert "tests" in _err(S.test_pack_specs, data, _write(tmp_path, "tests: {}\n", "tp.yaml"))
    assert "зайві ключі" in _err(S.test_pack_specs, data, _write(tmp_path, "tests: []\nextra: 1\n", "tp.yaml"))
    assert "зайві ключі" in _err(S.test_pack_specs, data, _write(tmp_path, "tests: []\nextra: 1\n2: 3\n", "tp.yaml"))
    assert "немає" in _err(S.test_pack_specs, data, tmp_path / "absent.yaml")
    dup = ("tests:\n  - {id: T1, title: a, frame: {location: mina, frame: x}}\n"
           "  - {id: T1, title: b, frame: {location: mina, frame: y}}\n")
    assert "повторюється" in _err(S.test_pack_specs, data, _write(tmp_path, dup, "tp.yaml"))
    extra = ("tests:\n  - {id: T1, title: a, frame: {location: mina, frame: x}, "
             "extra_frames: [{location: mina, frame: y}]}\n")
    assert "extra_frames потребує id" in _err(S.test_pack_specs, data, _write(tmp_path, extra, "tp.yaml"))


def test_real_test_pack_loads() -> None:
    """Справжній series/<slug>/lab/test_pack.yaml (старий формат або нові ключі) читається без помилок."""
    specs = S.test_pack_specs(P.Data(SLUG))
    ids = [s.id for s in specs]
    assert {"T1", "T4", "T4-face", "T5"} <= set(ids) and len(ids) == len(set(ids))
    by = {s.id: s for s in specs}
    assert by["T4"].video_id == "buildup" and by["T4-face"].gen_s >= 4
    assert all(s.frame and (s.action or s.mode == "still") for s in specs)


# ---------------------------------------------------------------- кліпи (§12)


FIXED = {"name": "manual-5s", "clip_s": [5], "resolution": "720p"}
RANGED = {"name": "replicate-2.5", "clip_min_s": 4, "clip_max_s": 30, "resolution_by_tier": {"hero": "720p"}}


@pytest.mark.parametrize(("edit", "profile", "want"), [
    (0.5, FIXED, (5, 1)), (3, FIXED, (5, 1)), (5, FIXED, (5, 1)), (5.0000001, FIXED, (5, 1)), (7, FIXED, (5, 2)),
    (10, FIXED, (5, 2)), (11, FIXED, (5, 3)), (4, {"clip_s": [4, 8]}, (4, 1)), (6, {"clip_s": [4, 8]}, (8, 1)),
    (9, {"clip_s": [4, 8]}, (8, 2)), (0.5, RANGED, (4, 1)), (7, RANGED, (7, 1)), (4.2, RANGED, (5, 1)),
    (40, RANGED, (20, 2)),
])
def test_clip_plan(edit: float, profile: dict, want: tuple[int, int]) -> None:
    assert S.clip_plan(edit, profile) == want


def _clip_spec(data, out_root: Path, **update) -> S.ShotSpec:
    return _specs(data, out_root, FIX / "overlay_v2.yaml")["4.03"].model_copy(update=update)


def test_clips_single_window_and_scare_event(data, out_root: Path) -> None:
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=3.0), FIXED)
    assert (c.index, c.of, c.gen_s, c.window, c.start, c.warnings) == (1, 1, 5, (0.0, 3.0), "frame", [])
    sp = _clip_spec(data, out_root, edit_s=3.0)
    assert (c.action, c.end_state, c.camera) == (sp.action, sp.end_state, sp.camera)
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=1.0, beat="scare", event_s=2.0), FIXED)
    assert c.window == (1.5, 2.5)                                           # 1 с навколо події
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=1.0, event_s=0.2), FIXED)
    assert c.window == (0.0, 1.0)                                           # не виходить за початок
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=2.0, window=(1.0, 3.0)), FIXED)
    assert c.window == (1.0, 3.0)
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=2.0, window=(3.0, 7.0)), FIXED)
    assert c.window == (3.0, 5.0) and "обрізано" in c.warnings[0]
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=8.0), RANGED)
    assert (c.gen_s, c.window) == (8, (0.0, 8.0))


def test_clips_split_with_and_without_overlay_clips(data, out_root: Path) -> None:
    sp = _clip_spec(data, out_root, edit_s=7.0)
    a, b = S.clips(sp, FIXED)
    assert (a.window, b.window, a.start, b.start) == ((0.0, 5.0), (0.0, 2.0), "frame", "prev_last")
    assert a.action == sp.action and b.action == f"The same action continues. {sp.action}"
    assert (a.end_state, b.end_state) == (None, sp.end_state) and "clips" in a.warnings[0] and b.warnings == []
    own = [S.ClipIn(action="x", camera=S.Camera(move="pan_left")), S.ClipIn(action="y", end_state="z")]
    a, b = S.clips(sp.model_copy(update={"clips": own}), FIXED)
    assert (a.action, a.camera.move, a.end_state, b.action, b.end_state) == ("x", "pan_left", None, "y", "z")
    assert b.camera == sp.camera and a.warnings == []
    a, b, c = S.clips(sp.model_copy(update={"edit_s": 11.0, "clips": own}), FIXED)
    assert "в оверлеї 2, а кліпів 3" in a.warnings[0] and c.action.startswith("The same action continues.")
    assert c.window == (0.0, 1.0) and c.end_state == sp.end_state
    a, _ = S.clips(sp.model_copy(update={"window": (0.0, 2.0)}), FIXED)
    assert any("лише для шоту з одного кліпу" in w for w in a.warnings)


def test_clips_handoff_t2v_and_no_video(data, out_root: Path) -> None:
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=4.0, handoff="continue"), FIXED)
    assert c.start == "prev_last"
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=4.0, mode="t2v"), FIXED)
    assert c.start == "none"
    a, b = S.clips(_clip_spec(data, out_root, edit_s=6.0, mode="t2v"), FIXED)
    assert (a.start, b.start) == ("none", "prev_last")
    assert S.clips(_clip_spec(data, out_root, mode="still"), FIXED) == []
    assert S.clips(_clip_spec(data, out_root, mode="none"), FIXED) == []


def test_clips_window_length_must_match_edit(data, out_root: Path) -> None:
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=1.0, window=(0.0, 3.0)), FIXED)
    assert c.window == (0.0, 3.0) and c.warnings == ["window 3 с ≠ edit_s 1 с (shots.json) — у монтажі шот вийде "
                                                     "іншої довжини"]
    (c,) = S.clips(_clip_spec(data, out_root, edit_s=2.0, window=(1.0, 3.04)), FIXED)
    assert c.warnings == []                                                 # допуск 0.05 с
