"""Лінт промптів: списки з prompts/lint.yaml, межі слів, whitelist, рухи камери, формат і порядок повідомлень."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fabrica import lint as L

MSG = re.compile(r"^lint: «[^»]+» \([^)]+\)( → .+)?$")

# Приклади з docs/research/2026-10-07-generators.md §2.8 (зібрані за правилами): E1 — чистий,
# E2 — одне справжнє заперечення («her eyes do not leave the doorway»), репліки в лапках не чіпаємо.
E1 = ("Single continuous shot, no cuts. Clean low-noise image; dark areas stay clean without colour noise. "
      "The clip begins exactly at this moment. The woman with the flashlight takes three slow steps down the "
      "corridor, the beam trembling slightly in her hand and sweeping from the cracked floor tiles up to a "
      "half-open wooden door at the far end. End state: she stops two metres from the door. Camera: slow push in "
      "from behind her right shoulder at her walking pace, ending framed on the dark gap of the door. The "
      "flashlight beam is the only light source, steady intensity; outside the beam the corridor stays very dark "
      "but readable; dust drifts through the beam. Sound: her uneven breathing, shoes scraping grit on tile, "
      "<one wooden creak from behind the door at the very end>. No BGM. Her hair and clothing stay exactly as in "
      "the image; the corridor layout stays the same. No subtitles, no on-screen text.")
E2 = ("Single continuous shot, no cuts. The clip begins exactly at this moment. Static locked-off camera on a "
      "tripod, medium close-up; the frame does not move. The woman lowers the flashlight slightly. After one "
      "breath, in Mexican Spanish with a Mexico City accent, a slow trembling whisper, she says only this line, "
      "once: \"¿Mamá? No, no puede ser.\" Then her lips close and stay still; her eyes do not leave the doorway. "
      "Sound: slow water drips. No BGM. Her face, hair and clothing stay exactly as in the image. "
      "No subtitles, no on-screen text.")


def terms(kind: str, text: str, **kw) -> list[str]:
    """Лише «слово» з кожного повідомлення — так тести читаються."""
    return [re.match(r"lint: «([^»]+)»", m).group(1) for m in L.lint(kind, text, **kw)]


def labels(kind: str, text: str) -> list[str]:
    return [re.match(r"lint: «[^»]+» \(([^)]+)\)", m).group(1) for m in L.lint(kind, text)]


# ---------------------------------------------------------------- каталог


def test_catalog_loads_with_all_lists() -> None:
    data = L.load()
    assert list(data["lists"]) == ["age_words", "banned_video", "soft_video", "homographs", "violence_raw",
                                   "param_leak", "negations", "emotion_words", "text_magnets", "multi_camera"]
    for name, spec in data["lists"].items():
        assert set(spec["kinds"]) <= set(L.KINDS), name
        assert spec["label"].strip(), name


def test_whitelist_holds_compiler_constants() -> None:
    """DESIGN §7 + prompt_en.video_constants: сталі речення компілятора не дають жодного попередження."""
    phrases = {p.rstrip(".").lower() for p in L.load()["whitelist"]["phrases"]}
    for p in ("single continuous shot, no cuts", "no subtitles, no on-screen text", "no bgm", "no audio",
              "no logo, no watermark", "no music"):
        assert p in phrases
    constants = [
        "Single continuous shot, no cuts.", "Clean low-noise image; dark areas stay clean without colour noise.",
        "The clip begins exactly at this moment.", "Static locked-off camera on a tripod; the frame does not move.",
        "No BGM.", "No BGM; only ambience and action sounds.", "No audio.", "No logo, no watermark.",
        "No subtitles, no on-screen text.", "Strictly only naturally occurring sound and foley, no music allowed.",
        "Handheld home-video camcorder look: moderate shake, imperfect framing, autofocus hunting, small exposure "
        "shifts; no stabilization, no gimbal.",
        "Handheld smartphone video: light natural shake, autofocus hunting; no stabilization.",
        "Characters keep their mouths naturally closed, there is no narration, only the specified ambience remains.",
        "She stays seated; she does not stand, turn, or leave frame.",
        "Her eyes, not her head, turn toward the sound.",
        "One continuous take, no cuts.",
    ]
    for c in constants:
        assert L.lint("video", c) == [], c
    assert L.lint("video", " ".join(constants)) == []


def test_research_examples() -> None:
    assert L.lint("video", E1) == []
    assert terms("video", E2) == ["not"]                     # «do not leave»; «No, no» у лапках — репліка


# ---------------------------------------------------------------- межі слів і регістр


@pytest.mark.parametrize("text", ["breakfast", "steadfast", "fasten the belt", "a fastener"])
def test_fast_only_as_word(text: str) -> None:
    assert "fast" not in terms("video", text)


@pytest.mark.parametrize("text", ["she turns fast", "FAST", "a fast-moving shadow", "fast."])
def test_fast_hits(text: str) -> None:
    assert terms("video", text) == ["fast"]


@pytest.mark.parametrize("text", ["her nose bleeds", "none of them moves", "a slow nod", "a notebook",
                                  "a knot of rope", "the north wall", "nevertheless", "nobody's notes",
                                  "a nonsense rhyme", "innocent eyes", "anyone"])
def test_negation_false_positives(text: str) -> None:
    assert L.lint("video", text) == []


@pytest.mark.parametrize(("text", "hit"), [("No one is there.", "no"), ("She does NOT cry.", "not"),
                                           ("he never blinks", "never"), ("without a sound", "without"),
                                           ("Don't look.", "don't"), ("Don’t look.", "don't"),
                                           ("she doesn’t move her lips", "doesn't"), ("he cannot see", "cannot")])
def test_negation_hits(text: str, hit: str) -> None:
    assert terms("video", text) == [hit]


@pytest.mark.parametrize("text", ["a cowboy hat", "her girlfriend", "fifteen candles", "a minority", "kidney",
                                  "a studentship", "a boycott", "skidding tyres"])
def test_age_false_positives(text: str) -> None:
    assert L.lint("video", text) == []


def test_multiword_phrases_hyphen_space_and_case() -> None:
    assert terms("image", "an 18-year-old in a School-Uniform") == ["school uniform"]
    assert terms("image", "a SCHOOL  UNIFORM") == ["school uniform"]
    assert terms("video", "the room is pitch-black") == ["pitch black"]
    assert terms("video", "a real person close-up") == ["real person"]
    assert terms("video", "a 6 seconds long clip with audio") == ["seconds long", "with audio"]
    assert terms("image", "a blood pool on the floor") == ["blood pool"]


def test_longest_phrase_wins_inside_list() -> None:
    """«prepa student» — одне попередження, без окремого «student»."""
    assert terms("image", "an 18-year-old prepa student") == ["prepa student"]
    assert terms("image", "a student and a prepa student") == ["student", "prepa student"]


# ---------------------------------------------------------------- списки й kinds


def test_age_words_hint_differs_by_kind() -> None:
    img, vid = L.lint("image", "a boy"), L.lint("video", "a boy")
    assert img != vid
    assert "adult man, 19" in img[0] and "гардероб" in vid[0]


def test_young_is_video_only() -> None:
    assert L.lint("image", "a young woman, adult, 19") == []
    assert terms("video", "a young woman") == ["young"]
    assert terms("video", "youth and kids") == ["youth", "kids"]


def test_banned_and_soft_video() -> None:
    assert terms("video", "photorealistic, 8K, masterpiece, ultra detailed, grainy VHS look") == \
        ["photorealistic", "8K", "masterpiece", "ultra-detailed", "grainy", "VHS"]
    assert terms("video", "the glass glints; a faint glow") == ["glints", "glow"]
    soft = L.lint("video", "a drone shot over the mine")
    assert len(soft) == 1 and "aerial flythrough" in soft[0] and "м'яко" in soft[0]
    assert L.lint("image", "photorealistic 8K drone photo") == []      # для картинок це не заборона


def test_homograph_and_violence_both_report_shoot() -> None:
    assert labels("video", "they shoot") == ["омонім", "насильство"]
    assert labels("image", "they shoot") == ["насильство"]           # омоніми — лише відео


def test_violence_and_wounds() -> None:
    assert terms("image", "a stab wound, gore") == ["stab", "wound", "gore"]
    assert terms("video", "wounds") == ["wounds"]


def test_param_leak() -> None:
    assert terms("video", "16:9 frame, 720p, 24fps, 24 fps") == ["16:9", "720p", "24fps", "fps"]
    assert terms("video", "a 5-second clip --ar 16:9 --duration 5") == ["second clip", "--ar", "16:9", "--duration"]
    assert L.lint("video", "the clock shows 3:17; it reads 21:90") == []
    assert L.lint("video", "a long hallway — slowly") == []


def test_emotion_words_point_to_body() -> None:
    out = L.lint("video", "She is terrified and angry.")
    assert terms("video", "She is terrified and angry.") == ["terrified", "angry"]
    assert "breath catches" in out[0] and "jaw clenches" in out[1]
    assert L.lint("image", "a terrified adult woman, 19") == []


def test_text_magnets_and_list_allow() -> None:
    assert terms("image", "a neon sign, store signage and a soda bottle") == ["sign", "signage", "soda bottle"]
    assert terms("video", "a news ticker and chyron") == ["news ticker", "chyron"]
    assert L.lint("image", "a label-less bottle on a brand new table, a logo-free cap") == []
    assert L.lint("image", "a design on the cushion, she resigns, a signal lamp") == []


def test_voice_kind_has_no_lists() -> None:
    assert L.lint("voice", "[whispering] No, no. ¡El niño! A boy runs fast.") == []


def test_unknown_kind_raises() -> None:
    with pytest.raises(L.LintError, match="kind"):
        L.lint("audio", "text")


# ---------------------------------------------------------------- whitelist і маски


def test_whitelist_masks_every_list() -> None:
    """«logo» у «No logo, no watermark.» і «subtitles» у сталому реченні — не магніти тексту."""
    assert L.lint("video", "No logo, no watermark. No subtitles, no on-screen text.") == []
    assert terms("video", "A logo on the wall. No logo, no watermark.") == ["logo"]


def test_whitelist_without_final_period_and_mixed_case() -> None:
    assert L.lint("video", "no subtitles, NO ON-SCREEN TEXT") == []
    assert L.lint("video", "Single continuous shot, no cuts") == []


def test_negation_next_to_whitelist_still_flagged() -> None:
    assert terms("video", "No BGM. No one moves.") == ["no"]
    assert terms("video", "No subtitles, no on-screen text. She does not cry.") == ["not"]


def test_quoted_dialogue_is_ignored() -> None:
    text = 'In Mexican Spanish she says: "No, no te vayas, niño." Then {No sé.} and “No.”'
    assert L.lint("video", text) == []
    assert terms("video", 'She says "No." and does not move her hands.') == ["not"]


def test_extra_allow_from_compiler() -> None:
    rule = "a clean frame with unmarked walls, no lettering, signs or logos anywhere"
    assert L.lint("image", rule) == []                             # стоїть у whitelist YAML
    custom = "every wall bare of signs, labels"
    assert terms("image", custom) == ["signs", "labels"]
    assert L.lint("image", custom, allow=[custom]) == []
    assert L.lint("image", custom + ". A boy.", allow=(custom,)) == L.lint("image", "A boy.")


def test_image_negations_are_allowed() -> None:
    assert L.lint("image", "no people in frame, never blurred, without glare") == []


# ---------------------------------------------------------------- рухи камери


@pytest.mark.parametrize("text", [
    "Camera: very slow push in toward the door, ending on the handle.",
    "Camera: slow push in, slightly handheld.",
    "Camera: dolly zoom on her face, the hallway stretching behind her.",
    "Camera: whip pan to the doorway.",
    "Camera: tracks left, following her at walking speed.",
    "Camera: insert, slow pan following the beam.",
    "Camera: slow tilt up from the floor to the ceiling, following the flashlight beam.",
    "Camera: wide tracking shot.",
    "Camera: static.",
    "The camera pans left and tilts up while it zooms. Camera: static locked-off on a tripod.",
    "Camera: slow push in. The beam pans across the wall and follows the dust.",
    "Camera: push in. Lighting: lamp. Camera: pan left.",
])
def test_multi_camera_single_move(text: str) -> None:
    assert "кілька рухів камери" not in labels("video", text)


def test_multi_camera_warns_in_camera_sentence() -> None:
    out = L.lint("video", "The door opens. Camera: slow push in, then pan left and tilt up toward the lamp. Sound: hum.")
    assert len(out) == 1 and "(кілька рухів камери)" in out[0]
    assert "«push in + pan + tilt»" in out[0]
    assert terms("video", "Camera: Crane up, orbiting the well.") == ["crane + orbit"]
    assert terms("video", "camera: zoom in and dolly in") == ["zoom + push in"]
    assert terms("video", "Camera: follows her, then pans left.") == ["track + pan"]


def test_multi_camera_each_sentence_separately_and_video_only() -> None:
    text = "Camera: pan left and zoom. Camera: orbit, then crane down."
    assert terms("video", text) == ["pan + zoom", "orbit + crane"]
    assert L.lint("image", text) == []


# ---------------------------------------------------------------- формат, повтори, порядок


def test_message_format() -> None:
    out = L.lint("video", "A boy runs fast without a sound. 16:9. Camera: pan and tilt. She is sad, a sign.")
    assert out and all(MSG.match(m) for m in out)
    assert all(m.startswith("lint: ") for m in out)


def test_dedup_case_insensitive() -> None:
    assert L.lint("video", "boy boy Boy BOY") == L.lint("video", "a boy")
    assert len(L.lint("video", "Camera: pan and tilt. Camera: pan and tilt.")) == 1


def test_stable_order_lists_then_position() -> None:
    """Порядок списків YAML (вік → заборонене → … → камера), усередині — за першою появою."""
    text = "Camera: pan and tilt. She is sad. Fast. A girl, then a boy, then a girl."
    assert labels("video", text) == ["вік", "вік", "заборонено у відео", "емоція словом", "кілька рухів камери"]
    assert terms("video", text)[:2] == ["girl", "boy"]
    assert L.lint("video", text) == L.lint("video", text)


def test_empty_text() -> None:
    assert L.lint("video", "") == [] and L.lint("image", None) == []    # type: ignore[arg-type]


# ---------------------------------------------------------------- зламаний YAML


def _yaml(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "lint.yaml"
    p.write_text(body, encoding="utf-8", newline="\n")
    return p


@pytest.mark.parametrize(("body", "needle"), [
    ("lists: {}\n", "lists"),
    ("lists:\n  a: {label: x, kinds: [audio], terms: [y]}\n", "kinds"),
    ("lists:\n  a: {label: x, kinds: [video]}\n", "terms або moves"),
    ("lists:\n  a: {kinds: [video], terms: [y]}\n", "label"),
    ("lists:\n  a: {label: x, kinds: [video], terms: [{re: '([a-'}]}\n", "регулярний вираз"),
    ("lists:\n  a: {label: x, kinds: [video], terms: [y], colour: red}\n", "невідомі ключі"),
    ("lists:\n  a: {label: x, kinds: [video], terms: [{term: y, kinds: [image]}]}\n", "kinds терміна"),
    ("lists:\n  a: {label: x, kinds: [video], terms: [y], hint: {audio: z}}\n", "hint"),
    ("lists:\n  a: {label: x, kinds: [video], terms: [y], sentence: Camera}\n", "sentence"),
    ("whitelist: {patterns: ['(']}\nlists:\n  a: {label: x, kinds: [video], terms: [y]}\n", "регулярний вираз"),
    ("lists: [\n", "YAML"),
])
def test_broken_catalog_is_clear(tmp_path: Path, body: str, needle: str) -> None:
    p = _yaml(tmp_path, body)
    with pytest.raises(L.LintError, match=re.escape(needle)):
        L.load(p)


def test_custom_catalog_and_bom(tmp_path: Path) -> None:
    p = tmp_path / "lint.yaml"
    p.write_bytes("\ufefflists:\n  x:\n    label: тест\n    kinds: [image]\n    terms: [kettle]\n".encode("utf-8"))
    assert L.lint("image", "a Kettle", path=p) == ["lint: «kettle» (тест)"]
    assert L.lint("video", "a kettle", path=p) == []
    with pytest.raises(L.LintError, match="немає файлу"):
        L.load(tmp_path / "missing.yaml")


def test_catalog_reloads_after_edit(tmp_path: Path) -> None:
    p = _yaml(tmp_path, "lists:\n  x: {label: t, kinds: [video], terms: [kettle]}\n")
    assert terms("video", "kettle pot", path=p) == ["kettle"]
    _yaml(tmp_path, "lists:\n  x: {label: t, kinds: [video], terms: [kettle, pot]}\n")
    assert terms("video", "kettle pot", path=p) == ["kettle", "pot"]
