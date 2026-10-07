"""Етап video (fabrica/video.py): план за item.route / item.payload, golden-ворота для ПОТОЧНОГО промпту, кліпи
k ≥ 2 і handoff з останнього кадру кліпу цієї черги, golden-кліп лабораторії не генеруємо вдруге, кеш, облік витрат,
невідома ціна блокує, заглушки провайдерів — без мережі. Елементи збираємо руками (prompts.build підмінено), ffmpeg
підмінено; + кошторис costs (call_usd, estimate_items, load_rates із запасом із каталогу маршрутів)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fabrica import costs as costs_mod
from fabrica import lab as lab_mod
from fabrica import prompts as P
from fabrica import providers as providers_mod
from fabrica import video as video_mod
from fabrica.cli import app
from fabrica.ledger import AutomationDisabled, Ledger, Limits

SLUG = "la-garganta"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
NB = "replicate:google/nano-banana-2.1"
SD_R, SD_CF = "replicate:bytedance/seedance-2.5", "cloudflare:bytedance/seedance-2.5"
TEMPLATES = {t: P.Template(t, t.split(".")[0], 2, "", {}, "", "", {}, Path(f"{t}.yaml"), f"{t[:7]:0<12}")
             for t in ("image.start_frame", "video.i2v", "video.first_last", "video.t2v", "voice.line")}


def _item(iid: str, kind: str, tpl: str, route: str, payload: dict, produces: str | None = None,
          extra: dict | None = None, warnings=()) -> P.Item:
    refs = video_mod.refs_in(payload)
    return P.Item(iid, "1", kind, f"title {iid}", TEMPLATES[tpl], payload.get("prompt") or payload.get("text", ""), "",
                  {"route": route}, refs, produces, extra or {}, list(warnings), 5 if kind == "image" else 6, route,
                  payload, refs)


def _clip(prompt: str, image: str | None, **kw) -> dict:
    p = {"prompt": prompt, **({"image": image, "aspect_ratio": "adaptive"} if image else {"aspect_ratio": "16:9"}),
         "duration": 5, "resolution": "720p", "generate_audio": True, "output_format": "mp4", "seed": 7}
    return {**p, **kw}


def _frame(iid: str, ref: str) -> P.Item:
    return _item(iid, "image", "image.start_frame", NB,
                 {"prompt": f"Create one cinematic film still {iid}.", "aspect_ratio": "16:9"}, ref)


@pytest.fixture
def items() -> list[P.Item]:
    frame = _frame
    return [
        frame("p1-1.02-frame", "p1.1.02.frame"), frame("p1-1.03-frame", "p1.1.03.frame"),
        frame("p1-1.03-end", "p1.1.03.end"),
        _item("p1-1.02-video", "video", "video.i2v", SD_R, _clip("Beto turns slowly.", "ref:p1.1.02.frame"),
              "p1.1.02.c1", {"shot": "1.02", "clip": {"index": 1, "of": 2}}),
        _item("p1-1.02-video-2", "video", "video.i2v", SD_R, _clip("The action continues.", "ref:p1.1.02.c1.last"),
              "p1.1.02.c2", {"shot": "1.02", "clip": {"index": 2, "of": 2}}),
        _item("p1-1.03-video", "video", "video.first_last", SD_CF,
              _clip("Generate a continuous transition.", "ref:p1.1.03.frame", last_frame_image="ref:p1.1.03.end",
                    use_virtual_avatar=True), "p1.1.03.c1", {"shot": "1.03"}),
        _item("p1-1.04-video", "video", "video.t2v", SD_R, _clip("A dark tunnel, dust drifts.", None), "p1.1.04.c1"),
        _item("p1-1.02-voice1", "voice", "voice.line", "elevenlabs:eleven_v4",
              {"text": "¿Hay alguien?", "model_id": "eleven_v4", "voice_id": "v1"}),
    ]


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, items: list[P.Item]) -> Path:
    """Тимчасові output/, журнал, медіа й golden; prompts.build і шаблони — з елементів вище; ffmpeg — фейк."""
    out = tmp_path / "out"
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))

    def build(slug, set_name, kinds=None, only=None, out_root=None, templates=None):
        found = [i for i in items if i.set == set_name and (not kinds or i.kind in kinds)]
        return [i for i in found if not only or i.id == only]

    monkeypatch.setattr(P, "build", build)
    monkeypatch.setattr(P, "load_templates", lambda root=None: dict(TEMPLATES))
    monkeypatch.setattr(lab_mod, "extract_last_frame", fake_extract)
    return out


def fake_extract(video: Path, out: Path | None = None, *, item_id: str = "") -> tuple[Path | None, str | None]:
    out = out or video.with_name(f"{video.stem}.last.png")
    out.parent.mkdir(parents=True, exist_ok=True)                         # як справжній: теку створює сам
    out.write_bytes(PNG + video.read_bytes()[-16:])                      # кадр «залежить» від кліпу
    return out, None


def golden_templates(*ids: str) -> None:
    g = lab_mod.golden()
    for t in ids or TEMPLATES:
        g["templates"][t] = {"version": TEMPLATES[t].version, "sha": TEMPLATES[t].sha}
    lab_mod._dump(lab_mod.GOLDEN, g)


def approve(tmp: Path, item_id: str, name: str | None = None, data: bytes = PNG) -> Path:
    f = tmp / (name or f"{item_id}.png")
    f.write_bytes(data)
    e = lab_mod.log(SLUG, item_id, "gemini", 5, f, "ок")
    lab_mod.approve(SLUG, item_id)
    return Path(e["file"])


class FakeProvider:
    name = "fake"

    def __init__(self, fail_submit: video_mod.ProviderError | None = None, states=("running", "succeeded")) -> None:
        self.submitted: list[tuple[str, dict, dict[str, Path]]] = []
        self.fail_submit, self.states = fail_submit, list(states)

    def submit(self, route, payload, files):
        if self.fail_submit:
            raise self.fail_submit
        self.submitted.append((route, payload, dict(files)))
        return f"job-{len(self.submitted)}"

    def poll(self, job_id):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return state, (f"https://example/{job_id}.mp4" if state == "succeeded" else "boom")

    def download(self, url, dest):
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42" + url.encode())


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    lg = Ledger(tmp_path / "fabrica.sqlite", Limits.of(per_episode=160, daily=60, monthly=900))
    yield lg
    lg.close()


def run(out: Path, **kw):
    kw.setdefault("log", lambda *_: None)
    kw.setdefault("sleep", lambda _s: None)
    return video_mod.run(SLUG, 1, out, **kw)


def queue(out: Path) -> dict:
    return json.loads((out / SLUG / "part1" / "video" / "queue.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- план


def test_dry_run_explains_every_block(world: Path, items: list[P.Item]) -> None:
    jobs = {j.item_id: j for j in run(world, dry_run=True)}
    assert list(jobs) == ["p1-1.02-video", "p1-1.02-video-2", "p1-1.03-video", "p1-1.04-video"]   # лише відео
    assert all(j.state == "blocked" for j in jobs.values())
    c1, c2, fl, t2v = jobs.values()
    assert any("video.i2v@v2 не golden" in r for r in c1.reasons)
    assert any(r.startswith("стартовий кадр «p1.1.02.frame»: p1-1.02-frame не golden") for r in c1.reasons)
    assert any("«p1.1.02.c1.last»: чекає на кліп p1-1.02-video цієї черги" in r for r in c2.reasons)
    assert any(r.startswith("кінцевий кадр «p1.1.03.end»") for r in fl.reasons)
    assert len(t2v.reasons) == 1 and "video.t2v" in t2v.reasons[0]              # без референсів — лише шаблон
    assert c1.route == SD_R and fl.route == SD_CF and (c1.clip, c2.clip) == (1, 2) and c2.shot_id == "1.02"
    assert c1.resolution == "720p" and c1.duration_s == 5
    assert c1.estimate_usd == pytest.approx(providers_mod.price(SD_R, items[3].payload)) == pytest.approx(1.156)
    q = queue(world)
    assert q["part"] == 1 and [j["item_id"] for j in q["jobs"]] == list(jobs)


def test_stale_golden_frame_is_not_used(world: Path, tmp_path: Path, items: list[P.Item]) -> None:
    """Регресія: golden кадру для старої версії промпту — автоматика його НЕ бере (раніше брала старий файл)."""
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "pending" and job.first_frame and job.files["p1.1.02.frame"] == job.first_frame
    items[0].payload["prompt"] += " Beto now holds a lamp."                     # промпт кадру змінили
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "blocked" and job.first_frame is None and job.key is None
    assert any("golden для старої версії промпту" in r and "fabrica lab approve p1-1.02-frame" in r
               for r in job.reasons)


def test_golden_per_item_template(world: Path, tmp_path: Path) -> None:
    golden_templates("video.i2v")                                              # first_last і t2v — ще ні
    for iid in ("p1-1.02-frame", "p1-1.03-frame", "p1-1.03-end"):
        approve(tmp_path, iid)
    jobs = {j.item_id: j for j in video_mod.plan(SLUG, 1, world)}
    assert jobs["p1-1.02-video"].state == "pending"
    assert jobs["p1-1.03-video"].state == "blocked" and jobs["p1-1.03-video"].reasons == [
        "шаблон video.first_last@v2 не golden (draft)"]
    assert set(jobs["p1-1.03-video"].files) == {"p1.1.03.frame", "p1.1.03.end"}   # обидва кадри знайдено
    assert jobs["p1-1.04-video"].reasons[0].startswith("шаблон video.t2v@v2 не golden")


def test_api_errors_and_warnings_block(world: Path, tmp_path: Path, items: list[P.Item]) -> None:
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    clip = items[3]
    clip.payload["fps"] = 24
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "blocked" and any(r.startswith("API: невідоме поле «fps»") for r in job.reasons)
    del clip.payload["fps"]
    clip.warnings = ["lint: «boy» (вік) → adult man"]
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "blocked" and "lint: «boy» (вік) → adult man" in job.reasons
    lab_mod.log(SLUG, clip.id, "dropshot", 4)
    lab_mod.approve(SLUG, clip.id)                                              # людина бачила й затвердила
    assert video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0].state == "pending"


def test_legacy_item_without_payload_is_blocked(world: Path, items: list[P.Item]) -> None:
    items[6].route, items[6].payload = "", {}
    job = video_mod.plan(SLUG, 1, world, only="p1-1.04-video")[0]
    assert job.state == "blocked" and "старий формат" in job.reasons[0]


def test_duration_and_resolution_follow_route_defaults(world: Path, items: list[P.Item]) -> None:
    t2v = items[6].payload
    del t2v["duration"], t2v["resolution"]                                     # API візьме типові: 5 с, 720p
    job = video_mod.plan(SLUG, 1, world, only="p1-1.04-video")[0]
    assert (job.duration_s, job.resolution, job.estimate_usd) == (5.0, "720p", pytest.approx(1.156))
    t2v.update(duration=-1, resolution="480p")                                 # -1 — оплата до максимуму маршруту
    job = video_mod.plan(SLUG, 1, world, only="p1-1.04-video")[0]
    assert (job.duration_s, job.resolution, job.estimate_usd) == (30.0, "480p", pytest.approx(0.1028 * 30))


def test_cache_key_depends_on_payload_route_and_files(tmp_path: Path) -> None:
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    a.write_bytes(PNG)
    b.write_bytes(PNG + b"x")
    p = _clip("x", "ref:s")
    base = video_mod.cache_key(SD_R, p, {"s": a})
    assert base == video_mod.cache_key(SD_R, dict(p), {"s": tmp_path / "a.png"})
    assert base != video_mod.cache_key(SD_R, {**p, "seed": 8}, {"s": a})
    assert base != video_mod.cache_key(SD_CF, p, {"s": a})
    assert base != video_mod.cache_key(SD_R, p, {"s": b})


# ---------------------------------------------------------------- запуск


def test_generates_clips_in_order_then_caches(world: Path, tmp_path: Path, ledger: Ledger, items: list[P.Item],
                                              automation_on: None) -> None:
    golden_templates()
    frame = approve(tmp_path, "p1-1.02-frame")
    fake = FakeProvider()
    jobs = run(world, provider=fake, ledger=ledger, only="1.02")
    assert [j.state for j in jobs] == ["done", "done"] and len(fake.submitted) == 2
    folder = world / SLUG / "part1" / "video"
    (r1, p1, f1), (r2, p2, f2) = fake.submitted
    assert (r1, p1) == (SD_R, items[3].payload) and f1 == {"p1.1.02.frame": frame}   # рівно payload лабораторії
    assert (r2, p2) == (SD_R, items[4].payload)
    assert f2 == {"p1.1.02.c1.last": folder / f"{jobs[0].key}.last.png"}         # кадр кліпу 1 цієї черги
    assert jobs[0].last_frame == f"{jobs[0].key}.last.png" and (folder / jobs[0].file).is_file()
    assert jobs[1].first_frame == (folder / jobs[0].last_frame).as_posix()
    assert ledger.spent(SLUG, 1) == pytest.approx(sum(j.estimate_usd for j in jobs)) and ledger.unsettled() == []
    again = FakeProvider()
    assert [j.state for j in run(world, provider=again, ledger=ledger, only="1.02")] == ["done", "done"]
    assert again.submitted == []
    q = {j["item_id"]: j for j in queue(world)["jobs"]}                       # --only: у queue.json уся черга
    assert len(q) == 4 and [q[i]["state"] for i in ("p1-1.02-video", "p1-1.02-video-2")] == ["done", "done"]
    assert [q[i]["provider_job"] for i in ("p1-1.02-video", "p1-1.02-video-2")] == ["job-1", "job-2"]   # перенесено
    run(world, dry_run=True)                                                   # і сухий запуск id задач не стирає
    assert queue(world)["jobs"][0]["provider_job"] == "job-1"


def test_clip_two_from_lab_golden_last_frame(world: Path, tmp_path: Path) -> None:
    golden_templates()
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video-2")[0]
    assert job.state == "blocked"
    clip = approve(tmp_path, "p1-1.02-video", "clip.mp4", b"\x00\x00\x00\x18ftypmp42lab")   # last_frame — фейк ffmpeg
    row = lab_mod.results(SLUG)[-1]
    assert row["last_frame"] and Path(row["last_frame"]).parent == clip.parent
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video-2")[0]
    assert job.state == "pending" and job.first_frame == row["last_frame"]


def test_lab_golden_clip_is_not_paid_twice(world: Path, tmp_path: Path, ledger: Ledger, items: list[P.Item],
                                           automation_on: None) -> None:
    """Golden-кліп лабораторії — готовий (source lab), черга його не генерує; кліп 2 — з ЙОГО кадру. Регресія: кадр
    став stale → кліп 1 черги блокувався, а кліп 2 ішов з лабораторного кадру; потім черга робила свій кліп 1 і
    платила за кліп 2 вдруге (інший ключ), а кліп 2 не продовжував кліп 1 черги."""
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    lab_clip = approve(tmp_path, "p1-1.02-video", "clip.mp4", b"\x00\x00\x00\x18ftypmp42lab")
    lab_frame = lab_mod.results(SLUG)[-1]["last_frame"]
    items[0].payload["prompt"] += " changed"                                  # кадр кліпу 1 тепер stale
    c1, c2 = video_mod.plan(SLUG, 1, world, only="1.02")
    assert (c1.state, c1.source, c1.file, c1.last_frame) == ("done", "lab", lab_clip.as_posix(), lab_frame)
    assert c2.state == "pending" and c2.first_frame == lab_frame
    fake = FakeProvider()
    jobs = run(world, provider=fake, ledger=ledger, only="1.02")
    assert [j.state for j in jobs] == ["done", "done"] and len(fake.submitted) == 1     # лише кліп 2
    assert fake.submitted[0][2] == {"p1.1.02.c1.last": Path(lab_frame)}
    assert ledger.spent(SLUG, 1) == pytest.approx(jobs[1].estimate_usd)
    assert run(world, provider=FakeProvider(), ledger=ledger, only="1.02")[1].key == jobs[1].key   # і далі кеш


def test_lab_clip_without_frame_and_missing_file(world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    golden_templates()
    monkeypatch.setattr(lab_mod, "extract_last_frame", lambda v, o=None, *, item_id="": (None, "немає ffmpeg"))
    lab_clip = approve(tmp_path, "p1-1.02-video", "clip.mp4", b"\x00\x00\x00\x18ftypmp42lab")   # без last_frame
    monkeypatch.setattr(lab_mod, "extract_last_frame", fake_extract)
    c1, c2 = video_mod.plan(SLUG, 1, world, only="1.02")                     # кадр витягує черга, у свою теку
    folder = world / SLUG / "part1" / "video"
    assert c2.state == "pending" and c2.first_frame == (folder / "p1-1.02-video.last.png").as_posix()
    assert c1.source == "lab" and c1.last_frame == c2.first_frame
    lab_clip.unlink()                                                          # golden є, файлу на диску немає
    c1, c2 = video_mod.plan(SLUG, 1, world, only="1.02")
    assert c1.state == "blocked" and any("на диску немає" in r and "вдруге не генеруємо" in r for r in c1.reasons)
    assert c2.state == "blocked" and any("чекає на кліп p1-1.02-video" in r for r in c2.reasons)


def test_clip_k_never_starts_from_foreign_frame(world: Path, tmp_path: Path) -> None:
    """Кліп k-1 у цій черзі ще не готовий → кліп k чекає, навіть якщо в лабораторії є кадр «<кліп>-last» ≥ 4."""
    golden_templates()
    lab_mod.log(SLUG, "p1-1.02-video", "dropshot", 5)                          # golden без файлу кліпу
    lab_mod.approve(SLUG, "p1-1.02-video")
    frame = tmp_path / "manual.png"
    frame.write_bytes(PNG)
    lab_mod.log(SLUG, "p1-1.02-video-last", "ffmpeg", 5, frame)
    c1, c2 = video_mod.plan(SLUG, 1, world, only="1.02")
    assert c1.state == "blocked" and c1.source == "queue"                      # стартового кадру ще немає
    assert c2.state == "blocked" and c2.first_frame is None
    assert any("чекає на кліп p1-1.02-video цієї черги" in r for r in c2.reasons)


def test_handoff_continue_from_previous_shot_queue_clip(world: Path, tmp_path: Path, ledger: Ledger,
                                                       items: list[P.Item], automation_on: None) -> None:
    """handoff continue: шот 1.05 без стартового кадру — кліп 1 з останнього кадру останнього кліпу 1.02 (черга)."""
    items.insert(5, _item("p1-1.05-video", "video", "video.i2v", SD_R, _clip("Beto keeps walking.", "ref:p1.1.02.c2.last"),
                          "p1.1.05.c1", {"shot": "1.05", "clip": {"index": 1, "of": 1, "start": "prev_last"}}))
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    assert any("чекає на кліп p1-1.02-video-2" in r for r in video_mod.plan(SLUG, 1, world, only="1.05")[0].reasons)
    fake = FakeProvider()
    jobs = {j.item_id: j for j in run(world, provider=fake, ledger=ledger)}
    assert [s[1]["prompt"] for s in fake.submitted][:3] == ["Beto turns slowly.", "The action continues.",
                                                           "Beto keeps walking."]
    c2, b1 = jobs["p1-1.02-video-2"], jobs["p1-1.05-video"]
    folder = world / SLUG / "part1" / "video"
    assert b1.state == "done" and b1.first_frame == (folder / f"{c2.key}.last.png").as_posix()
    assert fake.submitted[2][2] == {"p1.1.02.c2.last": folder / f"{c2.key}.last.png"}


def test_ffmpeg_failure_after_download(world: Path, tmp_path: Path, ledger: Ledger, monkeypatch: pytest.MonkeyPatch,
                                       automation_on: None) -> None:
    """ffmpeg не витягнув кадр: попередження в лозі, last_frame None, кліп 2 заблоковано з тією ж причиною, без падіння."""
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    monkeypatch.setattr(lab_mod, "extract_last_frame",
                        lambda v, o=None, *, item_id="": (None, f"немає ffmpeg — {item_id}-last руками"))
    logs: list[str] = []
    fake = FakeProvider()
    c1, c2 = run(world, provider=fake, ledger=ledger, only="1.02", log=logs.append)
    assert c1.state == "done" and c1.last_frame is None and len(fake.submitted) == 1
    assert any("⚠️ немає ffmpeg — p1-1.02-video-last" in m for m in logs)
    assert c2.state == "blocked" and any("немає ffmpeg" in r for r in c2.reasons)


def test_clip_key_survives_reextracted_frame(world: Path, tmp_path: Path, ledger: Ledger,
                                            automation_on: None) -> None:
    """Ключ кліпу 2 — від sha кліпу 1, а не від байтів PNG: інший ffmpeg / кодер PNG не робить кеш-промаху."""
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    c1, c2 = run(world, provider=FakeProvider(), ledger=ledger, only="1.02")
    frame = world / SLUG / "part1" / "video" / c1.last_frame
    frame.write_bytes(PNG + b"other-encoder")
    again = video_mod.plan(SLUG, 1, world, only="1.02")
    assert again[1].key == c2.key and again[1].state == "done"


def test_unknown_price_blocks(world: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Регресія: ціни немає ні в каталозі, ні в COSTS.md → був кошторис $0 і pending (резерв $0 обходив ліміти)."""
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    monkeypatch.setattr(providers_mod, "price", lambda *_a, **_k: None)
    monkeypatch.setattr(costs_mod, "load_rates", lambda *a, **k: {"480p": 0.11})   # 720p ставки немає
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "blocked" and job.estimate_usd == 0.0
    assert any(r.startswith(f"немає ціни для {SD_R} @ 720p") for r in job.reasons)
    monkeypatch.setattr(costs_mod, "load_rates", lambda *a, **k: {"720p": 0.25})   # запас — COSTS.md × тривалість
    job = video_mod.plan(SLUG, 1, world, only="p1-1.02-video")[0]
    assert job.state == "pending" and job.estimate_usd == pytest.approx(1.25)


