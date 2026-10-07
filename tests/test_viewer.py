"""Переглядач лабораторії (fabrica/viewer.py): кроки, слоти референсів і їхній стан, payload, ручні інструкції,
попередження за групами, .md і manifest.json. Елементи збираємо руками — без компіляторів промптів."""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from fabrica import lab as lab_mod
from fabrica import lessons as lessons_mod
from fabrica import prompts as P
from fabrica import viewer as V

SLUG = "la-garganta"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
NB, SD_CF, SD_R, EL = ("replicate:google/nano-banana-2.1", "cloudflare:bytedance/seedance-2.5",
                       "replicate:bytedance/seedance-2.5", "elevenlabs:eleven_v4")


def _tpl(tid: str, version: int = 2) -> P.Template:
    return P.Template(tid, tid.split(".")[0], version, "", {}, "", "", {}, Path(f"{tid}.yaml"), f"{tid[:6]:0<12}")


def _item(iid: str, kind: str, step: int, *, route: str = "", payload: dict | None = None, needs=(), refs=(),
          produces: str | None = None, extra: dict | None = None, warnings=(), tpl: str | None = None,
          set_name: str = "1") -> P.Item:
    tid = tpl or {"image": "image.start_frame", "video": "video.i2v", "voice": "voice.line"}[kind]
    payload = payload or {}
    return P.Item(iid, set_name, kind, f"title {iid}", _tpl(tid), payload.get("prompt") or payload.get("text") or "",
                  "", {"route": route}, list(refs), produces, extra or {}, list(warnings), step, route, payload,
                  list(needs))


