"""Каталог маршрутів (prompts/providers.yaml + fabrica/providers.py): форма каталогу, валідація payload, ціни."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from fabrica import providers as PR

ROOT = Path(__file__).resolve().parents[1]
SD25, CF25 = "replicate:bytedance/seedance-2.5", "cloudflare:bytedance/seedance-2.5"
SD20 = "replicate:bytedance/seedance-2.0"
NBPRO, NB21 = "replicate:google/nano-banana-pro", "replicate:google/nano-banana-2.1"
EL4, TTV, SYNC = "elevenlabs:eleven_v4", "elevenlabs:eleven_ttv_v3", "replicate:sync/lipsync-2-pro"
ROUTES = (SD25, CF25, SD20, NBPRO, NB21, EL4, TTV, SYNC)

I2V = {"prompt": "Single continuous shot, no cuts. The clip begins exactly at this moment. No BGM.",
       "image": "ref:tp.T1.frame", "duration": 5, "resolution": "480p", "aspect_ratio": "adaptive",
       "generate_audio": True, "output_format": "mp4", "seed": 123456}
SAMPLES = {   # так компілятори складатимуть payload — кожен має бути чистим
    SD25: I2V,
    CF25: {**I2V, "use_virtual_avatar": True},
    SD20: {"prompt": "Shot 1: wide establishing of the mine mouth at dawn.", "duration": 8, "resolution": "1080p",
           "aspect_ratio": "16:9", "generate_audio": True, "seed": 1},
    NBPRO: {"prompt": "A photograph of an adult woman, 19, front view.", "aspect_ratio": "3:4", "resolution": "2K",
            "output_format": "png", "safety_filter_level": "block_only_high", "allow_fallback_model": False},
    NB21: {"prompt": "Create one cinematic film still. Image 1 is the location.", "aspect_ratio": "16:9",
           "image_input": ["ref:mina.tunnel", "ref:vale.full", "ref:mateo.34"], "resolution": "2K",
           "google_search": False, "image_search": False, "output_format": "png"},
    EL4: {"voice_id": "abc123", "output_format": "mp3_44100_192", "text": "[whispering] No toquen nada.",
          "model_id": "eleven_v4", "language_code": "es", "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
          "seed": 4294967295},
    TTV: {"voice_description": "Native Spanish (Mexico City). Male, early 20s. Perfect quality. Persona: joker.",
          "text": "¿Neta? No manches, güey, aquí no hay nada. Vámonos ya, que se hace de noche y la mina da miedo, "
                  "de veras.", "model_id": "eleven_ttv_v3", "guidance_scale": 5, "loudness": 0.5, "seed": 7,
          "should_enhance": False},
    SYNC: {"video": "ref:p1-4.03-video", "audio": "ref:p1-4.03-voice1", "sync_mode": "cut_off", "temperature": 0.5,
           "active_speaker": True},
}


def v(key: str, **changes) -> list[str]:
    """validate для зразка маршруту з правками; None у правці — прибрати поле."""
    payload = {**SAMPLES[key], **changes}
    return PR.validate(key, {k: x for k, x in payload.items() if x is not None})


def has(msgs: list[str], *parts: str) -> bool:
    return any(all(p in m for p in parts) for m in msgs)


# ---------------------------------------------------------------- каталог


def test_catalog_has_design_routes() -> None:
    routes = PR.load()
    assert set(routes) == set(ROUTES)
    kinds = {k: r.kind for k, r in routes.items()}
    assert kinds == {SD25: "video", CF25: "video", SD20: "video", NBPRO: "image", NB21: "image", EL4: "voice",
                     TTV: "voice_design", SYNC: "lipsync"}
    for key, r in routes.items():
        assert key == f"{r.provider}:{r.model}" and r.provider in PR.PROVIDERS
        assert r.verified and "\n" not in r.verified
        assert re.search(r"20\d\d-\d\d-\d\d", r.verified), f"{key}: verified без дати"


def test_catalog_cached_and_reloaded_on_change(tmp_path: Path) -> None:
    assert PR._catalog(None)[0] is PR._catalog(None)[0]                # кеш спільний …
    assert PR.load() is not PR.load() and PR.load() == PR.load()          # … а назовні — копії
    path = tmp_path / "providers.yaml"
    path.write_text((ROOT / "prompts" / "providers.yaml").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    first = PR.load(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["routes"][SYNC]
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    st = path.stat()
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert SYNC in first and SYNC not in PR.load(path)


def test_manual_per_route_in_ukrainian() -> None:
    for key, r in PR.load().items():
        m = r.manual
        assert m["surface"] and m["url"].startswith("https://") and re.search("[а-яіїєґ]", m["how"]), key
    cf = PR.route(CF25).manual
    assert "$CLOUDFLARE_ACCOUNT_ID" in cf["how"] and "$CLOUDFLARE_API_TOKEN" in cf["how"]
    assert "/ai/run/bytedance/seedance-2.5" in cf["endpoint"] and "UNVERIFIED" in cf["how"] + cf["endpoint"]
    cmds = [line.strip() for line in cf["how"].splitlines() if line.strip().startswith("curl")]
    assert len(cmds) == 2 and cmds[1].startswith("curl.exe ")             # zsh + PowerShell — окремими рядками
    assert all(c.endswith('--data-binary "@payload.json"') for c in cmds)  # @ без лапок у PowerShell — splatting
    assert "$env:CLOUDFLARE_ACCOUNT_ID" in cmds[1] and "$env:CLOUDFLARE_API_TOKEN" in cmds[1]
    assert "$env:" not in cmds[0] and not re.search(r"(?<!\")@payload", cf["how"])
    assert "Replicate playground" in PR.route(SD25).manual["surface"]
    assert "ElevenLabs" in PR.route(EL4).manual["surface"] and "{voice_id}" in PR.route(EL4).manual["endpoint"]
    text = (ROOT / "prompts" / "providers.yaml").read_text(encoding="utf-8")
    assert not re.search(r"(r8_|sk_)[A-Za-z0-9]{16,}", text)          # жодних ключів у каталозі


def test_unverified_shapes_marked() -> None:
    assert PR.route(NB21).verified.startswith("UNVERIFIED")
    assert "UNVERIFIED" in PR.route(CF25).verified
    assert "UNVERIFIED" in PR.route(EL4).verified and PR.route(EL4).price["rate"] is None


def test_enum_values_are_strings() -> None:
    """YAML робить із «16:9» число, а з on/off — bool: у каталозі вони мусять бути в лапках."""
    def walk(fields: dict):
        for name, spec in fields.items():
            yield name, spec
            yield from walk(spec.get("fields") or {})
    for key, r in PR.load().items():
        for name, spec in walk(r.fields):
            if spec["type"] == "enum":
                assert all(isinstance(x, str) for x in spec["values"]), f"{key}.{name}"
            if name == "aspect_ratio":
                assert all(":" in x or x in ("adaptive", "match_input_image") for x in spec["values"]), key


def test_design_specifics() -> None:
    sd25, cf, sd20 = PR.route(SD25), PR.route(CF25), PR.route(SD20)
    assert sd25.prompt_max_chars == cf.prompt_max_chars == 2000 and sd20.prompt_max_chars == 4000
    assert set(cf.fields) - set(sd25.fields) == {"use_virtual_avatar", "fps", "camera_fixed"}
    assert "avoid" in cf.fields["fps"] and "avoid" in cf.fields["camera_fixed"]
    assert cf.defaults["aspect_ratio"] == "adaptive" and sd25.defaults["aspect_ratio"] == "16:9"
    assert "audio_needs_visual_ref" not in cf.rules and "audio_needs_visual_ref" in sd25.rules
    assert sd20.fields["duration"]["max"] == 15 and {"1080p", "4k"} <= set(sd20.fields["resolution"]["values"])
    assert "9:21" in sd20.fields["aspect_ratio"]["values"] and "9:21" not in sd25.fields["aspect_ratio"]["values"]
    assert [sd20.fields[k]["max_items"] for k in PR.REFS] == [9, 3, 3]
    assert [sd25.fields[k]["max_items"] for k in PR.REFS] == [30, 10, 10]
    assert set(PR.route(EL4).fields["voice_settings"]["fields"]) == {"stability", "similarity_boost"}
    assert "seed" not in PR.route(NBPRO).fields and "seed" not in PR.route(NB21).fields
    assert PR.route(SYNC).price == {"unit": "second", "rate": 0.08325} and PR.route(SYNC).prompt_field is None


def test_defaults_are_copies() -> None:
    d = PR.route(SD25).defaults
    d["reference_images"].append("ref:x")
    assert PR.route(SD25).defaults["reference_images"] == []


def test_unknown_route() -> None:
    with pytest.raises(PR.ProviderError, match="немає маршруту «replicate:foo/bar»"):
        PR.route("replicate:foo/bar")
    with pytest.raises(ValueError):
        PR.validate("replicate:foo/bar", {})
    with pytest.raises(PR.ProviderError, match="немає каталогу"):
        PR.load(Path("nope") / "providers.yaml")


# ---------------------------------------------------------------- валідація


@pytest.mark.parametrize("key", ROUTES)
def test_every_route_sample_valid(key: str) -> None:
    assert PR.validate(key, SAMPLES[key]) == []


def test_messages_prefixed_and_deduplicated() -> None:
    msgs = v(SD25, duration=40, foo=1)
    assert msgs and all(m.startswith("API: ") for m in msgs) and len(msgs) == len(set(msgs))
    assert PR.validate(SD25, ["not", "a", "dict"]) == ["API: payload має бути словником, а не list"]


def test_unknown_keys() -> None:
    assert has(v(SD25, foo=1), "невідоме поле «foo»", SD25)
    assert has(v(SD25, negative_prompt="blur"), "«negative_prompt»", "позитивно")
    assert has(v(SD25, use_virtual_avatar=True), "«use_virtual_avatar»", "cloudflare")
    assert has(v(NB21, seed=1), "невідоме поле «seed»")
    assert has(v(EL4, voice_settings={"stability": 0.5, "similarity_boost": 0.7, "style": 0.3}),
               "«voice_settings.style»", "лише stability і similarity_boost")
    for key, extra in ((SD25, {"style": "noir"}), (NBPRO, {"speed": 1}), (EL4, {"style": 0.3})):
        msgs = PR.validate(key, {**SAMPLES[key], **extra})                 # вкладена підказка не для верхнього рівня
        assert has(msgs, "прибери його") and not has(msgs, "voice_settings"), key


def test_required_and_none_is_absent() -> None:
    assert has(v(NBPRO, prompt=None), "бракує обов'язкового поля «prompt»")
    assert has(v(NBPRO, prompt=""), "бракує обов'язкового поля «prompt»")
    assert has(v(EL4, text=None), "«text»") and has(v(EL4, model_id=None), "«model_id»")
    assert has(v(SYNC, audio=None), "«audio»")
    assert PR.validate(SD25, {**I2V, "seed": None}) == []           # nullable у схемі Replicate: null дозволено
    assert PR.validate(SD25, {**I2V, "image": None, "aspect_ratio": "16:9", "last_frame_image": None}) == []
    assert PR.validate(SD20, {**SAMPLES[SD20], "seed": None}) == []
    assert PR.validate(SD25, {}) == []                               # у 2.5 обов'язкових полів немає


def test_none_where_api_takes_no_null() -> None:
    """None = JSON null: payload — рівно те, що отримає API, тож непотрібне поле прибирають, а не обнуляють."""
    for name in ("duration", "resolution", "aspect_ratio", "generate_audio", "prompt"):
        assert has(PR.validate(SD25, {**I2V, name: None}), f"«{name}»=None — API отримає null"), name
    assert has(PR.validate(CF25, {**SAMPLES[CF25], "seed": None}), "«seed»=None")     # Cloudflare: суворі типи
    assert has(PR.validate(NBPRO, {**SAMPLES[NBPRO], "allow_fallback_model": None}), "«allow_fallback_model»=None")
    assert has(PR.validate(EL4, {**SAMPLES[EL4], "voice_settings": {"stability": None, "similarity_boost": 0.7}}),
               "«voice_settings.stability»=None")
    assert has(PR.validate(CF25, {**SAMPLES[CF25], "fps": None}), "«fps» не надсилаємо")
    assert PR.validate(NBPRO, {**SAMPLES[NBPRO], "prompt": None}) == ["API: бракує обов'язкового поля «prompt»"]


def test_types() -> None:
    assert has(v(SD25, duration="5"), "«duration» має бути цілим числом")
    assert has(v(SD25, duration=5.0), "«duration» має бути цілим числом")
    assert has(v(SD25, duration=True), "«duration» має бути цілим числом")
    assert has(v(SD25, generate_audio="true"), "«generate_audio» має бути true/false")
    assert has(v(SD25, prompt=42), "«prompt» має бути рядком")
    assert has(v(SD25, image=["ref:a"]), "«image» має бути рядком")
    assert has(v(NB21, image_input="ref:a"), "«image_input» має бути списком")
    assert has(v(EL4, voice_settings=0.5), "«voice_settings» має бути об'єктом")
    assert has(v(EL4, voice_settings={"stability": "high", "similarity_boost": 0.7}), "«voice_settings.stability»")
    assert has(v(EL4, previous_request_ids=["a", 1]), "«previous_request_ids»[1]")
    assert v(TTV, loudness=0) == [] and v(TTV, guidance_scale=3.5) == []     # number: і ціле, і дробове


def test_enum_and_const() -> None:
    assert has(v(SD25, resolution="1080p"), "«resolution»=«1080p»", "480p, 720p")
    assert v(SD20, resolution="4k") == []
    assert has(v(SD25, aspect_ratio="9:21"), "«aspect_ratio»=«9:21»")
    assert has(v(EL4, output_format="mp3_44100_999"), "«output_format»")
    assert has(v(EL4, model_id="eleven_v3"), "«model_id» має бути «eleven_v4»")
    assert has(v(TTV, model_id="eleven_multilingual_ttv_v2"), "«model_id» має бути «eleven_ttv_v3»")


def test_min_max_and_also() -> None:
    assert v(SD25, duration=-1) == [] and v(SD25, duration=30) == [] and v(SD25, duration=4) == []
    assert has(v(SD25, duration=3), "«duration»=3 поза межами 4…30 (або -1)")
    assert has(v(SD25, duration=31), "«duration»=31")
    assert has(v(SD25, duration=0), "«duration»=0")
    assert has(v(SD20, duration=16), "«duration»=16 поза межами 4…15")
    assert has(v(EL4, seed=-1), "«seed»=-1") and has(v(EL4, seed=2**32), "«seed»")
    assert has(v(TTV, loudness=1.5), "«loudness»=1.5")
    assert has(v(EL4, voice_settings={"stability": 1.2, "similarity_boost": 0.7}), "«voice_settings.stability»=1.2")


def test_max_items() -> None:
    refs = {"image": None, "aspect_ratio": "16:9"}
    assert v(SD25, **refs, reference_images=[f"ref:r{i}" for i in range(30)]) == []
    assert has(v(SD25, **refs, reference_images=[f"ref:r{i}" for i in range(31)]), "31 елементів, максимум 30")
    assert has(v(SD20, **refs, reference_images=[f"ref:r{i}" for i in range(10)]), "максимум 9")
    assert has(v(NB21, image_input=[f"ref:r{i}" for i in range(15)]), "«image_input»: 15 елементів, максимум 14")
    assert has(v(EL4, previous_request_ids=["a", "b", "c", "d"]), "максимум 3")


def test_string_lengths_and_pattern() -> None:
    assert has(v(TTV, text="Hola."), "«text»: 5 символів, мінімум 100")
    assert has(v(TTV, text="a" * 1001), "«text»: 1001 символів, максимум 1000")
    assert has(v(TTV, voice_description="Male voice"), "«voice_description»: 10 символів, мінімум 20")
    assert has(v(TTV, voice_description="x" * 1001), "«voice_description»: 1001 символів, максимум 1000")
    assert has(v(EL4, language_code="esp"), "«language_code»=«esp»") and has(v(EL4, language_code="ES"), "шаблону")
    assert has(v(EL4, voice_id=""), "«voice_id»: 0 символів, мінімум 1")


def test_prompt_length() -> None:
    assert v(SD25, prompt="a" * 2000) == []
    assert has(v(SD25, prompt="a" * 2001), "«prompt»: 2001 символів, максимум 2000")
    assert has(v(CF25, prompt="a" * 2001), "максимум 2000")
    assert v(SD20, prompt="a" * 4000) == [] and has(v(SD20, prompt="a" * 4001), "максимум 4000")
    assert has(v(EL4, text="a" * 10001), "«text»: 10001 символів, максимум 10000")


def test_ref_strings_accepted() -> None:
    for ok in ("ref:mina.tunnel", "ref:p1-4.03-frame", "https://cdn.example.com/a.png", "http://host/x.png",
               "media/lab/la-garganta/tp-T1-frame/a.png", "/home/u/a.png", r"C:\lab\a.png", "C:/lab/a.png",
               "data:image/png;base64,iVBORw0KGgo="):
        assert v(SD25, image=ok) == [], ok
        assert v(NB21, image_input=[ok, "ref:vale.front"]) == [], ok
    for bad, why in (("ref:", "без id"), ("ref:  ", "без id"), ("ftp://host/a.png", "схема «ftp:»"),
                     ("https://", "неповний URL"), ("", "потрібен рядок"), ("  ", "потрібен рядок")):
        assert has(v(SD25, image=bad), "«image»", why), bad
    assert has(v(NB21, image_input=["ref:a", "s3://bucket/x"]), "«image_input»[1]", "s3")
    assert has(v(SYNC, video=5), "«video» має бути рядком")


def test_avoid_and_policy() -> None:
    assert v(CF25, fps=24) == ["API: «fps» не надсилаємо: Seedance завжди дає 24 к/с"]
    assert has(v(CF25, camera_fixed=False), "«camera_fixed» не надсилаємо", "Static locked-off")
    assert has(v(NBPRO, allow_fallback_model=True), "«allow_fallback_model»=True — тримаємо False", "seedream")
    assert has(v(NB21, google_search=True), "«google_search»") and has(v(NB21, image_search=True), "«image_search»")
    assert v(NBPRO, allow_fallback_model=None) == []                  # ключа немає — API візьме false


# ---------------------------------------------------------------- іменовані правила


def test_rule_frame_xor_reference() -> None:
    msgs = v(SD25, reference_images=["ref:vale.front"])
    assert has(msgs, "image не поєднується з reference_images")
    assert has(v(CF25, reference_audios=["ref:line.wav"]), "reference_audios")
    frames = {"image": "ref:start", "last_frame_image": "ref:end", "aspect_ratio": "adaptive"}
    assert has(v(SD20, **frames, reference_videos=["ref:v"]),
               "image + last_frame_image не поєднується з reference_videos")
    assert v(SD20, **frames) == []
    assert v(SD25, reference_images=[]) == []                        # порожній список — не референсний режим


def test_rule_last_frame_needs_image() -> None:
    assert v(SD25, last_frame_image="ref:tp.T1.end") == []
    msgs = v(SD25, image=None, last_frame_image="ref:tp.T1.end")
    assert has(msgs, "last_frame_image без image")


def test_rule_audio_needs_visual_ref() -> None:
    audio = {"image": None, "aspect_ratio": "16:9", "reference_audios": ["ref:line.wav"]}
    assert has(v(SD25, **audio), "reference_audios потребує")
    assert has(v(SD20, **audio), "reference_audios потребує")
    assert v(CF25, **audio) == []                                     # Cloudflare 2.5: аудіо без фото можна
    assert v(SD25, **audio, reference_images=["ref:vale.front"]) == []
    assert v(SD25, **audio, reference_videos=["ref:clip"]) == []


def test_rule_adaptive_with_frame() -> None:
    assert has(v(SD25, aspect_ratio="16:9"), "aspect_ratio має бути «adaptive», а не «16:9»")
    assert has(v(SD25, aspect_ratio=None), "«16:9»")                 # Replicate за замовчуванням 16:9
    assert v(CF25, aspect_ratio=None) == []                           # Cloudflare за замовчуванням adaptive
    assert has(v(CF25, aspect_ratio="9:16"), "«9:16»")
    assert v(SD20, image=None, aspect_ratio="16:9") == []             # t2v — будь-яке співвідношення


def test_rule_match_input_needs_image() -> None:
    assert has(v(NBPRO, aspect_ratio=None), "match_input_image")     # текстовий якір без явного співвідношення
    assert has(v(NB21, image_input=None, aspect_ratio="match_input_image"), "задай співвідношення явно")
    assert v(NB21, aspect_ratio="match_input_image") == []


def test_rule_text_or_auto_text() -> None:
    assert has(v(TTV, text=None), "бракує text (100–1000 символів) або auto_generate_text: true")
    assert has(v(TTV, text=None, auto_generate_text=False), "бракує text")
    assert v(TTV, text=None, auto_generate_text=True) == []
    assert has(v(TTV, text=""), "бракує text")
    assert PR.route(TTV).rules == ("text_or_auto_text",)


# ---------------------------------------------------------------- ціни


def test_price_video() -> None:
    assert PR.price(SD25, {"duration": 5, "resolution": "720p"}) == pytest.approx(1.156)
    assert PR.price(SD25, {"duration": 4, "resolution": "480p"}) == pytest.approx(0.4112)
    assert PR.price(SD25, {}) == pytest.approx(0.2312 * 5)               # API за замовчуванням 720p, 5 с
    assert PR.price(SD25, {"duration": -1, "resolution": "480p"}) == pytest.approx(0.1028 * 30)
    assert PR.price(SD20, {"duration": -1, "resolution": "4k"}) == pytest.approx(15.0)
    assert PR.price(SD25, {"duration": 5, "resolution": "480p", "reference_videos": ["ref:c"]}) == pytest.approx(2.152)
    assert PR.price(CF25, I2V) == PR.price(SD25, I2V)
    assert PR.price(SD25, {"resolution": "1080p"}) is None
    assert PR.price(SD25, {"duration": "5"}) is None


def test_price_image_voice_lipsync() -> None:
    assert PR.price(NBPRO, SAMPLES[NBPRO]) == pytest.approx(0.15)
    assert PR.price(NBPRO, {"prompt": "x", "resolution": "4K"}) == pytest.approx(0.30)
    assert PR.price(NB21, {"prompt": "x"}) == pytest.approx(0.0336)
    assert PR.price(NB21, SAMPLES[NB21]) == pytest.approx(0.0504)
    assert PR.price(EL4, SAMPLES[EL4]) is None                           # ставка UNVERIFIED → null
    assert PR.price(TTV, SAMPLES[TTV]) is None
    assert PR.price(SYNC, SAMPLES[SYNC]) is None                         # тривалість не в payload


def test_video_rates() -> None:
    assert PR.video_rates(SD25) == {"480p": 0.1028, "720p": 0.2312} == PR.video_rates(CF25)
    assert PR.video_rates(SD20) == {"480p": 0.08, "720p": 0.18, "1080p": 0.45, "4k": 1.0}
    for key in (NBPRO, EL4, SYNC):
        with pytest.raises(PR.ProviderError, match="посекундних ставок"):
            PR.video_rates(key)


def test_split_path_query_body() -> None:
    parts = PR.split(EL4, SAMPLES[EL4])
    assert parts["path"] == {"voice_id": "abc123"} and parts["query"] == {"output_format": "mp3_44100_192"}
    assert "voice_id" not in parts["body"] and parts["body"]["model_id"] == "eleven_v4"
    assert PR.split(SD25, I2V) == {"path": {}, "query": {}, "body": I2V}
    for bad in ({"voice_id": None}, {"voice_id": ""}, {"voice_id": "  "}, {}):
        payload = {k: x for k, x in SAMPLES[EL4].items() if k != "voice_id"} | bad
        with pytest.raises(PR.ProviderError, match="бракує «voice_id» для шляху запиту .*bible.yaml"):
            PR.split(EL4, payload)


def test_cache_not_mutable_from_outside() -> None:
    r = PR.route(SD25)
    r.fields["resolution"]["values"].append("1080p")
    r.manual["how"] = "зіпсовано"
    r.price["values"]["1080p"] = 9.0
    assert has(v(SD25, resolution="1080p"), "«resolution»=«1080p»") and PR.price(SD25, {"resolution": "1080p"}) is None
    assert PR.route(SD25).manual["how"] != "зіпсовано"
    PR.load()[SD25].manual["surface"] = "x"
    assert PR.route(SD25).manual["surface"] == "Replicate playground"
    g = PR.generation()
    g["resolution"] = "480p"
    g.setdefault("clip_s", []).append(10)
    assert PR.generation()["resolution"] == "720p" and "clip_s" not in PR.generation()


# ---------------------------------------------------------------- профіль генерації


@pytest.fixture
def no_env_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.delenv("GENERATION_PROFILE", raising=False)
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "no.env"))     # справжній .env не впливає
    return monkeypatch


def test_generation_default_profile(no_env_profile: pytest.MonkeyPatch) -> None:
    g = PR.generation()
    assert g["name"] == "lab-2.5" and (g["clip_min_s"], g["clip_max_s"]) == (4, 10) and g["resolution"] == "720p"
    assert "dropshot" in g["surface"] and g["url"].startswith("https://") and "платний" in g["note"]


def test_generation_env_override(no_env_profile: pytest.MonkeyPatch, tmp_path: Path) -> None:
    no_env_profile.setenv("GENERATION_PROFILE", "replicate-2.5")
    g = PR.generation()
    assert g == {"name": "replicate-2.5", "clip_min_s": 4, "clip_max_s": 10, "resolution": "720p"}
    no_env_profile.delenv("GENERATION_PROFILE")
    env = tmp_path / "with.env"
    env.write_text("\ufeffGENERATION_PROFILE=replicate-2.5\n", encoding="utf-8", newline="\n")
    no_env_profile.setenv("FABRICA_ENV_FILE", str(env))
    assert PR.generation()["name"] == "replicate-2.5"                     # і з .env (BOM теж)


def test_generation_unknown_profile(no_env_profile: pytest.MonkeyPatch) -> None:
    no_env_profile.setenv("GENERATION_PROFILE", "dropshot-10s")
    with pytest.raises(PR.ProviderError, match="профіль генерації «dropshot-10s» невідомий .*manual-5s"):
        PR.generation()


def test_generation_profiles_match_video_routes() -> None:
    res = set(PR.route(SD25).fields["resolution"]["values"])
    gen = yaml.safe_load((ROOT / "prompts" / "providers.yaml").read_text(encoding="utf-8"))["generation"]
    for name, p in gen["profiles"].items():
        assert {p.get("resolution"), *p.get("resolution_by_tier", {}).values()} - {None} <= res, name
        lo, hi = PR.route(SD25).fields["duration"]["min"], PR.route(SD25).fields["duration"]["max"]
        assert all(lo <= s <= hi for s in p.get("clip_s", [p.get("clip_min_s"), p.get("clip_max_s")])), name


# ---------------------------------------------------------------- ціни


# ---------------------------------------------------------------- зламаний каталог


ROUTE = {"provider": "replicate", "model": "a/b", "kind": "image", "verified": "2026-10-07 тест",
         "prompt_field": "prompt", "prompt_max_chars": 100,
         "fields": {"prompt": {"type": "string"}, "size": {"type": "enum", "values": ["1K", "2K"], "default": "1K"},
                    "image_input": {"type": "uri_list"}, "aspect_ratio": {"type": "enum", "values": ["1:1"]}},
         "rules": ["match_input_needs_image"],
         "price": {"unit": "image", "by": "size", "values": {"1K": 0.01, "2K": 0.02}},
         "manual": {"surface": "Тест", "url": "https://example.com", "how": "встав JSON"}}


def write(tmp_path: Path, data, bom: bool = False) -> Path:
    path = tmp_path / "providers.yaml"
    text = data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(("\ufeff" if bom else "") + text, encoding="utf-8", newline="\n")
    return path


def broken(tmp_path: Path, **changes) -> str:
    raw = {**ROUTE, **changes}
    with pytest.raises(PR.ProviderError) as e:
        PR.load(write(tmp_path, {"routes": {"replicate:a/b": {k: x for k, x in raw.items() if x is not None}}}))
    return str(e.value)


def test_minimal_catalog_with_bom_and_hints(tmp_path: Path) -> None:
    path = write(tmp_path, {"hints": {"seed": "тут сіда немає"}, "routes": {"replicate:a/b": ROUTE}}, bom=True)
    assert set(PR.load(path)) == {"replicate:a/b"}
    msgs = PR.validate("replicate:a/b", {"prompt": "x", "seed": 1, "aspect_ratio": "1:1"}, path=path)
    assert msgs == ["API: невідоме поле «seed» (маршрут replicate:a/b його не приймає) — тут сіда немає"]
    assert PR.price("replicate:a/b", {"size": "2K"}, path=path) == pytest.approx(0.02)
    assert has(v(SD25, seed_x=1), "прибери його")                         # підказки тестового каталогу не протікають


@pytest.mark.parametrize("changes, expected", [
    ({"provider": "fal"}, "ключ має бути"),
    ({"kind": "audio"}, "kind «audio»"),
    ({"verified": " "}, "verified"),
    ({"fields": {}}, "fields"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "float"}}}, "type «float»"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "uri_list", "max_item": 3}}}, "невідомі ключі ['max_item']"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "enum", "values": [True, False]}}}, "в лапках"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "enum", "values": [969]}}}, "в лапках"),       # 16:9 без лапок
    ({"fields": {**ROUTE["fields"], "x": {"type": "string", "nullable": "yes"}}}, "nullable — true або false"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "enum", "values": []}}}, "непорожнього списку"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "const"}}}, "const потребує value"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "object"}}}, "object потребує fields"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "int", "min": "0"}}}, "min має бути числом"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "string", "in": "header"}}}, "in — body, query або path"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "string", "pattern": "("}}}, "pattern не regex"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "enum", "values": ["a"], "default": "b"}}}, "default: «x»=«b»"),
    ({"fields": {**ROUTE["fields"], "x": {"type": "int", "min": 0, "max": 9, "default": 10}}}, "default: «x»=10"),
    ({"prompt_field": "text"}, "prompt_field «text»"),
    ({"prompt_field": None}, "prompt_max_chars"),
    ({"fields": {**ROUTE["fields"], "prompt": {"type": "string", "max_chars": 50}}}, "межу задай один раз"),
    ({"rules": ["no_such_rule"]}, "правило «no_such_rule» невідоме"),
    ({"rules": ["adaptive_with_frame"]}, "потребує полів ['image']"),
    ({"price": {"unit": "minute", "rate": 1}}, "price: словник з unit"),
    ({"price": {"unit": "image", "by": "quality", "values": {"hi": 1}}}, "price.by «quality»"),
    ({"price": {"unit": "image", "by": "size", "values": {"1K": "дешево"}}}, "price.values"),
    ({"price": {"unit": "image", "by": "size", "values": {"1K": 0.01}}}, "ставка на кожне значення"),
    ({"price": {"unit": "image", "by": "size", "values": {"1K": 0.01, "2K": 0.02, "4K": 0.04}}}, "≠ значенням «size»"),
    ({"price": {"unit": "image", "by": "size", "values": {"1K": 0.01, "2K": 0.02}, "video_input": {"4K": 1}}},
     "price.video_input: зайві ключі ['4K']"),
    ({"price": {"unit": "second"}}, "by + values або rate"),
    ({"manual": {"surface": "Тест", "url": "https://example.com"}}, "manual"),
    ({"extra_key": 1}, "невідомі ключі ['extra_key']"),
])
def test_broken_catalog(tmp_path: Path, changes: dict, expected: str) -> None:
    assert expected in broken(tmp_path, **changes)


GEN = {"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution": "720p"}}}


@pytest.mark.parametrize("gen, expected", [
    ({"profile": "b", "profiles": GEN["profiles"]}, "generation.profile «b» немає серед profiles"),
    ({"profile": "a", "profiles": {}}, "generation: потрібні profile і profiles"),
    ([1], "generation: потрібні"),
    ({**GEN, "default": "a"}, "generation: невідомі ключі ['default']"),
    ({"profile": "a", "profiles": {"a": {"resolution": "720p"}}}, "або clip_s"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "clip_max_s": 9, "resolution": "720p"}}}, "або clip_s"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [], "resolution": "720p"}}}, "clip_s — непорожній список"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [0], "resolution": "720p"}}}, "clip_s — непорожній список"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [True], "resolution": "720p"}}}, "clip_s — непорожній список"),
    ({"profile": "a", "profiles": {"a": {"clip_min_s": 9, "clip_max_s": 4, "resolution": "720p"}}}, "clip_min_s ≤"),
    ({"profile": "a", "profiles": {"a": {"clip_min_s": 4, "resolution": "720p"}}}, "clip_min_s ≤"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5]}}}, "потрібні resolution або resolution_by_tier"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution": 720}}}, "роздільність 720 — рядок"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution": "720P"}}}, "«720P» не знає жоден відео-маршрут"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution_by_tier": ["720p"]}}}, "resolution_by_tier — словник"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution": "720p", "clip": 5}}}, "невідомі ключі ['clip']"),
    ({"profile": "a", "profiles": {"a": {"clip_s": [5], "resolution": "720p", "surface": ""}}}, "surface — непорожній"),
    ({"profile": "a", "profiles": {"a": "5s"}}, "generation.profiles.a: потрібен словник"),
])
def test_broken_generation(tmp_path: Path, gen, expected: str) -> None:
    data = yaml.safe_load((ROOT / "prompts" / "providers.yaml").read_text(encoding="utf-8"))
    with pytest.raises(PR.ProviderError) as e:
        PR.load(write(tmp_path, {**data, "generation": gen}))
    assert expected in str(e.value)


def test_generation_optional_in_catalog(tmp_path: Path, no_env_profile: pytest.MonkeyPatch) -> None:
    path = write(tmp_path, {"routes": {"replicate:a/b": ROUTE}})
    assert PR.load(path) and PR.validate("replicate:a/b", {"prompt": "x", "aspect_ratio": "1:1"}, path=path) == []
    with pytest.raises(PR.ProviderError, match="немає блоку generation"):
        PR.generation(path=path)
    good = write(tmp_path, {"routes": {"replicate:a/b": ROUTE}, "generation": GEN})
    assert PR.generation(path=good) == {"name": "a", "clip_s": [5], "resolution": "720p"}


def test_broken_catalog_file(tmp_path: Path) -> None:
    for text, expected in (("routes: [a, b]", "потрібен ключ routes"), ("routes: {}", "потрібен ключ routes"),
                           ("routes: {a: [", "YAML не читається"), ("", "потрібен ключ routes")):
        with pytest.raises(PR.ProviderError, match=expected):
            PR.load(write(tmp_path, text))
    with pytest.raises(PR.ProviderError, match="не читається"):
        PR.load(tmp_path)                                                 # тека замість файлу
    with pytest.raises(PR.ProviderError, match="hints"):
        PR.load(write(tmp_path, {"hints": ["seed"], "routes": {"replicate:a/b": ROUTE}}))
    unquoted = (ROOT / "prompts" / "providers.yaml").read_text(encoding="utf-8").replace('"on", "off"', "on, off")
    with pytest.raises(PR.ProviderError, match="apply_text_normalization"):
        PR.load(write(tmp_path, unquoted))
