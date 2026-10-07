"""Студія (fabrica/studio.py): справжній сервер на 127.0.0.1 з ефемерним портом у потоці, кожен endpoint через
urllib. Дані — копія історії в tmp (tests/test_rewrite.make_copy), журнал / golden / прогрес / медіа — теж у tmp;
переписувач — FAKE-бекенд (справжні Ollama / Claude не викликаються); інтерфейс — 3-рядкова заглушка в tmp."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import pytest
import yaml

from fabrica import lab as lab_mod
from fabrica import lessons as lessons_mod
from fabrica import progress as progress_mod
from fabrica import prompts as P
from fabrica import rewrite as R
from fabrica import studio as studio_mod

from tests.test_rewrite import ACTION, RULE, SLUG, fake, make_copy, video_answer

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
MP4 = b"\x00\x00\x00\x18ftypmp42fake-clip"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    story = make_copy(tmp_path, monkeypatch)
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<!doctype html>\n<title>Студія</title>\n<script src=\"/static/app.js\"></script>\n",
                                   encoding="utf-8")
    (ui / "app.js").write_text("console.log('студія');\n", encoding="utf-8")
    monkeypatch.setattr(studio_mod, "UI", ui)
    monkeypatch.setattr(R, "backend_status", lambda: {"name": "fake", "model": "m", "ok": True, "note": ""})
    return {"tmp": tmp_path, "story": story}


@pytest.fixture
def base(env: dict) -> str:
    srv = studio_mod.make_server(0, SLUG, "first30", quiet=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()
        srv.server_close()


def call(url: str, body: dict | bytes | None = None, headers: dict | None = None) -> tuple[int, dict | bytes, dict]:
    data = json.dumps(body).encode("utf-8") if isinstance(body, dict) else body
    h = {"Content-Type": "application/json"} if isinstance(body, dict) else {}
    req = urllib.request.Request(url, data=data, headers=h | (headers or {}), method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw, status, hdrs = r.read(), r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw, status, hdrs = e.read(), e.code, dict(e.headers)
    if hdrs.get("Content-Type", "").startswith("application/json"):
        return status, json.loads(raw.decode("utf-8")), hdrs
    return status, raw, hdrs


def state(base: str, seq: str = "first30") -> dict:
    status, data, _ = call(f"{base}/api/state?story={SLUG}&seq={urllib.parse.quote(seq)}")
    assert status == 200, data
    return data


def item(data: dict, item_id: str) -> dict:
    return next(i for i in data["items"] if i["id"] == item_id)


def multipart(fields: dict, filename: str, content: bytes, ctype: str) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="upload"; filename="{filename}"\r\n'
                 f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
    return b"".join(parts) + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


# ---------------------------------------------------------------- статика й медіа


def test_index_static_and_traversal(base: str) -> None:
    status, body, h = call(f"{base}/")
    assert status == 200 and b"<title>" in body and h["Content-Type"].startswith("text/html")
    status, body, h = call(f"{base}/static/app.js")
    assert status == 200 and h["Content-Type"].startswith("text/javascript")
    for bad in ("/static/../studio.py", "/static/%2e%2e/studio.py", "/static/..%2fstudio.py", "/static/nope.js"):
        status, body, _ = call(base + bad)
        assert status == 404 and "error" in body, bad
    status, body, _ = call(f"{base}/nope")
    assert status == 404 and "немає такої сторінки" in body["error"]


def test_missing_ui_is_json_404(base: str, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(studio_mod, "UI", env["tmp"] / "no-ui")
    status, body, _ = call(f"{base}/")
    assert status == 404 and "studio_ui" in body["error"]


def test_media_only_from_media_and_prompts_out(base: str, env: dict) -> None:
    f = lab_mod.MEDIA / SLUG / "x" / "a.png"
    f.parent.mkdir(parents=True)
    f.write_bytes(PNG)
    status, body, h = call(f"{base}/media?path={urllib.parse.quote(str(f))}")
    assert status == 200 and body == PNG and h["Content-Type"] == "image/png"
    out = P.OUT / SLUG / "casting" / "index.html"
    out.parent.mkdir(parents=True)
    out.write_text("<p>пакет</p>", encoding="utf-8")
    assert call(f"{base}/media?path={urllib.parse.quote(str(out))}")[0] == 200
    secret = env["tmp"] / "secret.txt"
    secret.write_text("x", encoding="utf-8")
    sneaky = str(lab_mod.MEDIA / SLUG / ".." / ".." / ".." / "secret.txt")
    for bad in ("pyproject.toml", ".env", "../../etc/passwd", "/etc/passwd", str(secret), sneaky, ""):
        status, body, _ = call(f"{base}/media?path={urllib.parse.quote(bad)}")
        assert status == 404 and "error" in body, bad


def test_media_range_for_video(base: str) -> None:
    f = lab_mod.MEDIA / SLUG / "v" / "clip.mp4"
    f.parent.mkdir(parents=True)
    f.write_bytes(MP4)
    url = f"{base}/media?path={urllib.parse.quote(str(f))}"
    status, body, h = call(url, headers={"Range": "bytes=4-11"})
    assert status == 206 and body == MP4[4:12] and h["Content-Range"] == f"bytes 4-11/{len(MP4)}"
    assert h["Content-Type"] == "video/mp4"
    assert call(url, headers={"Range": "bytes=999-"})[0] == 416


def test_foreign_origin_and_host_rejected(base: str) -> None:
    status, body, _ = call(f"{base}/api/status", {"story": SLUG, "item": "x", "status": "skip"},
                           headers={"Origin": "https://evil.example"})
    assert status == 403 and "127.0.0.1" in body["error"]
    status, body, _ = call(f"{base}/api/lessons?story={SLUG}", headers={"Host": "evil.example:80"})
    assert status == 403
    assert call(f"{base}/api/lessons?story={SLUG}", headers={"Origin": "null"})[0] == 403
    assert call(f"{base}/api/lessons?story={SLUG}", headers={"Origin": base})[0] == 200


# ---------------------------------------------------------------- стан


def test_state_first30(base: str) -> None:
    data = state(base)
    want = [i.id for i in P.sequence_items(SLUG, "first30")]
    assert [i["id"] for i in data["items"]] == want
    assert data["story"] == SLUG and data["seq"] == "first30"
    names = [s["name"] for s in data["sequences"]]
    assert names[0] == "first30" and {"part:1", "casting", "test-pack"} <= set(names)
    assert data["profile"]["name"] == "lab-2.5" and data["profile"]["clip_max_s"] == 10
    bud = data["budget"]                                                     # ліміт тестів first30 — $40
    assert bud["limit"] == 40 and bud["spent"] == 0 and bud["runs"] == 0 and bud["per_pass"] > 0
    assert bud["left_passes"] == int(40 // bud["per_pass"])
    assert data["rewrite_backend"] == {"name": "fake", "model": "m", "ok": True, "note": ""}
    assert [s["n"] for s in data["steps"]] == [1, 2, 3, 4, 5, 6, 7] and data["steps"][0]["title"]
    assert data["progress"] | {"next": None} == {"done": 0, "total": len(want), "next": None, "approved": 0,
                                                 "skipped": 0}
    assert data["progress"]["next"] == want[0]                    # якір лише текстом — потреб немає
    steps = [i["step"] for i in data["items"]]
    assert steps == sorted(steps)
    v = item(data, "p1-1.02-video")
    for key in ("id", "step", "kind", "title", "route", "prompt", "payload", "prompt_sha", "template", "status",
                "golden", "needs", "manual", "warnings", "extra", "results", "source", "stale"):
        assert key in v, key
    assert v["status"] == "todo" and v["stale"] is False and v["golden"] is False and v["results"] == []
    assert v["needs"][0] | {"label": ""} == {"ref": "p1.1.02.frame", "slot": "стартовий кадр", "state": "missing",
                                             "item": "p1-1.02-frame", "file": None, "score": None, "label": "",
                                             "url": None}
    assert set(v["warnings"]) == {"api", "lint", "data"}
    assert v["manual"][0]["surface"].startswith("dropshot") and "p1-1.02-frame" in v["manual"][0]["text"]
    assert all({"surface", "title", "text", "json", "cmd", "endpoint", "body", "note"} <= set(m) for m in v["manual"])
    assert v["extra"]["clip"]["index"] == 1 and v["extra"]["edit_window"]
    assert v["source"]["kind"] == "shot" and v["source"]["key"] == "1.02" and "frame" in v["source"]["fields"]
    assert item(data, "cast-lupita-1994")["source"]["kind"] == "member"
    tunnel = item(data, "loc-mina-tunnel")["source"]
    assert (tunnel["kind"], tunnel["key"], tunnel["target"]) == ("location", "mina.tunnel", "prompt_en")
    assert "desc" in tunnel["editable"] and "overridden" not in tunnel
    voice = item(data, "p1-1.02-voice1")
    assert voice["source"] | {"fields": {}} == {"kind": "line", "key": "1.02", "part": 1, "n": 1, "target": "line",
                                                "fields": {}, "editable": ["delivery"]}


def test_state_other_sequences_and_errors(base: str) -> None:
    cast = state(base, "casting")
    assert cast["seq"] == "casting" and all(i["id"].startswith(("cast-", "loc-")) for i in cast["items"])
    part = state(base, "part:1")
    assert {i["id"] for i in part["items"]} >= {i["id"] for i in state(base)["items"] if i["id"].startswith("p1-")}
    frame = item(part, "p1-1.02-frame")                           # референси кастингу — з кастингу
    assert [n["item"] for n in frame["needs"]][:1] == ["loc-mina-tunnel"]
    status, body, _ = call(f"{base}/api/state?story={SLUG}&seq=nope")
    assert status == 400 and "nope" in body["error"]
    status, body, _ = call(f"{base}/api/state?story=no-such&seq=first30")
    assert status == 404 and "no-such" in body["error"]


# ---------------------------------------------------------------- статус


def test_status_and_stale(base: str, env: dict) -> None:
    status, body, _ = call(f"{base}/api/status", {"story": SLUG, "item": "cast-lupita-1994", "status": "in_work"})
    assert (status, body) == (200, {"ok": True})
    data = state(base)
    assert item(data, "cast-lupita-1994")["status"] == "in_work"
    saved = progress_mod.load(SLUG)["cast-lupita-1994"]
    assert saved["prompt_sha"] == item(data, "cast-lupita-1994")["prompt_sha"]
    status, body, _ = call(f"{base}/api/status", {"story": SLUG, "item": "cast-lupita-1994", "status": "nah"})
    assert status == 400 and "невідомий статус" in body["error"]
    status, body, _ = call(f"{base}/api/status", {"story": SLUG, "item": "cast-nobody-1994", "status": "skip"})
    assert status in (400, 404) and "cast-nobody-1994" in body["error"]
    progress_mod.set_status(SLUG, "cast-monica-1994", "done", "old-sha")      # промпт з того часу змінився
    m = item(state(base), "cast-monica-1994")
    assert m["status"] == "todo" and m["stale"] is True
    assert call(f"{base}/api/status", {"story": SLUG, "item": "cast-lupita-1994", "status": "skip"})[0] == 200
    data = state(base)
    assert data["progress"]["done"] == 1 and data["progress"]["skipped"] == 1
    assert data["progress"]["next"] == "cast-monica-1994"


# ---------------------------------------------------------------- журнал і golden


def test_log_with_local_file_then_media(base: str, env: dict) -> None:
    src = env["tmp"] / "Мій кадр.png"
    src.write_bytes(PNG)
    status, body, _ = call(f"{base}/api/log", {"story": SLUG, "item": "cast-lupita-1994", "tool": "AI-Studio",
                                               "score": 5, "notes": "добре", "file": str(src)})
    assert status == 200, body
    e = body["entry"]
    assert e["item"] == "cast-lupita-1994" and e["score"] == 5 and e["tool"] == "ai-studio"
    assert body["warnings"] == [] and body["status"] == "done"
    stored = Path(e["file"])
    assert stored.is_file() and stored.is_relative_to(lab_mod.MEDIA / SLUG / "cast-lupita-1994")
    assert call(base + body["url"])[1] == PNG
    data = state(base)
    lupita = item(data, "cast-lupita-1994")
    assert lupita["status"] == "done" and lupita["results"][0]["current"] is True and lupita["results"][0]["url"]
    assert data["progress"]["done"] == 1 and data["progress"]["next"] != "cast-lupita-1994"


def test_log_multipart_upload(base: str) -> None:
    body, ctype = multipart({"story": SLUG, "item": "loc-mina", "tool": "gemini", "score": "3", "notes": "темно"},
                            "плита шахти?.png", PNG, "image/png")
    status, res, _ = call(f"{base}/api/log", body, headers={"Content-Type": ctype})
    assert status == 200, res
    f = Path(res["entry"]["file"])
    assert f.read_bytes() == PNG and f.parent == lab_mod.MEDIA / SLUG / "loc-mina"
    assert f.name.endswith("_gemini_upload.png")                     # «плита шахти?.png» → латиниця для Windows
    assert all(c.isascii() and (c.isalnum() or c in "-_.") for c in f.name)
    assert res["status"] == "in_work" and item(state(base), "loc-mina")["status"] == "in_work"


def test_log_video_upload_warns_without_ffmpeg(base: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lab_mod.shutil, "which", lambda name: None)
    body, ctype = multipart({"story": SLUG, "item": "p1-1.01-video", "tool": "dropshot", "score": "4"},
                            "clip.mp4", MP4, "video/mp4")
    status, res, _ = call(f"{base}/api/log", body, headers={"Content-Type": ctype})
    assert status == 200, res
    assert res["entry"]["file"].endswith(".mp4") and "last_frame" not in res["entry"]
    assert any("ffmpeg" in w for w in res["warnings"])
    assert item(state(base), "p1-1.01-video")["status"] == "done"


def test_log_errors(base: str) -> None:
    status, body, _ = call(f"{base}/api/log", {"story": SLUG, "item": "loc-mina", "tool": "x", "score": 9})
    assert status == 400 and "від 1 до 5" in body["error"]
    status, body, _ = call(f"{base}/api/log", {"story": SLUG, "item": "loc-mina", "tool": "x", "score": 4,
                                               "file": "/no/such/file.png"})
    assert status == 400 and "файлу немає" in body["error"]
    status, body, _ = call(f"{base}/api/log", b"{not json", headers={"Content-Type": "application/json"})
    assert status == 400 and "JSON" in body["error"]


def test_approve(base: str, env: dict) -> None:
    status, body, _ = call(f"{base}/api/approve", {"story": SLUG, "item": "loc-mina"})
    assert status == 400 and "оцінкою ≥ 4" in body["error"]
    status, body, _ = call(f"{base}/api/approve", {"story": SLUG, "item": "loc-mina", "force": True})
    assert status == 200 and "golden" in body["message"]
    m = item(state(base), "loc-mina")
    assert m["golden"] is True and m["status"] == "approved"
    src = env["tmp"] / "t.png"
    src.write_bytes(PNG)
    call(f"{base}/api/log", {"story": SLUG, "item": "loc-mina-tunnel", "tool": "gemini", "score": 4, "file": str(src)})
    assert call(f"{base}/api/approve", {"story": SLUG, "item": "loc-mina-tunnel"})[0] == 200
    t = item(state(base), "loc-mina-tunnel")
    assert t["status"] == "approved" and t["golden"] is True
    frame = item(state(base), "p1-1.02-frame")
    assert frame["needs"][0]["state"] == "golden" and frame["needs"][0]["url"]


# ---------------------------------------------------------------- переписувач і уроки


def test_rewrite_apply_lessons_flow(base: str, env: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer())
    before = item(state(base), "p1-1.03-video")
    ov = env["story"] / "lab" / "overrides.yaml"
    ov_before = ov.read_bytes()
    status, body, _ = call(f"{base}/api/rewrite", {"story": SLUG, "item": "p1-1.03-video",
                                                   "feedback": "ліхтарі мерехтять"})
    assert status == 200, body
    p = body["proposal"]
    assert set(p) >= {"id", "item", "backend", "changes", "lesson", "prompt_old", "prompt_new", "warnings_new"}
    assert p["prompt_old"] == before["prompt"] and ACTION in p["prompt_new"] and "_patch" not in p
    assert p["changes"][0]["target"] == "overlay" and p["changes"][0]["field"] == "action"
    assert ov.read_bytes() == ov_before                                        # пропозиція нічого не пише
    status, body, _ = call(f"{base}/api/rewrite/apply", {"story": SLUG, "proposal": p["id"], "save_lesson": True,
                                                         "rule": RULE})
    assert status == 200, body
    assert body["ok"] is True and body["item"]["id"] == "p1-1.03-video"
    assert ACTION in body["item"]["prompt"] and body["item"]["prompt_sha"] != before["prompt_sha"]
    assert body["item"]["extra"]["lessons"] == ["L1"] and body["item"]["source"]["overridden"] == ["action"]
    assert yaml.safe_load(ov.read_text(encoding="utf-8"))["shots"]["p1-1.03"]["action"] == ACTION
    after = item(state(base), "p1-1.03-video")
    assert after["prompt"] == body["item"]["prompt"]                          # кеш скинуто: файли змінились
    status, body, _ = call(f"{base}/api/lessons?story={SLUG}")
    assert status == 200 and [x["id"] for x in body["lessons"]] == ["L1"] and body["lessons"][0]["active"] is True
    assert {"id", "at", "item", "problem", "rule", "scope", "active"} <= set(body["lessons"][0])
    assert call(f"{base}/api/lessons/toggle", {"story": SLUG, "id": "L1", "active": False})[1] == {"ok": True}
    assert lessons_mod.all(SLUG)[0]["active"] is False
    assert item(state(base), "p1-1.03-video")["extra"]["lessons"] == []
    status, body, _ = call(f"{base}/api/lessons/toggle", {"story": SLUG, "id": "L1", "active": "no"})
    assert status == 400
    status, body, _ = call(f"{base}/api/rewrite/apply", {"story": SLUG, "proposal": p["id"]})
    assert status == 400 and "уже записано" in body["error"]


def test_rewrite_errors(base: str, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer(changes=[{"field": "tier", "value": "hero"}]))
    status, body, _ = call(f"{base}/api/rewrite", {"story": SLUG, "item": "p1-1.03-video", "feedback": "x"})
    assert status == 400 and "tier" in body["error"]
    status, body, _ = call(f"{base}/api/rewrite/apply", {"story": SLUG, "proposal": "rw-nope"})
    assert status == 400 and "rw-nope" in body["error"]
    status, body, _ = call(f"{base}/api/rewrite", {"story": SLUG, "feedback": "x"})
    assert status == 400 and "item" in body["error"]


def test_lesson_avoid_shows_as_lint(base: str, env: dict) -> None:
    lessons_mod.add(SLUG, {"rule": "Keep the camera on a tripod.", "scope": {"kind": "video"},
                           "avoid": [r"\bcamcorder\b"]})
    data = state(base)
    v = item(data, "p1-1.03-video")
    assert "L1" in v["extra"]["lessons"] and v["extra"]["lessons_text"] == ["L1: Keep the camera on a tripod."]
    assert any(w.startswith("урок L1: «camcorder»") for w in v["warnings"]["lint"])
    long = item(data, "p1-1.02-video")                    # урок не вмістився в 2000 символів — заборона все одно діє
    if "L1" not in long["extra"]["lessons"]:
        assert any("урок L1 не вмістився" in w for w in long["warnings"]["data"])
    assert any(w.startswith("урок L1: «camcorder»") for w in long["warnings"]["lint"])


def test_server_binds_localhost_only(env: dict) -> None:
    srv = studio_mod.make_server(0, SLUG, quiet=True)
    try:
        assert srv.server_address[0] == "127.0.0.1"
    finally:
        srv.server_close()


def test_safe_name() -> None:
    assert studio_mod.safe_name("Мій кадр (1).PNG") == "1.png"
    assert studio_mod.safe_name("../../evil.sh") == "evil.sh"
    assert studio_mod.safe_name("") == "upload"


def test_cli_studio_no_open(monkeypatch: pytest.MonkeyPatch, env: dict) -> None:
    from typer.testing import CliRunner

    from fabrica.cli import app

    seen = {}
    monkeypatch.setattr(studio_mod, "serve", lambda *a, **k: seen.update(args=a, kw=k))
    r = CliRunner().invoke(app, ["studio", "--story", SLUG, "--sequence", "first30", "--port", "9999", "--no-open"])
    assert r.exit_code == 0, r.output
    assert seen["args"] == (SLUG, "first30", 9999) and seen["kw"]["open_browser"] is False
