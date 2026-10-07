"""Компілятори промптів (fabrica/compile.py): кастинг, кадри, кліпи, репліки, маршрути, payload, лінт, уроки,
послідовності. Дані — вбудований мінімальний англійський шар (не залежить від правок series/)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

import fabrica.shotspec as S
from fabrica import bible as bible_mod
from fabrica import compile as C
from fabrica import lessons as L
from fabrica import lint as lint_mod
from fabrica import prompts as P
from fabrica import providers
from fabrica import shotlist as shotlist_mod
from fabrica.models import Script, Shots

ROOT = Path(__file__).resolve().parents[1]
SLUG = "la-garganta"
SCRIPT = ROOT / "tests" / "fixtures" / SLUG / "part1.script.json"
MANUAL = {"name": "manual-5s", "clip_s": [5], "resolution": "720p", "surface": "dropshot AI Studio (Seedance 2.5)",
          "url": "https://aistudio.dropshot.io"}
RANGE = {"name": "replicate-2.5", "clip_min_s": 4, "clip_max_s": 30,
         "resolution_by_tier": {"hero": "720p", "secondary": "480p", "found_footage": "480p"}}
PREVIEW = "Esto no es una coincidencia. Siete nombres, una sola noche, y la misma hora en todos los relojes del pueblo."

DATA = f"""
characters: {{vale: {{name: Vale}}, mateo: {{name: Mateo}}, diego: {{name: Diego}}, sofia: {{name: Sofía}},
              renata: {{name: Renata}}}}
members: {{tomas: {{name: Tomás, dna: "= Mateo (той самий ref обличчя)"}},
           beto: {{name: Beto, voice: {{voice_id: abc123}}}}, lupita: {{name: Lupita}}}}
supporting: {{policia: {{name: напарник}}}}
groups: {{los_cuatro: [vale, diego, sofia, mateo]}}
locations: {{mina: {{name: Шахта}}, casa: {{name: Дім}}}}
en:
  style:
    image: "Photorealistic 35mm film still, muted palette."
    image_footage: {{vhs: "A single frame from a 1994 home-video camcorder recording."}}
    video: "Live-action horror film look, natural motion."
    video_footage: {{vhs: "Handheld home-video camcorder look: moderate shake; no stabilization, no gimbal."}}
    low_light: {{image: "Dim but readable exposure; clean low-noise image.",
                 video: "Clean low-noise image; dark areas stay clean without colour noise."}}
    sheet_background: "plain light-grey seamless studio backdrop, soft even key light"
    original: "An original fictional character, not resembling any real person."
  image_rules: ["every person is an adult", "a single full-bleed photograph, no panels, borders or captions"]
  video_constants: ["No subtitles, no on-screen text."]
  states:
    nosebleed: {{image: "a thin dark-red line of blood under the left nostril",
                 video: "the thin line of blood under the nose stays"}}
    wet: {{image: "soaked hair and clothes", video: "hair and clothes stay soaked and dripping"}}
  characters:
    vale: {{who: "an adult Mexican woman, 19", tag: "the woman in the black denim jacket",
            dna: ["black straight hair in a high ponytail", "a small thin scar above her left eyebrow"],
            wardrobe: "a black denim jacket over a grey t-shirt", expression: "guarded", emotions: [rage, resolve],
            voice_design: "Native Spanish (Mexico City). Female, early 20s. Perfect quality. Persona: guarded leader.",
            preview_es: "{PREVIEW}"}}
    mateo: {{who: "an adult Mexican man, 19", tag: "the pale man in the plaid flannel shirt",
             dna: ["short dark hair parted in the middle"], wardrobe: "a plaid flannel shirt", expression: calm,
             emotions: [stillness], voice_design: "Native Spanish (Mexico City). Male, early 20s. Perfect quality.",
             preview_es: "{PREVIEW}"}}
    diego: {{who: "an adult Mexican man, 19", tag: "the man in the yellow windbreaker", dna: ["a red cap"],
             wardrobe: "a yellow windbreaker", expression: grin, emotions: [laugh],
             voice_design: "Native Spanish (Mexico City). Male, early 20s.",
             preview_es: "{PREVIEW}"}}
    sofia: {{who: "an adult Mexican woman, 19", tag: "the woman with round glasses", dna: ["round metal glasses"],
             wardrobe: "a burgundy cardigan", expression: focused, emotions: [focus],
             voice_design: "Native Spanish (Mexico City). Female, early 20s.",
             preview_es: "{PREVIEW}"}}
    renata: {{who: "an adult Mexican woman, 44", tag: "the policewoman with a low bun", dna: ["a tight low bun"],
              wardrobe: "a navy shirt", expression: stern, emotions: [authority], voice: "low dry voice",
              preview_es: "{PREVIEW}"}}
  members:
    tomas: {{who: "an adult Mexican man, 19, a 1994 graduate", tag: "the man in a white shirt under a plaid flannel",
             look: "short dark hair parted in the middle", mood: smiling, wardrobe: "a white shirt",
             wet: "the same adult man, soaked through"}}
    beto: {{who: "an adult Mexican man, 19, a 1994 graduate", tag: "the broad-shouldered man with a buzz cut",
            look: "a buzz cut, broad shoulders, a small pale scar on his chin", mood: grinning,
            wardrobe: "a white shirt"}}
    lupita: {{who: "an adult Mexican woman, 19, a 1994 graduate", tag: "the woman with curly bangs and hoop earrings",
              look: "curly dark hair with full bangs", mood: laughing, wardrobe: "a white blouse",
              wet: "the same adult woman, soaked through",
              voice_design: "Native Spanish (Mexico City). Female, early 20s. Perfect quality.",
              preview_es: "{PREVIEW}"}}
  supporting:
    policia: {{who: "an adult Mexican man, 48, a small-town policeman", tag: "the heavy-set policeman",
               look: "heavy-set, short greying hair", wardrobe: "a plain navy uniform shirt"}}
  locations:
    mina:
      base: "a mine entrance in a rocky mountainside"
      light: "night, cold moonlight"
      mood: dread
      time: night
      framing: wide establishing shot
      variants:
        dawn: {{desc: "the same entrance at dawn, low mist", light: "dawn, pale golden light", time: dawn,
                ref: mina.plate}}
        tunnel: {{replace: true, desc: "a narrow mine tunnel with timber supports",
                  light: "flashlight beams in darkness",
                  framing: "medium wide shot down the tunnel", time: night, ref: null}}
        flooded: {{replace: true, desc: "a flooded tunnel with black water", ref: mina.tunnel, time: night}}
        broken: {{replace: true, desc: "a collapsed tunnel", ref: mina.nope}}
    casa: {{base: "a modest living room", light: "day, soft daylight", mood: calm, time: day,
            framing: wide shot of the room}}