def test_stub_providers_stop_before_any_reservation(world: Path, tmp_path: Path, ledger: Ledger,
                                                   automation_on: None) -> None:
    golden_templates()
    for iid in ("p1-1.03-frame", "p1-1.03-end"):
        approve(tmp_path, iid)
    with pytest.raises(video_mod.VideoError, match="Cloudflare Workers AI ще не підключено"):
        run(world, ledger=ledger, only="1.03")
    with pytest.raises(video_mod.VideoError, match="Replicate ще не підключено"):
        run(world, ledger=ledger, only="1.04")
    assert ledger.spent() == 0 and ledger.unsettled() == []


def test_provider_rejects_before_charge(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    fake = FakeProvider(fail_submit=video_mod.ProviderError("HTTP 422: bad input", charged=False))
    with pytest.raises(video_mod.ProviderError):
        run(world, provider=fake, ledger=ledger, only="p1-1.02-video")
    assert ledger.spent() == 0 and ledger.unsettled() == []
    assert queue(world)["jobs"][0]["state"] == "failed"


def test_failed_generation_keeps_reservation(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    with pytest.raises(video_mod.ProviderError):
        run(world, provider=FakeProvider(states=("running", "failed")), ledger=ledger, only="p1-1.02-video")
    assert len(ledger.unsettled()) == 1                    # провайдер міг списати гроші — звірити з рахунком


def test_timeout(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    with pytest.raises(video_mod.ProviderError, match="немає результату"):
        run(world, provider=FakeProvider(states=("running",)), ledger=ledger, only="p1-1.02-video", timeout_s=0)


def test_lab_mode_blocks_before_submit(world: Path, tmp_path: Path, ledger: Ledger,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_ENABLED", "false")
    golden_templates()
    approve(tmp_path, "p1-1.02-frame")
    fake = FakeProvider()
    with pytest.raises(AutomationDisabled):
        run(world, provider=fake, ledger=ledger, only="p1-1.02-video")
    assert fake.submitted == []


def test_cli_dry_run(world: Path) -> None:
    r = CliRunner().invoke(app, ["video", SLUG, "1", "--out", str(world), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Відео la-garganta ч.1: 4 кліпів" in r.output and "⛔ p1-1.02-video" in r.output and "queue.json" in r.output


# ---------------------------------------------------------------- заглушки провайдерів: запит без мережі


def test_refs_in_and_resolve() -> None:
    p = {"image": "ref:a", "reference_images": ["ref:b", "https://x/y.png", "ref:a"], "prompt": "ref: is text"}
    assert video_mod.refs_in(p) == ["a", "b"]
    out = video_mod.resolve_refs(p, {"a": Path("/m/a.png"), "b": Path("/m/b.png")})
    assert out == {"image": "/m/a.png", "reference_images": ["/m/b.png", "https://x/y.png", "/m/a.png"],
                   "prompt": "ref: is text"} and p["image"] == "ref:a"            # оригінал не змінено
    with pytest.raises(video_mod.VideoError, match="ref:b"):
        video_mod.resolve_refs(p, {"a": Path("/m/a.png")})


def test_replicate_build_request(tmp_path: Path) -> None:
    f = tmp_path / "start.png"
    f.write_bytes(PNG)
    payload = _clip("Beto turns.", "ref:p1.1.02.frame")
    req = video_mod.ReplicateProvider().build_request(SD_R, payload, {"p1.1.02.frame": f})
    assert req["method"] == "POST"
    assert req["url"] == "https://api.replicate.com/v1/models/bytedance/seedance-2.5/predictions"
    assert req["json"] == {"input": {**payload, "image": f.as_posix()}} and req["auth_env"] == "REPLICATE_API_TOKEN"
    assert payload["image"] == "ref:p1.1.02.frame"
    with pytest.raises(video_mod.VideoError, match="не пройде API"):
        video_mod.ReplicateProvider().build_request(SD_R, {**payload, "fps": 24}, {"p1.1.02.frame": f})
    with pytest.raises(video_mod.VideoError, match="не відео Replicate"):
        video_mod.ReplicateProvider().build_request(SD_CF, payload, {"p1.1.02.frame": f})
    with pytest.raises(video_mod.VideoError, match="Replicate ще не підключено"):
        video_mod.ReplicateProvider().submit(SD_R, payload, {"p1.1.02.frame": f})


def test_cloudflare_build_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    f = tmp_path / "start.png"
    f.write_bytes(PNG)
    payload = _clip("Beto turns.", "ref:p1.1.02.frame", use_virtual_avatar=True)
    req = video_mod.CloudflareProvider("acc123").build_request(SD_CF, payload, {"p1.1.02.frame": f})
    assert req["url"] == "https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/bytedance/seedance-2.5"
    body = req["json"]
    assert body["image"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
    assert {k: v for k, v in body.items() if k != "image"} == {k: v for k, v in payload.items() if k != "image"}
    assert "$CLOUDFLARE_ACCOUNT_ID" in video_mod.CloudflareProvider().build_request(SD_CF, payload,
                                                                                   {"p1.1.02.frame": f})["url"]
    with pytest.raises(video_mod.VideoError, match="не підключено"):
        video_mod.CloudflareProvider().poll("job")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc-env")                     # id акаунта — з оточення / .env
    assert "/accounts/acc-env/ai/run/" in video_mod.CloudflareProvider().build_request(SD_CF, payload,
                                                                                       {"p1.1.02.frame": f})["url"]


# ---------------------------------------------------------------- кошторис: COSTS.md + запас із каталогу


def test_load_rates_falls_back_to_catalog(tmp_path: Path) -> None:
    catalog = providers_mod.video_rates(costs_mod.VIDEO_ROUTE)
    md = tmp_path / "COSTS.md"
    md.write_text("| Провайдер | Етап | Одиниця | Ціна |\n|---|---|---|---|\n"
                  "| Seedance 2.5 | video | секунда 720p | ≈ 0,25 |\n", encoding="utf-8")
    assert costs_mod.load_rates(md) == {**catalog, "720p": 0.25}                 # COSTS.md важить більше
    md.write_text("| ElevenLabs | voice | 1K символів | ≈ 0,18 |\n", encoding="utf-8")
    assert costs_mod.load_rates(md) == catalog == {"480p": 0.1028, "720p": 0.2312}
    assert costs_mod.load_rates(tmp_path / "nope.md") == catalog
    with pytest.raises(ValueError, match="немає ставок Seedance"):
        costs_mod.load_rates(md, route=None)
    with pytest.raises(ValueError, match="каталог маршрутів"):
        costs_mod.load_rates(md, route="replicate:google/nano-banana-pro")      # не посекундний маршрут
    assert set(costs_mod.load_rates()) >= {"480p", "720p"}                       # справжній COSTS.md


def test_call_usd_catalog_then_costs_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = _clip("x", "ref:s")
    assert costs_mod.call_usd(SD_R, p) == pytest.approx(0.2312 * 5)            # каталог важить більше
    assert costs_mod.call_usd(SD_R, {**p, "duration": -1}) == pytest.approx(0.2312 * 30)
    md = tmp_path / "COSTS.md"
    md.write_text("| Seedance 2.5 | video | секунда 720p | ≈ 0,25 |\n", encoding="utf-8")
    monkeypatch.setattr(providers_mod, "price", lambda *_a, **_k: None)         # ціна маршруту null / UNVERIFIED
    monkeypatch.setattr(providers_mod, "video_rates",
                        lambda *_a, **_k: (_ for _ in ()).throw(providers_mod.ProviderError("без ставок")))
    assert costs_mod.call_usd(SD_R, p, md) == pytest.approx(1.25)
    assert costs_mod.call_usd(SD_R, {**p, "resolution": "480p"}, md) is None   # ставку не вигадуємо
    assert costs_mod.call_usd(SD_R, p, tmp_path / "nope.md") is None


def test_estimate_items_follows_clip_profile(items: list[P.Item], monkeypatch: pytest.MonkeyPatch) -> None:
    """Кошторис за скомпільованими кліпами (5 с кожен) = те, що порахує черга × спроби; без ціни — unpriced."""
    for it, tier in zip(items[3:7], ("hero", "hero", "secondary", "hero"), strict=True):
        it.extra["tier"] = tier
    items[3].extra["clip"] = {"index": 1, "of": 2, "window": [0, 5]}
    items[4].extra["clip"] = {"index": 2, "of": 2, "window": [0, 2.5]}
    est = costs_mod.estimate_items(items, attempts=2)
    hero = est.tiers["hero"]
    assert (hero.shots, hero.billed_s, hero.screen_s) == (2, 15.0, 12.5)       # 1.02 (2 кліпи) + 1.04
    assert hero.usd == pytest.approx(3 * 0.2312 * 5 * 2, abs=0.01) and est.unpriced == []
    assert est.usd == pytest.approx(4 * 0.2312 * 5 * 2, abs=0.01)
    monkeypatch.setattr(costs_mod, "call_usd", lambda route, payload, path=None: None if route == SD_CF else 1.0)
    est = costs_mod.estimate_items(items, attempts=1)
    assert est.unpriced == ["p1-1.03-video"] and est.usd == 3.0