@pytest.fixture
def lab_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Журнал, медіа й golden — у тимчасовій теці; .env не читаємо."""
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("GENERATION_PROFILE", raising=False)
    return tmp_path


@pytest.fixture
def items() -> list[P.Item]:
    anchor = _item("cast-beto-front", "image", 1, route="replicate:google/nano-banana-pro",
                   payload={"prompt": "A portrait of Beto."}, produces="beto.front", tpl="image.character")
    plate = _item("loc-mina", "image", 3, route=NB, payload={"prompt": "The mine."}, produces="mina.plate",
                  tpl="image.location")
    tunnel = _item("loc-mina-tunnel", "image", 3, route=NB,
                   payload={"prompt": "Image 1 is the mine. A tunnel.", "image_input": ["ref:mina.plate"]},
                   refs=["mina.plate"], needs=["mina.plate"], produces="mina.tunnel", tpl="image.location")
    frame = _item("p1-1.02-frame", "image", 5, route=NB,
                  payload={"prompt": "Create one cinematic film still.", "image_input": ["ref:mina.tunnel", "ref:beto.front"],
                           "aspect_ratio": "16:9"},
                  refs=["mina.tunnel", "beto.front"], needs=["mina.tunnel", "beto.front"], produces="p1.1.02.frame",
                  warnings=["немає англійського опису шоту"])
    video = _item("p1-1.02-video", "video", 6, route=SD_CF,
                  payload={"prompt": "Single continuous shot, no cuts. <b>Beto</b> turns.", "image": "ref:p1.1.02.frame",
                           "duration": 5, "resolution": "720p", "aspect_ratio": "adaptive", "use_virtual_avatar": True},
                  refs=["p1.1.02.frame"], needs=["p1.1.02.frame"], produces="p1.1.02.c1",
                  extra={"face": "clear", "edit_window": "кліп 5 с → у монтаж 1.5 с",
                         "clip": {"index": 1, "of": 2, "gen_s": 5, "window": [0, 1.5], "start": "frame"},
                         "lessons": [{"id": "L1", "rule": "Keep the lamp steady."}],
                         "manual": [{"surface": "dropshot AI Studio", "title": "Frame to Video",
                                     "text": "Video → Seedance 2.5 → Frame to Video; 16:9 · 5s · 720p"},
                                    {"surface": "Cloudflare", "title": "curl", "cmd": "curl -X POST https://api.example"},
                                    {"surface": "Replicate playground", "json": {"prompt": "x"}}]},
                  warnings=["API: «fps» не надсилаємо", "lint: «boy» (вік) → adult man", "кадр без опису"])
    video2 = _item("p1-1.02-video-2", "video", 6, route=SD_R,
                   payload={"prompt": "The clip continues.", "image": "ref:p1.1.02.c1.last", "duration": 5},
                   needs=["p1.1.02.c1.last"], produces="p1.1.02.c2",
                   extra={"face": "partial", "clip": {"index": 2, "of": 2, "gen_s": 5, "start": "prev_last"}})
    line = _item("p1-1.02-voice1", "voice", 7, route=EL, payload={"text": "[whispering] ¿Hay alguien?", "voice_id": None},
                 needs=["beto.voice"])
    return [anchor, plate, tunnel, frame, video, video2, line]


def _rows(tmp: Path, items: list[P.Item], *rows: dict) -> list[dict]:
    """Записати результати прямо в журнал (lab.log шукає елемент через компілятор — тут його немає)."""
    by_id = {i.id: i for i in items}
    out = []
    for n, r in enumerate(rows, 1):
        it = by_id.get(r["item"])
        out.append({"id": n, "story": SLUG, "tool": "gemini", "notes": "", "file": None,
                    "prompt_sha": it.prompt_sha if it else "x", **r})
    lab_mod._dump(lab_mod.RESULTS, {"results": out})
    return out


def _png(tmp: Path, name: str) -> str:
    f = tmp / name
    f.write_bytes(PNG)
    return f.as_posix()


# ---------------------------------------------------------------- кроки, слоти, попередження


def test_steps_fallback_and_prompts_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(P, "STEPS", raising=False)
    st = V.steps()
    assert list(st) == [1, 2, 3, 4, 5, 6, 7] and st[6]["key"] == "video"
    assert all(s["title"] and s["todo"] and s["tool"] and s["done"] for s in st.values())
    monkeypatch.setattr(P, "STEPS", [{"step": 1, "key": "identity", "title": "Якорі", "todo": "зробити якорі"},
                                     {"key": "video", "title": "Кліпи"}], raising=False)
    st = V.steps()
    assert st[1]["title"] == "Якорі" and st[1]["todo"] == "зробити якорі" and st[1]["tool"]   # tool — із запасної
    assert st[6]["title"] == "Кліпи" and st[6]["done"]
    monkeypatch.setattr(P, "STEPS", {"lines": {"title": "Голос реплік", "todo": "озвучити"}, 8: {"title": "Звук"}},
                        raising=False)
    st = V.steps()
    assert st[7]["title"] == "Голос реплік" and st[8]["title"] == "Звук" and list(st)[-1] == 8


def test_steps_use_step_n_and_single_done(monkeypatch: pytest.MonkeyPatch) -> None:
    st = V.steps()                                                                 # справжні prompts.STEPS
    for s in P.STEPS:
        assert st[s.n]["title"] == s.title and st[s.n]["todo"] == s.todo and st[s.n]["tool"] == s.tool
        assert "n" not in st[s.n]
    assert st[2]["done"] == "" and st[6]["done"] == ""                             # «Готово —» уже в todo
    assert st[4]["done"] and st[7]["done"]
    monkeypatch.setattr(P, "STEPS", (P.Step(8, "sound", "Звук", "зібрати звук", "DAW"),
                                     P.Step(1, "identity", "Якорі", "зробити якорі", "NB Pro")))
    st = V.steps()                                                                 # номер — Step.n, не позиція
    assert st[8]["title"] == "Звук" and st[1]["title"] == "Якорі" and st[2]["key"] == "views"


def test_slots_follow_payload_order(items: list[P.Item]) -> None:
    by = {i.id: i for i in items}
    assert V.slots(by["p1-1.02-frame"]) == [("Image 1", "mina.tunnel"), ("Image 2", "beto.front")]
    assert V.slots(by["p1-1.02-video"]) == [("стартовий кадр", "p1.1.02.frame")]
    assert V.slots(by["p1-1.02-video-2"]) == [("стартовий кадр", "p1.1.02.c1.last")]
    assert V.slots(by["p1-1.02-voice1"]) == [("потрібно", "beto.voice")]
    fl = _item("x", "video", 6, payload={"image": "ref:a.frame", "last_frame_image": "ref:a.end", "prompt": "p"},
               needs=["a.frame", "a.end"])
    assert V.slots(fl) == [("стартовий кадр", "a.frame"), ("кінцевий кадр", "a.end")]
    legacy = _item("tp-T1-frame", "image", 0, refs=["mateo.front", "mina.plate"])        # старий формат без payload
    assert V.slots(legacy) == [("Image 1", "mateo.front"), ("Image 2", "mina.plate")]


def test_split_warnings() -> None:
    g = V.split_warnings(["API: «fps» зайве", "lint: «boy» (вік)", "немає опису", "API: ще одне"])
    assert g == {"API": ["«fps» зайве", "ще одне"], "lint": ["«boy» (вік)"], "дані": ["немає опису"]}


def test_manual_falls_back_to_catalog(items: list[P.Item]) -> None:
    frame = items[3]
    m = V.manual(frame)
    assert m and m[0]["surface"] == "Replicate playground" and m[0]["json"] == frame.payload
    assert V.manual(items[4])[0]["title"] == "Frame to Video"
    assert V.manual(_item("x", "image", 0)) == []                                        # без маршруту — нічого


# ---------------------------------------------------------------- стан референсів


def test_ref_states(lab_dirs: Path, items: list[P.Item]) -> None:
    by = {i.id: i for i in items}
    tunnel, clip = _png(lab_dirs, "tunnel.png"), _png(lab_dirs, "clip.png")
    _rows(lab_dirs, items,
          {"item": "loc-mina-tunnel", "score": 4, "file": tunnel},
          {"item": "loc-mina", "score": 2, "file": _png(lab_dirs, "plate.png")},
          {"item": "cast-beto-front", "score": 5, "file": _png(lab_dirs, "beto.png")},
          {"item": "p1-1.02-video", "score": 5, "file": "media/lab/clip.mp4", "last_frame": clip})
    lab_mod._dump(lab_mod.GOLDEN, {"templates": {}, "items": {SLUG: {"cast-beto-front": {
        "prompt_sha": by["cast-beto-front"].prompt_sha, "result": 3}}}})
    pack = V.Pack(SLUG, items)
    s = pack.ref("mina.tunnel")
    assert s.state == "ok" and s.file == tunnel and s.label(SLUG) == "✓ є (4/5)" and s.ready
    s = pack.ref("beto.front")
    assert s.state == "golden" and s.row["id"] == 3 and s.label(SLUG).startswith("★ golden")
    s = pack.ref("mina.plate")
    assert s.state == "weak" and "крок 3 · loc-mina" in s.label(SLUG) and not s.ready
    s = pack.ref("p1.1.02.frame")
    assert s.state == "missing" and s.label(SLUG) == "ще немає — спершу крок 5 · p1-1.02-frame"
    s = pack.ref("p1.1.02.c1.last")                                       # last_frame рядка кліпу
    assert s.state == "ok" and s.file == clip and s.producer.id == "p1-1.02-video"
    assert pack.ref("beto.voice").label(SLUG) == "ще немає — джерела в пакеті немає (збери пакет разом із кастингом)"
    assert pack.ref("nope.last").state == "missing"
    for ref in ("mina.tunnel", "beto.front", "mina.plate", "p1.1.02.frame", "p1.1.02.c1.last"):   # той самий файл
        f = lab_mod.ref_file(SLUG, ref, items)
        assert (Path(pack.ref(ref).file) if pack.ref(ref).file else None) == f, ref


def test_ref_ranks_like_lab_and_missing_local_file(lab_dirs: Path, items: list[P.Item]) -> None:
    """Стара 5/5 vs поточна 4/4 — як у lab.ref_file (поточна версія); файл із журналу, якого тут немає, — не мініатюра."""
    old, cur = _png(lab_dirs, "old.png"), _png(lab_dirs, "cur.png")
    _rows(lab_dirs, items, {"item": "loc-mina", "score": 5, "file": old, "prompt_sha": "oldsha"},
          {"item": "loc-mina", "score": 4, "file": cur})
    s = V.Pack(SLUG, items).ref("mina.plate")
    assert s.file == cur and s.row["score"] == 4 and Path(cur) == lab_mod.ref_file(SLUG, "mina.plate", items)
    _rows(lab_dirs, items, {"item": "loc-mina", "score": 5, "file": "media/lab/la-garganta/loc-mina/x.png"})
    s = V.Pack(SLUG, items).ref("mina.plate")
    assert s.state == "nofile" and s.file is None and not s.ready
    assert s.label(SLUG) == "✓ 5/5, але файлу немає на цьому комп'ютері"
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    assert "<img" not in _card(text, "loc-mina-tunnel") and "<img" not in _card(text, "loc-mina")
    assert html.escape("#1 gemini · 5/5 · файлу немає на цьому комп'ютері") in _card(text, "loc-mina")
    _rows(lab_dirs, items, {"item": "loc-mina", "score": 4})
    assert V.Pack(SLUG, items).ref("mina.plate").label(SLUG) == "оцінка 4/5 без файлу — запиши результат з --file"


def test_last_frame_states(lab_dirs: Path, items: list[P.Item]) -> None:
    _rows(lab_dirs, items, {"item": "p1-1.02-video", "score": 4, "file": "media/lab/clip.mp4"})
    s = V.Pack(SLUG, items).ref("p1.1.02.c1.last")
    assert s.state == "clip" and "fabrica lab log p1-1.02-video-last --story la-garganta --tool other --score 4 --file" \
        in s.label(SLUG)                                                        # --tool і --score обов'язкові в CLI
    frame = _png(lab_dirs, "last.png")
    _rows(lab_dirs, items, {"item": "p1-1.02-video", "score": 4, "file": "media/lab/clip.mp4"},
          {"item": "p1-1.02-video-last", "score": 4, "file": frame})              # кадр записано руками
    s = V.Pack(SLUG, items).ref("p1.1.02.c1.last")
    assert s.state == "ok" and s.file == frame
    explicit = _item("p1-1.02-lastframe", "image", 6, produces="p1.1.02.c1.last")        # окремий елемент кадру
    _rows(lab_dirs, items, {"item": "p1-1.02-lastframe", "score": 5, "file": frame})
    s = V.Pack(SLUG, [*items, explicit]).ref("p1.1.02.c1.last")
    assert s.state == "ok" and s.producer.id == "p1-1.02-lastframe"


def test_golden_without_file_uses_best_file(lab_dirs: Path, items: list[P.Item]) -> None:
    f = _png(lab_dirs, "plate.png")
    _rows(lab_dirs, items, {"item": "loc-mina", "score": 4, "file": f}, {"item": "loc-mina", "score": 5})
    g = {"templates": {}, "items": {SLUG: {"loc-mina": {"prompt_sha": items[1].prompt_sha, "result": 2}}}}
    s = V.Pack(SLUG, items, g=g).ref("mina.plate")
    assert s.state == "golden" and s.file == f and s.ready


def test_next_item(lab_dirs: Path, items: list[P.Item]) -> None:
    pack = V.Pack(SLUG, items, rows=[], g={"templates": {}, "items": {}})
    assert pack.next_item(items).id == "cast-beto-front"
    rows = _rows(lab_dirs, items, {"item": "cast-beto-front", "score": 5, "file": _png(lab_dirs, "b.png")})
    pack = V.Pack(SLUG, items, rows=rows, g={"templates": {}, "items": {}})
    assert pack.done(items[0]) and pack.next_item(items).id == "loc-mina"         # тунель чекає на плиту


# ---------------------------------------------------------------- HTML


def test_html_groups_by_step_with_cards(lab_dirs: Path, items: list[P.Item]) -> None:
    _rows(lab_dirs, items, {"item": "loc-mina-tunnel", "score": 4, "file": _png(lab_dirs, "tunnel.png")})
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    heads = re.findall(r'<section class="step" data-step="(\d+)">', text)
    assert heads == ["1", "3", "5", "6", "7"]
    st = V.steps()
    for n in (1, 3, 5, 6, 7):
        assert html.escape(st[n]["todo"]) in text and html.escape(st[n]["done"]) in text
    assert "Що робити:" in text and "Чим:" in text and "Готово, коли:" in text and "готово 0 з 2" in text
    assert text.count('data-step-filter="') == 6                                  # усі + 5 кроків
    assert 'data-flag="warn"' in text and 'id="search"' in text and 'data-kind-filter="video"' in text
    assert f'<span class="badge route">{SD_CF}</span>' in text
    assert text.count('<span class="badge face">обличчя → Cloudflare</span>') == 1   # лише face: clear
    assert "Далі: крок 1 · <code>cast-beto-front</code>" in text


def _card(text: str, iid: str) -> str:
    m = re.search(rf'<article class="card"[^>]*>(?:(?!</article>).)*?<code>{re.escape(iid)}</code>.*?</article>', text, re.DOTALL)
    assert m, iid
    return m.group(0)


def test_html_card_contents(lab_dirs: Path, items: list[P.Item]) -> None:
    tunnel = _png(lab_dirs, "tunnel.png")
    _rows(lab_dirs, items, {"item": "loc-mina-tunnel", "score": 4, "file": tunnel})
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    video = _card(text, "p1-1.02-video")
    pre = re.search(r'<pre id="(i\d+-j)">(.*?)</pre>', video, re.DOTALL)
    assert json.loads(html.unescape(pre.group(2))) == items[4].payload           # payload — рівно JSON для API
    assert f'data-target="{pre.group(1)}"' in video
    assert "&lt;b&gt;Beto&lt;/b&gt;" in video and "<b>Beto</b>" not in video
    assert video.count("<details class=\"manual\"") == 3 and video.count("<details class=\"manual\" open>") == 1
    assert video.index("<details class=\"manual\" open><summary>dropshot AI Studio — Frame to Video") > 0
    assert "curl -X POST https://api.example" in video and "Копіювати" in video
    assert "кліп 1 з 2" in video and "генерувати 5 с" in video and "у монтаж: 0–1.5 с кліпу" not in video
    assert "монтаж: кліп 5 с → у монтаж 1.5 с" in video and "старт: стартовий кадр" in video
    assert "⚠️ API (1)" in video and "⚠️ lint (1)" in video and "⚠️ дані (1)" in video
    assert "«fps» не надсилаємо" in video and "API: «fps»" not in video
    assert "враховано уроків: 1" in video and "Keep the lamp steady." in video
    assert "стартовий кадр</b> = <code>p1.1.02.frame</code>" in video
    assert "ще немає — спершу крок 5 · p1-1.02-frame" in video
    assert "<option selected>dropshot</option>" in video and "Копіювати команду журналу" in video
    frame = _card(text, "p1-1.02-frame")
    assert "Image 1</b> = <code>mina.tunnel</code>" in frame and "✓ є (4/5)" in frame
    assert "mina.tunnel · 4/5" in frame and "<img src=" in frame and "loc-mina-tunnel" in frame
    assert "Image 2</b> = <code>beto.front</code>" in frame and "ще немає — спершу крок 1 · cast-beto-front" in frame
    assert "обличчя → Cloudflare" not in frame and "Replicate playground" in frame       # інструкція з каталогу
    assert "<option selected>replicate</option>" in frame and "Endpoint" in frame          # endpoint із каталогу
    v2 = _card(text, "p1-1.02-video-2")
    assert "старт: останній кадр попереднього кліпу" in v2 and "обличчя: partial" in v2
    assert "<code>p1.1.02.c1.last</code>" in v2 and "спершу крок 6 · p1-1.02-video" in v2
    assert "файл: останній кадр результату <code>p1-1.02-video</code>" in v2


def test_html_phone_css_and_js_kept(lab_dirs: Path, items: list[P.Item]) -> None:
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in text
    assert "@media (max-width:640px)" in text and "--bg:#0f1115" in text
    assert "uv run fabrica lab log " in text and "localStorage" in text and "data-step-filter" in V.JS
    assert "профіль кліпів «lab-2.5»" in text                                     # є відео → активний профіль


def test_html_legacy_items_without_step(lab_dirs: Path) -> None:
    legacy = [_item("tp-T1-frame", "image", 0, refs=["mateo.front"], produces="tp.T1.frame"),
              _item("tp-T1-video", "video", 0, refs=["tp.T1.frame"])]
    text = V.build_html(SLUG, "test-pack", legacy, lab_dirs / "out")
    assert '<section class="step" data-step="0">' in text and "Без кроку" in text
    assert "data-step-filter" not in text.split("<main>")[0]                       # один крок — без кнопок
    assert "ще немає — спершу tp-T1-frame" in text and "Payload" not in text


# ---------------------------------------------------------------- .md і пакет


def test_item_md(items: list[P.Item]) -> None:
    md = V.item_md(SLUG, items[4])
    assert f"- Маршрут: `{SD_CF}` · обличчя → Cloudflare" in md and "- Крок 6 · " in md
    assert "потрібно: p1.1.02.frame" in md and "кліп 1 з 2" in md and "монтаж: кліп 5 с → у монтаж 1.5 с" in md
    body = md.split("## Payload (тіло запиту до API)\n\n```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(body) == items[4].payload
    assert "- стартовий кадр = `p1.1.02.frame`" in md
    assert "## Руками: dropshot AI Studio — Frame to Video" in md and "Video → Seedance 2.5 → Frame to Video" in md
    assert "```bash\ncurl -X POST https://api.example\n```" in md
    assert "> ⚠️ API: «fps» не надсилаємо" in md and "> ⚠️ lint: «boy» (вік) → adult man" in md
    assert "uv run fabrica lab log p1-1.02-video --story la-garganta" in md


def test_write_package_manifest(lab_dirs: Path, items: list[P.Item]) -> None:
    out = lab_dirs / "out"
    (out / SLUG / "1").mkdir(parents=True)
    (out / SLUG / "1" / "stale.md").write_text("old", encoding="utf-8")
    index = V.write_package(SLUG, "1", items, out=out)
    folder = index.parent
    assert not (folder / "stale.md").exists() and all((folder / f"{i.id}.md").exists() for i in items)
    raw = (folder / "manifest.json").read_bytes()
    assert b"\r\n" not in raw
    m = json.loads(raw.decode("utf-8"))
    assert m["story"] == SLUG and m["set"] == "1" and [e["id"] for e in m["items"]] == [i.id for i in items]
    e = next(e for e in m["items"] if e["id"] == "p1-1.02-video")
    assert e["route"] == SD_CF and e["step"] == 6 and e["needs"] == ["p1.1.02.frame"]
    assert e["payload"] == items[4].payload and e["face"] == "clear" and e["clip"]["index"] == 1
    assert e["edit_window"] and e["prompt_sha"] == items[4].prompt_sha
    assert "<!doctype html>" in index.read_text(encoding="utf-8")


# ---------------------------------------------------------------- контракт із компілятором (рев'ю)


CF_HOW = ("Ключі лише з оточення. macOS / zsh:\n\n  curl -X POST \"https://api.example/$ACC\" --data-binary \"@payload.json\""
          "\n\nWindows / PowerShell — саме curl.exe:\n\n  curl.exe -X POST \"https://api.example/$env:ACC\"\n\nВідповідь — url.")


def test_manual_endpoint_body_and_commands(lab_dirs: Path) -> None:
    """endpoint і body (ElevenLabs) — на картці й у .md; curl із how — окремі блоки «Команда», не в прозі."""
    ep = "POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_192 — заголовок xi-api-key"
    body = json.dumps({"text": "[whispering] ¿Hay alguien?", "model_id": "eleven_v4"}, ensure_ascii=False, indent=2)
    line = _item("p1-1.02-voice1", "voice", 7, route=EL, payload={"text": "¿Hay alguien?"},
                 extra={"manual": [{"surface": "ElevenLabs API (JSON)", "url": "https://elevenlabs.io", "endpoint": ep,
                                    "how": "Тіло запиту — рівно цей JSON.", "body": body}]})
    video = _item("p1-1.02-video", "video", 6, route=SD_CF, payload={"prompt": "p", "image": "ref:x"},
                  extra={"manual": [{"surface": "Cloudflare Workers AI (curl)", "endpoint": "POST https://cf", "how": CF_HOW}]})
    text = V.build_html(SLUG, "1", [line, video], lab_dirs / "out")
    card = _card(text, "p1-1.02-voice1")
    assert "<span>Endpoint</span>" in card and html.escape(ep) in card
    assert "<span>Тіло запиту (JSON)</span>" in card and html.escape(body) in card
    card = _card(text, "p1-1.02-video")
    pres = re.findall(r'<pre id="i1-m0-how\d+">(.*?)</pre>', card, re.DOTALL)
    assert [html.unescape(x).split(" ")[0] for x in pres] == ["curl", "curl.exe"]
    assert '<p class="how">Ключі лише з оточення. macOS / zsh:</p>' in card and "curl" not in card.split("<pre")[0]
    assert '<p class="how">Відповідь — url.</p>' in card and "white-space:pre-wrap}" in V.CSS
    md = V.item_md(SLUG, line)
    assert f"https://elevenlabs.io\n\nEndpoint: `{ep}`\n\nТіло запиту — рівно цей JSON.\n" in md   # абзаци окремо
    assert f"```json\n{body}\n```" in md
    md = V.item_md(SLUG, video)
    assert '```text\ncurl -X POST "https://api.example/$ACC" --data-binary "@payload.json"\n```' in md
    assert "```text\ncurl.exe -X POST" in md and "Відповідь — url." in md


def test_face_badge_only_on_cloudflare_route(lab_dirs: Path) -> None:
    frame = _item("p1-1.02-frame", "image", 5, route=NB, payload={"prompt": "p"}, extra={"face": "clear"})
    video = _item("p1-1.02-video", "video", 6, route=SD_CF, payload={"prompt": "p"}, extra={"face": "clear"})
    text = V.build_html(SLUG, "1", [frame, video], lab_dirs / "out")
    assert "обличчя → Cloudflare" not in _card(text, "p1-1.02-frame") and "обличчя: clear" in _card(text, "p1-1.02-frame")
    assert '<span class="badge face">обличчя → Cloudflare</span>' in _card(text, "p1-1.02-video")
    assert "Cloudflare" not in V.item_md(SLUG, frame).split("\n## ")[0]
    assert f"- Маршрут: `{SD_CF}` · обличчя → Cloudflare" in V.item_md(SLUG, video)


def _shots(set_name: str) -> list[P.Item]:
    """1.01 (два кліпи, state_out на останньому) → 1.02 (кадр + кліп) → 1.03 (handoff continue: без кадру)."""
    pre = "p1" if set_name == "1" else "tp"
    clip = {"of": 2, "gen_s": 5, "window": [0, 5]}
    return [
        _item(f"{pre}-1.01-frame", "image", 5, extra={"shot": "1.01", "which": "first"}, set_name=set_name),
        _item(f"{pre}-1.02-frame", "image", 5, extra={"shot": "1.02", "which": "first"}, set_name=set_name),
        _item(f"{pre}-1.02-end", "image", 5, extra={"shot": "1.02", "which": "last"}, set_name=set_name),
        _item(f"{pre}-1.01-video", "video", 6, extra={"shot": "1.01", "clip": {**clip, "index": 1, "start": "frame"}},
              set_name=set_name),
        _item(f"{pre}-1.01-video-2", "video", 6, set_name=set_name, extra={
            "shot": "1.01", "clip": {**clip, "index": 2, "start": "prev_last"},
            "state_out": ["the lamp lies on the floor", "Beto is soaked"]}),
        _item(f"{pre}-1.02-video", "video", 6, set_name=set_name,
              extra={"shot": "1.02", "clip": {**clip, "of": 1, "index": 1, "start": "frame"}, "state_out": ["dust"]}),
        _item(f"{pre}-1.03-video", "video", 6, set_name=set_name, extra={
            "shot": "1.03", "clip": {"index": 1, "of": 1, "start": "prev_last", "start_ref": "p1.1.02.c1.last",
                                     "start_item": f"{pre}-1.02-video"}}),
    ]


def test_carry_over_state_to_next_shot(lab_dirs: Path) -> None:
    items = _shots("1")
    assert V.carry_over(items) == {"1.02": ["the lamp lies on the floor", "Beto is soaked"], "1.03": ["dust"]}
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    head = html.escape(V.STATE_IN)
    for iid in ("p1-1.02-frame", "p1-1.02-video"):                             # стартовий кадр і кліп 1
        assert head in _card(text, iid) and "<li>the lamp lies on the floor</li><li>Beto is soaked</li>" in _card(text, iid)
    assert head not in _card(text, "p1-1.02-end") and head not in _card(text, "p1-1.01-frame")
    assert "<li>dust</li>" in _card(text, "p1-1.03-video")                       # handoff — кліп 1 без кадру
    assert html.escape(V.STATE_OUT) in _card(text, "p1-1.01-video-2")
    md = (V.write_package(SLUG, "1", items, out=lab_dirs / "out").parent / "p1-1.02-frame.md").read_text(encoding="utf-8")
    assert f"## {V.STATE_IN}\n\n- the lamp lies on the floor\n- Beto is soaked" in md
    assert V.carry_over(_shots("test-pack")) == {}                              # тести незалежні


def test_clip_chips_from_compiler_keys() -> None:
    t2v = V._clip_parts({"index": 1, "of": 1, "gen_s": 5, "window": [0, 2], "start": "none", "start_ref": None,
                         "start_item": None})
    assert t2v == ["кліп 1 з 1", "генерувати 5 с", "у монтаж: 0–2 с кліпу", "старт: без кадру (лише текст)"]
    hand = V._clip_parts({"index": 1, "of": 1, "gen_s": 5, "window": [0, 2], "start": "prev_last",
                          "start_ref": "p1.1.02.c1.last", "start_item": "p1-1.02-video"}, window=False)
    assert hand == ["кліп 1 з 1", "генерувати 5 с", "старт: останній кадр попереднього шоту",
                    "файл старту: результат «p1-1.02-video» — його останній кадр"]
    c2 = V._clip_parts({"index": 2, "of": 2, "start": "prev_last", "start_ref": "p1.1.02.c1.last",
                        "start_item": "p1-1.02-video", "extra_key": "x"})
    assert "старт: останній кадр попереднього кліпу" in c2 and "extra_key: x" in c2
    assert not [c for c in c2 if c.startswith(("start_ref", "start_item"))]


def test_tool_default_is_earliest_surface() -> None:
    nb = _item("x", "image", 5, route=NB)
    assert V._tool(nb, [{"surface": "AI Studio / Gemini · dropshot Image"}]) == "ai-studio"
    assert V._tool(nb, [{"surface": "dropshot AI Studio (Seedance 2.5)"}]) == "dropshot"
    assert V._tool(nb, [{"surface": "ElevenLabs API (JSON)"}]) == "elevenlabs"
    assert V._tool(_item("y", "video", 6, route=SD_CF), []) == "cloudflare"
    assert V._tool(_item("z", "video", 6), []) == V.TOOLS[0]


def test_lessons_show_rules(lab_dirs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    it = _item("p1-1.02-video", "video", 6, route=SD_R, payload={"prompt": "p"}, extra={"lessons": ["L3", "L9"]})
    monkeypatch.setattr(lessons_mod, "load", lambda slug: [{"id": "L3", "rule": "The camera stays locked off."}])
    assert V._lessons(it, SLUG) == ["L3: The camera stays locked off.", "L9"]
    text = V.build_html(SLUG, "1", [it], lab_dirs / "out")
    assert "враховано уроків: 2" in text and "<li>L3: The camera stays locked off.</li>" in text
    assert "- L3: The camera stays locked off." in V.item_md(SLUG, it)

    def broken(slug: str) -> list[dict]:
        raise lessons_mod.LessonError("зламано")

    monkeypatch.setattr(lessons_mod, "load", broken)
    assert V._lessons(it, SLUG) == ["L3", "L9"]


def test_links_encoded_and_js_quoting(lab_dirs: Path, items: list[P.Item]) -> None:
    f = _png(lab_dirs, "a #1?.png")
    _rows(lab_dirs, items, {"item": "loc-mina-tunnel", "score": 4, "file": f})
    text = V.build_html(SLUG, "1", items, lab_dirs / "out")
    assert 'src="../a%20%231%3F.png"' in text and 'src="../a #1?.png"' not in text
    assert "qf(file)" in V.JS and "\\u2019" in V.JS and '\\"' not in V.JS        # без \" — PowerShell його не знає
    assert "--file '<шлях>' --notes '<що вийшло>'" in V.item_md(SLUG, items[0])


VOID = frozenset({"meta", "img", "input", "br", "hr", "link", "source"})


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.bad: list[str] = []
        self.ids: list[str] = []
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        self.ids += [a["id"]] if "id" in a else []
        self.targets += [a["data-target"]] if "data-target" in a else []
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in VOID and (not self.stack or self.stack.pop() != tag):
            self.bad.append(tag)


@pytest.fixture(scope="module")
def real() -> dict[str, list[P.Item]]:
    casting = P.build(SLUG, "casting")
    return {"casting": casting, "test-pack": P.build(SLUG, "test-pack")}


@pytest.mark.parametrize("set_name", ["test-pack", "casting"])
def test_contract_with_compiler(lab_dirs: Path, real: dict[str, list[P.Item]], set_name: str) -> None:
    """Справжній пакет компілятора: сирих полів кліпу немає, «обличчя → Cloudflare» лише не на фото, кожен endpoint і
    body з extra.manual — на сторінці, теги збалансовані, кожна кнопка «Копіювати» має свій блок."""
    items = real[set_name]
    text = V.build_html(SLUG, set_name, items, lab_dirs / "out", producers=real["casting"])
    assert "start_ref:" not in text and "start_item:" not in text and "старт: none" not in text
    for card in re.findall(r'<article class="card" data-kind="image".*?</article>', text, re.DOTALL):
        assert "обличчя → Cloudflare" not in card
    for it in items:
        for m in it.extra.get("manual") or []:
            for key in ("endpoint", "body"):
                assert not m.get(key) or html.escape(str(m[key])) in text, (it.id, key)
    tags = _Tags()
    tags.feed(text)
    assert not tags.bad and not tags.stack and len(tags.ids) == len(set(tags.ids))
    assert set(tags.targets) <= set(tags.ids)