"""


def _data(slug: str = "compile-test") -> P.Data:
    raw = yaml.safe_load(DATA)
    d = P.Data.__new__(P.Data)
    d.slug, d.en, d.bible = slug, raw["en"], {}
    d.characters = {k: {"id": k, **v} for k, v in raw["characters"].items()}
    d.members = {k: {"id": k, **v} for k, v in raw["members"].items()}
    d.supporting = {k: {"id": k, **v} for k, v in raw["supporting"].items()}
    d.groups, d.locations = raw["groups"], {k: {"id": k, **v} for k, v in raw["locations"].items()}
    return d


@pytest.fixture
def data() -> P.Data:
    return _data()


@pytest.fixture(scope="module")
def ts() -> dict[str, P.Template]:
    return P.load_templates()


def _spec(**kw) -> S.ShotSpec:
    base = dict(id="1.02", set="1", title="Ч.1 · 1.02", scene_id="s01", tier="hero", mode="i2v", edit_s=4.0, gen_s=4,
                location="mina", variant="tunnel", light=None, time="night", footage=None,
                frame="Two people stand in the tunnel.", end_frame=None,
                action="She slowly raises the flashlight toward the ceiling.", end_state=None, camera=S.Camera(),
                sound=S.Sound(), people=[], lines=[], face="none")
    return S.ShotSpec(**(base | kw))


def _api(items: list[P.Item]) -> list[str]:
    return [w for i in items for w in i.warnings if w.startswith("API:")]


def _lint(items: list[P.Item]) -> list[str]:
    return [w for i in items for w in i.warnings if w.startswith("lint:")]


# ---------------------------------------------------------------- шаблони


def test_templates_v2_routes_and_payload_defaults(ts) -> None:
    assert "video.shot" not in ts
    for tid in ("image.character", "image.member_1994", "image.location", "image.start_frame", "video.i2v",
                "video.first_last", "video.t2v", "voice.line", "voice.design"):
        t = ts[tid]
        assert t.route and t.profile, tid
        fields = providers.route(t.route).fields
        assert set(t.payload) <= set(fields), (tid, set(t.payload) - set(fields))
        for route, extra in t.route_payload.items():
            assert set(extra) <= set(providers.route(route).fields), (tid, route)
    assert ts["video.i2v"].version >= 2 and ts["image.start_frame"].version >= 2


# ---------------------------------------------------------------- кастинг


def test_character_anchor_and_derived_views(data, ts) -> None:
    by = {i.id: i for i in C.character_items(data, ts)}
    front = by["cast-vale-front"]
    assert (front.step, front.route, front.refs, front.needs, front.produces) == (
        1, C.ANCHOR_ROUTE, [], [], "vale.front")
    assert "image_input" not in front.payload and "Image 1" not in front.prompt
    assert front.payload["allow_fallback_model"] is False and front.negative == ""
    for suffix, view in (("34", "three_quarter"), ("profile", "profile"), ("full", "full_body")):
        it = by[f"cast-vale-{suffix}"]
        assert (it.step, it.route, it.refs, it.produces) == (2, ts["image.character"].route, ["vale.front"],
                                                             f"vale.{view}")
        assert it.payload["image_input"] == ["ref:vale.front"] and it.prompt.startswith("Image 1 is the approved")
        assert it.payload["google_search"] is False and "allow_fallback_model" not in it.payload
    assert by["cast-vale-full"].payload["aspect_ratio"] == "2:3" and by["cast-vale-34"].payload["aspect_ratio"] == "3:4"
    assert "rage" in by["cast-vale-emo1"].prompt and "Only the expression changes" in by["cast-vale-emo1"].prompt
    items = list(by.values())
    assert not _api(items) and not _lint(items)
    assert all(i.params["route"] == i.route and "prompt" not in i.params and "image_input" not in i.params
               for i in items)


def test_member_anchor_face_of_and_wet(data, ts) -> None:
    by = {i.id: i for i in C.member_items(data, ts)}
    beto = by["cast-beto-1994"]
    assert (beto.step, beto.route, beto.refs) == (1, C.ANCHOR_ROUTE, [])
    tomas = by["cast-tomas-1994"]                       # обличчя Mateo (bible: «= Mateo»)
    assert (tomas.step, tomas.route, tomas.refs) == (2, ts["image.member_1994"].route, ["mateo.front"])
    assert "identity reference for Mateo" in tomas.prompt
    wet = by["cast-beto-wet"]
    assert (wet.refs, wet.produces, wet.step) == (["beto.1994"], "beto.wet", 2)
    assert any("немає wet" in w for w in wet.warnings) and "soaked hair and clothes" in wet.prompt
    assert "soaked through" in by["cast-tomas-wet"].prompt and not by["cast-tomas-wet"].warnings
    assert not _api(list(by.values()))


def test_location_plate_variants_and_framing(data, ts) -> None:
    by = {i.id: i for i in C.location_items(data, ts)}
    assert (by["loc-mina"].refs, by["loc-mina"].produces, by["loc-mina"].step) == ([], "mina.plate", 3)
    dawn = by["loc-mina-dawn"]
    assert dawn.refs == ["mina.plate"] and "change only this: the same entrance at dawn" in dawn.prompt
    assert dawn.prompt.count("a mine entrance in a rocky mountainside") == 1          # без подвоєння бази
    tunnel = by["loc-mina-tunnel"]
    assert tunnel.refs == [] and "Framing: medium wide shot down the tunnel" in tunnel.prompt
    assert "wide establishing" not in tunnel.prompt
    flooded = by["loc-mina-flooded"]
    assert flooded.refs == ["mina.tunnel"] and flooded.prompt.startswith("Image 1 is a reference of the same place")
    assert by["loc-mina-broken"].refs == [] and any("mina.nope" in w for w in by["loc-mina-broken"].warnings)
    assert by["loc-casa"].payload["aspect_ratio"] == "16:9" and not _api(list(by.values()))


def test_voice_design_items(data, ts) -> None:
    by = {i.id: i for i in C.voice_design_items(data, ts)}
    assert set(by) == {f"cast-{x}-voice" for x in ("vale", "mateo", "diego", "sofia", "renata", "lupita")}
    v = by["cast-vale-voice"]
    assert v.prompt.startswith("Native Spanish (Mexico City). Female, early 20s.") and v.step == 4
    assert v.payload["voice_description"] == v.prompt and v.payload["text"] == PREVIEW
    assert {k: v.payload[k] for k in ("model_id", "guidance_scale", "loudness", "should_enhance")} == {
        "model_id": "eleven_ttv_v3", "guidance_scale": 5, "loudness": 0.5, "should_enhance": False}
    assert v.payload["seed"] == P.seed_for("cast-vale-voice") and v.extra["preview_es"] == PREVIEW
    assert v.extra["manual"][0]["surface"] == "ElevenLabs API (JSON)"
    assert json.loads(v.extra["manual"][0]["body"])["model_id"] == "eleven_ttv_v3"
    renata = by.pop("cast-renata-voice")                       # без voice_design → взято короткий voice
    assert any("voice_design" in w for w in renata.warnings) and any("мінімум 20" in w for w in renata.warnings)
    assert not _api(list(by.values()))


# ---------------------------------------------------------------- кадри


def test_frame_ref_order_views_and_text_only_people(data, ts) -> None:
    people = [S.Person(id="vale", view="back", screen="right"),
              S.Person(id="mateo", view="three_quarter", screen="left"),
              S.Person(id="diego", view="blurred"), S.Person(id="sofia", view="profile"),
              S.Person(id="policia", view="distant")]
    it = C.frame_items(_spec(people=people), data, ts)[0]
    assert it.id == "p1-1.02-frame" and it.step == 5 and it.produces == "p1.1.02.frame"
    assert it.refs == ["mina.tunnel", "mateo.three_quarter", "vale.full_body", "sofia.profile"]
    assert it.payload["image_input"] == [f"ref:{r}" for r in it.refs]
    assert ("Image 2 is Mateo, the pale man in the plaid flannel shirt; Image 3 is Vale, the woman in the black denim "
            "jacket; Image 4 is Sofía, the woman with round glasses.") in it.prompt   # ім'я + тег: жінок не сплутати
    assert "the camera position, framing and light come from this description" in it.prompt
    assert "Vale is on the right of the frame, seen from behind" in it.prompt
    assert "The man in the yellow windbreaker is out of focus" in it.prompt           # blurred — лише текст
    assert "An adult Mexican man, 48, a small-town policeman: heavy-set" in it.prompt     # другорядний — текстом
    assert it.prompt.index("Image 1 is the location") < it.prompt.index("Scene:") < it.prompt.index("Lighting:")
    assert not _api([it]) and it.negative == ""


def test_frame_caps_people_refs_at_four(data, ts) -> None:
    people = [S.Person(id=x) for x in ("vale", "mateo", "diego", "sofia", "renata")]
    it = C.frame_items(_spec(people=people), data, ts)[0]
    assert len(it.refs) == 1 + C.MAX_PEOPLE_REFS and "renata.front" not in it.refs
    assert any("більше 4" in w for w in it.warnings) and "a tight low bun" in it.prompt


def test_frame_states_wet_ref_footage_low_light_camera(data, ts) -> None:
    people = [S.Person(id="beto", state=["wet"]), S.Person(id="vale", state=["nosebleed"], screen="left")]
    cam = S.Camera(size="medium close-up", angle="low angle", lens_mm=35, move="push_in", speed="slow")
    it = C.frame_items(_spec(people=people, footage="vhs", camera=cam), data, ts)[0]
    assert it.refs == ["mina.tunnel", "vale.front", "beto.wet"]                         # зліва направо, потім решта
    assert "a thin dark-red line of blood under the left nostril" in it.prompt and "soaked hair" not in it.prompt
    assert it.prompt.startswith("Create one still frame.") and "1994 home-video camcorder" in it.prompt
    assert "Dim but readable exposure" in it.prompt and "Photorealistic 35mm" not in it.prompt
    assert "Camera: medium close-up, low angle, 35mm lens." in it.prompt
    assert "push" not in it.prompt.lower()                                              # кадр статичний
    day = C.frame_items(_spec(location="casa", variant=None, time="day"), data, ts)[0]
    assert "Dim but readable" not in day.prompt and day.refs == ["casa.plate"]


def test_first_last_end_frame_and_video(data, ts) -> None:
    sp = _spec(mode="first_last", end_frame="The tunnel is empty.", people=[S.Person(id="mateo", view="back")])
    frames = C.frame_items(sp, data, ts)
    assert [i.id for i in frames] == ["p1-1.02-frame", "p1-1.02-end"]
    end = frames[1]
    assert end.refs == ["p1.1.02.frame", "mateo.full_body"] and end.produces == "p1.1.02.end"
    assert "Image 1 is the first frame of this shot" in end.prompt and "The tunnel is empty." in end.prompt
    assert "Image 1 = p1.1.02.frame (результат «p1-1.02-frame»)" in end.extra["manual"][0]["how"]
    v = C.video_items(sp, data, ts, profile=MANUAL)[0]
    assert v.template.id == "video.first_last" and v.refs == v.needs == ["p1.1.02.frame", "p1.1.02.end"]
    assert v.payload["image"] == "ref:p1.1.02.frame" and v.payload["last_frame_image"] == "ref:p1.1.02.end"
    assert "Generate a continuous transition from the first frame to the last frame." in v.prompt
    assert "End frame" in v.extra["manual"][0]["how"] and not _api([v] + frames)


# ---------------------------------------------------------------- відео


def test_video_route_by_face_and_payload(data, ts) -> None:
    clear = C.video_items(_spec(people=[S.Person(id="vale", screen="left")], face="clear"), data, ts, profile=MANUAL)[0]
    assert clear.route == C.FACE_ROUTE and clear.payload["use_virtual_avatar"] is True
    assert clear.payload | {"prompt": ""} == {"prompt": "", "image": "ref:p1.1.02.frame", "duration": 5,
                                              "resolution": "720p", "seed": P.seed_for("p1-1.02-video"),
                                              "aspect_ratio": "adaptive", "generate_audio": True,
                                              "output_format": "mp4", "use_virtual_avatar": True}
    assert "Blocking:" in clear.prompt                                       # Cloudflare: кадр задає обличчя, не склад
    assert "the woman in the black denim jacket on the left of the frame" in clear.prompt
    auto = C.video_items(_spec(people=[S.Person(id="vale", screen="left")], face="clear"), data, ts, profile=RANGE)[0]
    assert auto.prompt == clear.prompt                                       # лабораторія = автомат (рішення 07.10)
    none = C.video_items(_spec(people=[S.Person(id="vale", view="back")], face="none"), data, ts, profile=MANUAL)[0]
    assert none.route == ts["video.i2v"].route and "use_virtual_avatar" not in none.payload
    assert "Blocking:" not in none.prompt and none.extra["face"] == "none"
    assert not _api([clear, none]) and clear.negative == none.negative == ""
    assert clear.params["tool"] == MANUAL["surface"] and "image" not in clear.params and clear.params["duration"] == 5


def test_video_block_order_and_lock(data, ts) -> None:
    sp = _spec(footage="vhs", end_state="the beam rests on the ceiling",
               camera=S.Camera(move="push_in", speed="very slow", target="the ceiling", endpoint="the cracked beam"),
               people=[S.Person(id="vale", screen="left", state=["nosebleed"])],
               sound=S.Sound(ambience=["water drips"], sfx=["a low rumble"]))
    p = C.video_items(sp, data, ts, profile=MANUAL)[0].prompt
    order = ["Single continuous shot, no cuts.", "Clean low-noise image",
             "The clip begins exactly at this moment.", "She slowly raises", "End state: the beam rests",
             "Camera: very slow push in toward the ceiling, ending on the cracked beam.",
             "Handheld home-video camcorder look", "Light: flashlight beams",               # вигляд запису — після камери
             "Sound: a low rumble; water drips.", "No BGM; only ambience and action sounds.",
             "The woman in the black denim jacket stays on the left",
             "the thin line of blood under the nose stays", "No subtitles, no on-screen text."]
    pos = [p.index(x) for x in order]
    assert pos == sorted(pos), p
    assert p.endswith("No subtitles, no on-screen text.")


def test_video_never_redescribes_appearance_and_constants_lint_clean(data, ts) -> None:
    people = [S.Person(id="vale", screen="left"), S.Person(id="beto", state=["wet"])]
    v = C.video_items(_spec(people=people, face="clear"), data, ts, profile=MANUAL)[0]
    for s in ("black straight hair", "scar above her left eyebrow", "an adult Mexican", "buzz cut, broad shoulders"):
        assert s not in v.prompt, s
    assert "the broad-shouldered man with a buzz cut: hair and clothes stay soaked and dripping" in v.prompt
    assert not _lint([v]) and not v.warnings, v.warnings                              # сталі речення чисті
    copied = C.video_items(_spec(people=people, action="Black straight hair in a high ponytail sways."), data, ts,
                           profile=MANUAL)[0]
    assert any("переописує зовнішність" in w for w in copied.warnings)


def test_on_screen_and_off_screen_dialogue(data, ts) -> None:
    line = S.Line(n=1, speaker="vale", text_es="¿Quién anda ahí?", delivery="whisper", on_screen=True,
                  delivery_source="overlay")
    people = [S.Person(id="vale"), S.Person(id="mateo")]
    v = C.video_items(_spec(people=people, lines=[line], face="clear"), data, ts, profile=MANUAL)[0]
    assert ('In Mexican Spanish with a Mexico City accent, in a trembling whisper, the woman in the black denim '
            'jacket says only this line, once: "¿Quién anda ahí?"') in v.prompt
    assert "everyone else keeps their mouth closed" in v.prompt and not any("камера static" in w for w in v.warnings)
    assert not _lint([v])                                          # «¿Quién…» у лапках не лінтується
    moving = C.video_items(_spec(people=people, lines=[line], face="clear", camera=S.Camera(move="pan_left")),
                           data, ts, profile=MANUAL)[0]
    assert any("камера static або push_in very slow" in w for w in moving.warnings)
    off = line.model_copy(update={"on_screen": False, "offscreen": True, "speaker": "mateo"})
    o = C.video_items(_spec(people=[S.Person(id="vale", view="back")], lines=[off]), data, ts, profile=MANUAL)[0]
    assert 'An off-screen voice, in Mexican Spanish with a Mexico City accent, in a trembling whisper, says: "¿Quién' \
           in o.prompt and "Everyone in the frame keeps their mouth naturally closed." in o.prompt


def test_t2v_has_no_refs_and_explicit_aspect(data, ts) -> None:
    v = C.video_items(_spec(mode="t2v", camera=S.Camera(size="extreme wide")), data, ts, profile=MANUAL)[0]
    assert v.template.id == "video.t2v" and v.refs == v.needs == [] and "image" not in v.payload
    assert v.payload["aspect_ratio"] == "16:9" and "Extreme wide shot of a narrow mine tunnel" in v.prompt
    assert "Live-action horror film look" in v.prompt and not _api([v])
    assert v.extra["clip"]["start"] == "none" and "без стартового кадру" in v.extra["manual"][0]["how"]


@pytest.mark.parametrize(("edit", "profile", "durations", "windows"), [
    (3, MANUAL, [5], [(0, 3)]), (5, MANUAL, [5], [(0, 5)]), (10, MANUAL, [5, 5], [(0, 5), (0, 5)]),
    (7, MANUAL, [5, 5], [(0, 5), (0, 2)]), (7, RANGE, [7], [(0, 7)]), (1, RANGE, [4], [(0, 1)]),
])
def test_clip_segmentation_items(data, ts, edit, profile, durations, windows) -> None:
    sp = _spec(edit_s=edit, gen_s=S.gen_seconds(edit), tier="secondary")
    vs = C.video_items(sp, data, ts, profile=profile)
    assert [v.payload["duration"] for v in vs] == durations
    assert [tuple(v.extra["clip"]["window"]) for v in vs] == windows
    assert [v.id for v in vs] == ["p1-1.02-video", "p1-1.02-video-2"][:len(vs)]
    assert [v.produces for v in vs] == [f"p1.1.02.c{k}" for k in range(1, len(vs) + 1)]
    assert vs[0].needs == ["p1.1.02.frame"] and all(v.extra["clip"]["of"] == len(vs) for v in vs)
    assert {v.payload["resolution"] for v in vs} == {"720p" if profile is MANUAL else "480p"}
    if len(vs) > 1:
        assert vs[1].needs == ["p1.1.02.c1.last"] and vs[1].extra["clip"]["start_item"] == "p1-1.02-video"
        assert "The same action continues." in vs[1].prompt and any("clips" in w for w in vs[0].warnings)
        assert "результат «p1-1.02-video» — його останній кадр" in vs[1].extra["manual"][0]["how"]
        assert "state_out" in vs[-1].extra and "state_out" not in vs[0].extra
    assert not _api(vs) and all(P.set_of(v.id) == "1" for v in vs)


def test_overlay_clips_drive_each_clip(data, ts) -> None:
    clips = [S.ClipIn(action="She steps forward.", camera=S.Camera(move="follow", target="her")),
             S.ClipIn(action="She stops at the edge.", end_state="she stands still")]
    vs = C.video_items(_spec(edit_s=8, clips=clips), data, ts, profile=MANUAL)
    assert "She steps forward." in vs[0].prompt and "Camera: slow follow shot behind her" in vs[0].prompt
    assert "She stops at the edge. End state: she stands still." in vs[1].prompt and C.STATIC in vs[1].prompt
    assert not any("clips" in w for v in vs for w in v.warnings)


def test_handoff_continue_chains_previous_clip(data, ts) -> None:
    a = _spec(id="1.05", title="Ч.1 · 1.05", edit_s=7)
    b = _spec(id="1.06", title="Ч.1 · 1.06", handoff="continue")
    items = C.spec_items([a, b], data, ts, profile=MANUAL)
    ids = [i.id for i in items]
    assert "p1-1.06-frame" not in ids and "p1-1.05-frame" in ids
    vb = next(i for i in items if i.id == "p1-1.06-video")
    assert vb.needs == ["p1.1.05.c2.last"] and vb.extra["clip"]["start"] == "prev_last"
    assert vb.extra["clip"]["start_item"] == "p1-1.05-video-2" and vb.extra["shot"] == "1.06"
    still = _spec(id="1.04", mode="still", gen_s=0)
    items = C.spec_items([still, b], data, ts, profile=MANUAL)                        # перед ним немає відео
    assert "p1-1.06-frame" in [i.id for i in items]
    vb = next(i for i in items if i.id == "p1-1.06-video")
    assert vb.needs == ["p1.1.06.frame"] and any("handoff continue" in w for w in vb.warnings)


def test_scare_window_centred_on_event(data, ts) -> None:
    v = C.video_items(_spec(edit_s=1, beat="scare", event_s=2.0), data, ts, profile=MANUAL)[0]
    assert v.extra["clip"]["window"] == [1.5, 2.5] and v.extra["edit_window"].startswith("кліп 5 с → у монтаж 1 с")


def test_long_video_prompt_warns_over_target(data, ts) -> None:
    v = C.video_items(_spec(action="She walks slowly. " * 90), data, ts, profile=MANUAL)[0]
    assert any("ціль ≤ 1600" in w for w in v.warnings)


# ---------------------------------------------------------------- репліки


def test_line_items_payload(data, ts) -> None:
    lines = [S.Line(n=1, speaker="beto", text_es="¡Chuy, graba!", delivery="shout", delivery_source="guess"),
             S.Line(n=2, speaker="lupita", text_es="¿Oyeron eso?", delivery_source="default")]
    a, b = C.line_items(_spec(lines=lines), data, ts)
    assert a.id == "p1-1.02-voice1" and a.step == 7 and a.prompt == "[shouting] ¡Chuy, graba!"
    assert a.payload == {"text": "[shouting] ¡Chuy, graba!", "voice_id": "abc123",
                         "voice_settings": {"stability": 0.3, "similarity_boost": 0.8},
                         "seed": P.seed_for("p1-1.02-voice1"), "output_format": "mp3_44100_192",
                         "model_id": "eleven_v4", "language_code": "es"}
    assert a.needs == ["beto.voice"] and a.extra["delivery"] == "shout"
    assert b.prompt == "¿Oyeron eso?" and "voice_id" not in b.payload and b.needs == ["lupita.voice"]
    assert b.payload["voice_settings"] == {"stability": 0.5, "similarity_boost": 0.75}
    parts = providers.split(a.route, a.payload)
    assert parts["path"] == {"voice_id": "abc123"} and parts["query"] == {"output_format": "mp3_44100_192"}
    assert "abc123" in a.extra["manual"][0]["endpoint"] and "voice_id ще немає" in b.extra["manual"][0]["how"]
    assert "{voice_id}" in b.extra["manual"][0]["endpoint"]
    assert "voice_id" not in json.loads(b.extra["manual"][0]["body"])
    assert not _api([a, b])


# ---------------------------------------------------------------- уроки


def _lessons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> None:
    path = tmp_path / "lessons.yaml"
    path.write_text(yaml.safe_dump({"lessons": rows}, allow_unicode=True), encoding="utf-8", newline="\n")
    monkeypatch.setattr(L, "path", lambda slug: path)


def test_lessons_injected_before_constants(data, ts, tmp_path, monkeypatch) -> None:
    _lessons(tmp_path, monkeypatch, [
        {"id": "L1", "rule": "The flashlight beam stays steady", "scope": {"kind": "video", "location": "mina"}},
        {"id": "L2", "rule": "Dust hangs in the beam.", "scope": {"kind": "video", "tags": ["vhs"]}, "priority": 5},
        {"id": "L3", "rule": "Off rule.", "scope": {"kind": "video"}, "active": False},
        {"id": "L4", "rule": "Other place.", "scope": {"location": "casa"}},
        {"id": "L5", "rule": "Images only.", "scope": {"kind": "image", "template": "image.start_frame"}},
    ])
    v = C.video_items(_spec(footage="vhs"), data, ts, profile=MANUAL)[0]
    assert v.extra["lessons"] == ["L2", "L1"]
    assert v.prompt.index("Dust hangs in the beam.") < v.prompt.index("The flashlight beam stays steady.") \
        < v.prompt.index("No subtitles")
    assert "Off rule" not in v.prompt and "Other place" not in v.prompt and "Images only" not in v.prompt
    f = C.frame_items(_spec(), data, ts)[0]
    assert f.extra["lessons"] == ["L5"] and "Images only." in f.prompt
    line = C.line_items(_spec(lines=[S.Line(n=1, speaker="vale", text_es="Hola.", delivery_source="default")]),
                        data, ts)[0]
    assert "lessons" not in line.extra and line.prompt == "Hola."
    assert L.rules_for(data.slug, "video", "x", "video.i2v", {"location:mina"}) == ["The flashlight beam stays steady"]


def test_lessons_dropped_when_prompt_too_long(data, ts, tmp_path, monkeypatch) -> None:
    _lessons(tmp_path, monkeypatch, [{"id": "BIG", "rule": "The beam stays steady. " * 120, "scope": {"kind": "video"}},
                                     {"id": "OK", "rule": "Dust hangs in the beam.", "priority": 1}])
    v = C.video_items(_spec(), data, ts, profile=MANUAL)[0]
    assert v.extra["lessons"] == ["OK"] and len(v.prompt) <= 2000
    assert any("урок BIG не вмістився" in w for w in v.warnings) and not _api([v])


def test_lessons_file_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(L, "path", lambda slug: tmp_path / "absent.yaml")
    assert L.load("x") == [] and L.rules_for("x", "video", "r", "t", set()) == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("lessons:\n  - {id: A}\n  - {id: A, rule: x, scope: {where: y}}\n", encoding="utf-8")
    monkeypatch.setattr(L, "path", lambda slug: bad)
    with pytest.raises(L.LessonError) as e:
        L.load("x")
    assert "rule" in str(e.value) and "scope" in str(e.value) and "повторюється" in str(e.value)


# ---------------------------------------------------------------- справжні набори й послідовності


@pytest.fixture
def manual_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENERATION_PROFILE", "manual-5s")


@pytest.fixture
def part1_out(tmp_path: Path) -> Path:
    folder = tmp_path / SLUG / "part1"
    folder.mkdir(parents=True)
    shutil.copy(SCRIPT, folder / "script.json")
    script = Script.model_validate_json(SCRIPT.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(ROOT / "series" / SLUG / "part1_shotlist.md", bible_mod.load(SLUG), 1, script)
    (folder / "shots.json").write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8")
    return tmp_path


def test_real_casting_and_test_pack_are_api_clean(manual_profile) -> None:
    for set_name in ("casting", "test-pack"):
        items = P.build(SLUG, set_name)
        assert not _api(items), _api(items)[:5]
        assert [i.step for i in items] == sorted(i.step for i in items)
        assert all(i.negative == "" and i.route and i.payload for i in items)
        for i in items:
            limit = providers.route(i.route).prompt_max_chars
            assert not limit or len(i.prompt) <= limit, i.id


def test_sequence_first30_closure(manual_profile, part1_out) -> None:
    items = P.sequence_items(SLUG, "first30", out_root=part1_out)
    steps = [i.step for i in items]
    assert steps == sorted(steps) and steps[0] <= 4 and steps[-1] == 6     # репліки VHS — рідний звук Seedance
    assert not any(i.kind == "voice" for i in items)
    shots = {i.extra.get("shot") for i in items if i.step >= 5}
    assert shots <= {f"1.0{k}" for k in range(1, 9)} and {"1.01", "1.07"} <= shots
    produced = {i.produces for i in items}
    for it in items:
        for need in it.needs:
            assert need in produced or need.removesuffix(".last") in produced, (it.id, need)
    ids = [i.id for i in items]
    assert "cast-beto-wet" in ids and "loc-mina-tunnel" in ids and "cast-vale-front" not in ids
    assert len(ids) == len(set(ids))


def test_sequence_errors(tmp_path, monkeypatch, part1_out) -> None:
    with pytest.raises(P.PromptError, match="немає послідовності"):
        P.sequence_items(SLUG, "nope", out_root=part1_out)
    path = tmp_path / "sequences.yaml"
    path.write_text('x: {title: t, part: 1, shots: ["9.99"]}\nbad: {part: 7, shots: []}\n', encoding="utf-8")
    monkeypatch.setattr(P, "sequences_path", lambda slug: path)
    with pytest.raises(P.PromptError, match="bad"):
        P.sequences(SLUG)
    path.write_text('x: {title: t, part: 1, shots: ["9.99"]}\n', encoding="utf-8")
    with pytest.raises(P.PromptError, match="9.99"):
        P.sequence_items(SLUG, "x", out_root=part1_out)


def test_set_of_and_select_clip_ids() -> None:
    assert P.set_of("p1-1.02-video-2") == "1" and P.set_of("tp-T4-buildup-2") == "test-pack"
    ids = ("p1-1.02-video", "p1-1.02-video-2", "p1-1.03-video")
    items = [P.Item(i, "1", "video", "", None, "", "", {}) for i in ids]
    assert [i.id for i in P.select(items, only="1.02")] == ["p1-1.02-video", "p1-1.02-video-2"]


def test_compiler_constants_are_whitelisted() -> None:
    text = " ".join(C.CONSTANTS) + " " + C.STATIC
    assert lint_mod.lint("video", text) == []


# ---------------------------------------------------------------- рев'ю core: мовець, стан, маршрути, sha


SHOUT = S.Line(n=1, speaker="lupita", text_es="¡Chuy, graba!", delivery="shout", delivery_source="guess")
LUPITA = "the woman with curly bangs and hoop earrings"


def test_speaker_in_frame_without_lip_sync_speaks_herself(data, ts) -> None:
    """Мовець у кадрі, репліка не on_screen (has_dialogue_visible ні) → говорить вона, а не «голос за кадром»."""
    people = [S.Person(id="lupita"), S.Person(id="beto", view="back")]
    v = C.video_items(_spec(people=people, lines=[SHOUT], face="clear"), data, ts, profile=MANUAL)[0]
    assert (f'In Mexican Spanish with a Mexico City accent, shouting, {LUPITA} says: "¡Chuy, graba!"'
            in v.prompt) and "off-screen" not in v.prompt
    assert "Then the speaker's lips close; everyone else keeps their mouth closed." in v.prompt
    assert "keeps their mouth naturally closed" not in v.prompt
    assert any("мовець «lupita» у кадрі (view face)" in w and "lines.1.on_screen" in w for w in v.warnings)
    a, b = C.video_items(_spec(people=people, lines=[SHOUT], face="clear", edit_s=8), data, ts, profile=MANUAL)
    assert any("мовець" in w for w in a.warnings) and not any("мовець" in w for w in b.warnings)   # репліка — кліп 1
    back = C.video_items(_spec(people=[S.Person(id="lupita", view="back")], lines=[SHOUT]), data, ts,
                         profile=MANUAL)[0]
    assert f"{LUPITA} says:" in back.prompt and not any("мовець" in w for w in back.warnings)
    absent = C.video_items(_spec(people=[S.Person(id="beto", view="back")], lines=[SHOUT]), data, ts,
                           profile=MANUAL)[0]
    assert 'An off-screen voice, in Mexican Spanish with a Mexico City accent, shouting, says: "¡Chuy' in absent.prompt
    assert "Everyone in the frame keeps their mouth naturally closed." in absent.prompt and not _lint([v, back, absent])


def test_state_out_has_person_states_and_carries_as_state_in(data, ts) -> None:
    a = _spec(id="1.05", title="Ч.1 · 1.05", scene_id="s04", end_state="she kneels",
              people=[S.Person(id="vale", view="back", state=["nosebleed"])],
              continuity=["the lantern lies on the floor"])
    b = _spec(id="1.06", title="Ч.1 · 1.06", scene_id="s04")
    c = _spec(id="1.07", title="Ч.1 · 1.07", scene_id="s05")
    by = {i.id: i for i in C.spec_items([a, b, c], data, ts, profile=MANUAL)}
    out = by["p1-1.05-video"].extra["state_out"]
    assert out == ["she kneels", "the woman in the black denim jacket: the thin line of blood under the nose stays",
                   "the lantern lies on the floor"]
    assert by["p1-1.06-frame"].extra["state_in"] == out and by["p1-1.06-video"].extra["state_in"] == out
    assert not any("state_in" in by[x].extra for x in ("p1-1.05-frame", "p1-1.05-video", "p1-1.07-frame",
                                                       "p1-1.07-video"))                       # інша сцена — ні
    alone = {i.id: i.prompt_sha for i in C.spec_items([b], data, ts, profile=MANUAL)}
    assert alone == {k: by[k].prompt_sha for k in alone}                    # state_in у prompt_sha не входить


def test_manual_keys_render_in_viewer_md(data, ts) -> None:
    """Контракт із переглядачем: endpoint, body (JSON) і note ручних інструкцій потрапляють у <елемент>.md."""
    from fabrica import viewer as viewer_mod

    voice = next(i for i in C.voice_design_items(data, ts) if i.id == "cast-vale-voice")
    md = viewer_mod.item_md(data.slug, voice)
    assert voice.extra["manual"][0]["endpoint"] in md and '"model_id": "eleven_ttv_v3"' in md
    line = C.line_items(_spec(lines=[S.Line(n=1, speaker="beto", text_es="¡Ya!", delivery_source="guess")]),
                        data, ts)[0]
    assert "text-to-speech/abc123?output_format=mp3_44100_192" in viewer_mod.item_md(data.slug, line)
    vid = C.video_items(_spec(people=[S.Person(id="vale")], face="clear"), data, ts, profile=MANUAL)[0]
    md = viewer_mod.item_md(data.slug, vid)
    assert vid.extra["manual"][-1]["endpoint"] in md and "dropshot може відхилити" in md


def test_dropshot_face_note_and_image_surface_parity(data, ts) -> None:
    face = C.video_items(_spec(people=[S.Person(id="vale")], face="clear"), data, ts, profile=MANUAL)[0]
    plain = C.video_items(_spec(), data, ts, profile=MANUAL)[0]
    assert "маршрут Cloudflare нижче" in face.extra["manual"][0]["note"] and "note" not in plain.extra["manual"][0]
    by = {i.id: i for i in C.character_items(data, ts)}
    pro, nb = by["cast-vale-front"].extra["manual"][0], by["cast-vale-34"].extra["manual"][0]
    assert pro["surface"] == "AI Studio / Gemini · dropshot Image" and "dropshot AI Studio → Image" in pro["how"]
    assert nb["surface"] == "AI Studio / Gemini" and "Nano Banana 2.1" in nb["how"]
    assert "лише чернетка, у журнал не як еталон" in nb["how"]


@pytest.mark.parametrize(("size", "want"), [
    ("medium", "medium shot"), ("extreme wide", "extreme wide shot"), ("medium wide", "medium wide shot"),
    ("wide, seen from the doorway", "wide shot, seen from the doorway"), ("medium close-up", "medium close-up"),
    ("close-up", "close-up"), ("extreme close-up", "extreme close-up"), ("wide establishing shot", "wide establishing shot"),
    ("handheld point of view", "handheld point of view"), ("medium two-shot", "medium two-shot"), (None, ""),
])
def test_shot_size_only_suffixes_vocabulary(size, want) -> None:
    assert C._shot_size(size) == want


def test_free_text_size_in_frame_and_blocking(data, ts) -> None:
    sp = _spec(people=[S.Person(id="vale")], face="clear", camera=S.Camera(size="wide, seen from the doorway"))
    assert "Camera: wide shot, seen from the doorway." in C.frame_items(sp, data, ts)[0].prompt
    assert "Blocking: wide shot, seen from the doorway;" in C.video_items(sp, data, ts, profile=RANGE)[0].prompt


def test_video_names_characters_warns(data, ts) -> None:
    ask = S.Line(n=1, speaker=None, text_es="¿Mateo?", delivery_source="default")
    v = C.video_items(_spec(people=[S.Person(id="vale", view="back")], action="Vale slowly turns toward Tomás.",
                            lines=[ask]), data, ts, profile=MANUAL)[0]
    names = [w for w in v.warnings if "називає" in w]
    assert names == ["відео називає «Vale» — Seedance не знає імен, пиши tag",
                     "відео називає «Tomás» — Seedance не знає імен, пиши tag"]   # «Mateo» лише в репліці
    clean = C.video_items(_spec(people=[S.Person(id="vale", view="back")]), data, ts, profile=MANUAL)[0]
    assert not any("називає" in w for w in clean.warnings)


def test_route_t2v_never_face_and_face_frame_chains_keep_face_route(data, ts) -> None:
    face = [S.Person(id="vale")]
    t = C.video_items(_spec(mode="t2v", people=face, face="clear"), data, ts, profile=MANUAL)[0]
    assert t.route == ts["video.t2v"].route != C.FACE_ROUTE and "use_virtual_avatar" not in t.payload
    t1, t2 = C.video_items(_spec(mode="t2v", edit_s=8, people=face, face="clear"), data, ts, profile=MANUAL)
    assert t1.route != C.FACE_ROUTE and (t2.route, t2.payload["use_virtual_avatar"]) == (C.FACE_ROUTE, True)
    a = _spec(id="1.05", title="Ч.1 · 1.05", people=face, face="clear")
    b = _spec(id="1.06", title="Ч.1 · 1.06", handoff="continue", people=[S.Person(id="vale", view="back")])
    vb = next(i for i in C.spec_items([a, b], data, ts, profile=MANUAL) if i.id == "p1-1.06-video")
    assert (vb.route, vb.payload["use_virtual_avatar"], vb.needs) == (C.FACE_ROUTE, True, ["p1.1.05.c1.last"])
    a2 = a.model_copy(update={"people": [S.Person(id="vale", view="back")], "face": "none"})
    vb = next(i for i in C.spec_items([a2, b], data, ts, profile=MANUAL) if i.id == "p1-1.06-video")
    assert vb.route == ts["video.i2v"].route and "use_virtual_avatar" not in vb.payload
    assert not _api([t, t1, t2, vb])


def test_continuity_spelled_out_only_when_frame_is_loose(data, ts) -> None:
    sp = _spec(people=[S.Person(id="vale")], face="clear",
               continuity=["hundreds of small grey pebbles hang motionless in the air."])
    lab = C.video_items(sp, data, ts, profile=MANUAL)[0]
    face = C.video_items(sp, data, ts, profile=RANGE)[0]
    assert lab.prompt == face.prompt                                         # промпт не залежить від профілю
    assert "Continuity: hundreds of small grey pebbles hang motionless in the air." in face.prompt
    assert face.prompt.index("Blocking:") < face.prompt.index("Continuity:") < face.prompt.index("She slowly raises")
    rep = C.video_items(sp.model_copy(update={"people": [S.Person(id="vale", view="back")], "face": "none"}), data, ts,
                        profile=MANUAL)[0]
    assert "Continuity:" not in rep.prompt
    t2v = C.video_items(sp.model_copy(update={"mode": "t2v"}), data, ts, profile=MANUAL)[0]
    assert "Continuity: hundreds of small grey pebbles" in t2v.prompt
    fl = C.video_items(sp.model_copy(update={"mode": "first_last", "end_frame": "The tunnel is empty."}), data, ts,
                       profile=RANGE)[0]
    assert "Continuity: hundreds" in fl.prompt and not _lint([face, t2v, fl])


def test_camera_static_with_shake_is_not_contradictory() -> None:
    assert C.camera_sentence(S.Camera(shake="light")) == ("Camera: handheld, holding the framing in place, with a "
                                                          "light natural shake.")
    assert C.camera_sentence(S.Camera(move="push_in", target="the door", shake="strong")) == (
        "Camera: slow push in toward the door, with a strong shake.")
    for shake in ("light", "moderate", "strong"):
        text = C.camera_sentence(S.Camera(shake=shake))
        assert "still" not in text and lint_mod.lint("video", text) == []


def test_prompt_sha_ignores_window_surface_and_card_state(data, ts) -> None:
    a = C.video_items(_spec(edit_s=1, beat="scare", event_s=2.0), data, ts, profile=MANUAL)[0]
    b = C.video_items(_spec(edit_s=1, beat="scare", event_s=1.0), data, ts, profile=MANUAL)[0]
    assert a.extra["clip"]["window"] != b.extra["clip"]["window"] and a.prompt_sha == b.prompt_sha
    c = C.video_items(_spec(edit_s=1, beat="scare", event_s=2.0), data, ts, profile=MANUAL | {"surface": "інша"})[0]
    assert c.params["tool"] != a.params["tool"] and c.prompt_sha == a.prompt_sha
    a.extra |= {"state_in": ["x"], "state_out": ["y"]}
    assert a.prompt_sha == b.prompt_sha
    d = C.video_items(_spec(edit_s=1, beat="scare", event_s=2.0, action="She lowers the flashlight."), data, ts,
                      profile=MANUAL)[0]
    e = C.video_items(_spec(edit_s=1, beat="scare", event_s=2.0), data, ts, profile=MANUAL | {"resolution": "480p"})[0]
    assert len({a.prompt_sha, d.prompt_sha, e.prompt_sha}) == 3                           # змінився API → новий sha


def test_line_camera_check_uses_clip_one_and_static_text(data, ts) -> None:
    line = S.Line(n=1, speaker="vale", text_es="Hola.", on_screen=True, delivery_source="default")
    sp = _spec(people=[S.Person(id="vale")], lines=[line], face="clear")
    for text, warns in (("medium shot, static", False), ("locked-off medium shot", False),
                        ("medium shot, very slow push in", False), ("medium shot", True),
                        ("medium shot, slow pan", True)):
        v = C.video_items(sp.model_copy(update={"camera": S.Camera(text=text)}), data, ts, profile=MANUAL)[0]
        assert any("камера static" in w for w in v.warnings) is warns, text
    own = [S.ClipIn(action="She speaks.", camera=S.Camera()),
           S.ClipIn(action="She turns away.", camera=S.Camera(move="pan_left"))]
    v1, v2 = C.video_items(sp.model_copy(update={"edit_s": 8, "clips": own, "camera": S.Camera(move="pan_left")}),
                           data, ts, profile=MANUAL)
    assert not any("камера static" in w for w in v1.warnings + v2.warnings)
    v1, v2 = C.video_items(sp.model_copy(update={"edit_s": 8, "clips": own[::-1]}), data, ts, profile=MANUAL)
    assert any("камера static" in w for w in v1.warnings) and not any("камера static" in w for w in v2.warnings)


def test_sequence_title_required_and_unique_shots(tmp_path, monkeypatch) -> None:
    path = tmp_path / "sequences.yaml"
    monkeypatch.setattr(P, "sequences_path", lambda slug: path)
    for text in ('x: {part: 1, shots: ["1.01"]}\n', 'x: {title: " ", part: 1, shots: ["1.01"]}\n',
                 'x: {title: 5, part: 1, shots: ["1.01"]}\n'):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(P.PromptError, match="x: потрібні title"):
            P.sequences(SLUG)
    path.write_text('x: {title: t, part: 1, shots: ["1.01", "1.02", "1.01"]}\n', encoding="utf-8")
    with pytest.raises(P.PromptError, match="шоти повторюються: 1.01"):
        P.sequences(SLUG)
    path.write_text('x: {title: t, part: 1, shots: ["1.01"]}\n', encoding="utf-8")
    assert P.sequences(SLUG)["x"]["title"] == "t"
