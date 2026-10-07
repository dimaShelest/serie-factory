"""Етап video (fabrica/video.py): черга, кеш, golden-ворота, облік витрат — без мережі (фейковий провайдер)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import lab as lab_mod
from fabrica import prompts as prompts_mod
from fabrica import shotlist as shotlist_mod
from fabrica import video as video_mod
from fabrica.cli import app
from fabrica.ledger import AutomationDisabled, Ledger, Limits
from fabrica.models import Script, Shots

ROOT = Path(__file__).resolve().parents[1]
SLUG = "la-garganta"
FIXTURE = ROOT / "tests" / "fixtures" / SLUG / "part1.script.json"
SHOT = "4.03"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class FakeProvider:
    name = "fake"

    def __init__(self, fail_submit: video_mod.ProviderError | None = None, states=("running", "succeeded")) -> None:
        self.submitted: list[tuple[str, dict, Path]] = []
        self.fail_submit, self.states = fail_submit, list(states)

    def submit(self, prompt, negative, params, first_frame, refs):
        if self.fail_submit:
            raise self.fail_submit
        self.submitted.append((prompt, params, first_frame))
        return f"job-{len(self.submitted)}"

    def poll(self, job_id):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return state, ("https://example/out.mp4" if state == "succeeded" else "boom")

    def download(self, url, dest):
        dest.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Частина 1 у тимчасовому output/, журнал лабораторії й golden — теж тимчасові, англійський опис шоту 4.03."""
    out = tmp_path / "out"
    folder = out / SLUG / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(ROOT / "series" / SLUG / "part1_shotlist.md", bible_mod.load(SLUG), 1, script)
    (folder / "shots.json").write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    overlay = tmp_path / "part1_prompts_en.yaml"
    overlay.write_text(yaml.safe_dump({SHOT: {
        "composition": "Four young adults on the ground, hundreds of pebbles hanging in the air.",
        "action": "The pebbles slowly drift and rotate in place.", "camera": "slow push-in",
        "light": "dawn, pale golden light", "variant": "dawn"}}), encoding="utf-8")
    monkeypatch.setattr(prompts_mod, "overlay_file", lambda slug, part: overlay)
    monkeypatch.setattr(prompts_mod, "OUTPUT", out)          # журнал лабораторії шукає частину тут
    return out


def approve_frame(tmp_path: Path) -> None:
    png = tmp_path / "frame.png"
    png.write_bytes(PNG)
    lab_mod.log(SLUG, f"p1-{SHOT}-frame", "gemini", 5, png, "кадр ок")
    lab_mod.approve(SLUG, f"p1-{SHOT}-frame")


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    lg = Ledger(tmp_path / "fabrica.sqlite", Limits.of(per_episode=160, daily=60, monthly=900))
    yield lg
    lg.close()


def run(out: Path, **kw):
    kw.setdefault("log", lambda *_: None)
    kw.setdefault("sleep", lambda _s: None)
    return video_mod.run(SLUG, 1, out, **kw)


def test_dry_run_explains_every_block(world: Path) -> None:
    jobs = run(world, dry_run=True)
    assert jobs and all(j.state == "blocked" for j in jobs)
    j = next(j for j in jobs if j.shot_id == SHOT)
    assert any("не golden" in r for r in j.reasons) and any("стартового кадру" in r for r in j.reasons)
    other = next(j for j in jobs if j.shot_id == "4.01")
    assert any("англійського опису" in r for r in other.reasons)      # UA-текст в автомат не йде
    queue = json.loads((world / SLUG / "part1" / "video" / "queue.json").read_text(encoding="utf-8"))
    assert len(queue["jobs"]) == len(jobs) and queue["part"] == 1


def test_generates_with_golden_frame_then_caches(world: Path, tmp_path: Path, ledger: Ledger,
                                                 automation_on: None) -> None:
    lab_mod.approve(SLUG, "video.shot", force=True)
    approve_frame(tmp_path)
    fake = FakeProvider()
    jobs = run(world, provider=fake, ledger=ledger, only=SHOT)
    job = jobs[0]
    assert job.state == "done" and (world / SLUG / "part1" / "video" / job.file).exists()
    prompt, params, frame = fake.submitted[0]
    lab_item = next(i for i in prompts_mod.build(SLUG, "1", ["video"], only=SHOT, out_root=world) if i.kind == "video")
    assert prompt == lab_item.prompt and params == lab_item.params          # рівно те, що бачила лабораторія
    assert frame.name.endswith("frame.png")
    assert ledger.spent("la-garganta", 1) == pytest.approx(job.estimate_usd) and ledger.unsettled() == []
    again = FakeProvider()
    assert run(world, provider=again, ledger=ledger, only=SHOT)[0].state == "done" and again.submitted == []


def test_provider_rejects_before_charge(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    lab_mod.approve(SLUG, "video.shot", force=True)
    approve_frame(tmp_path)
    fake = FakeProvider(fail_submit=video_mod.ProviderError("HTTP 422: bad input", charged=False))
    with pytest.raises(video_mod.ProviderError):
        run(world, provider=fake, ledger=ledger, only=SHOT)
    assert ledger.spent() == 0 and ledger.unsettled() == []
    queue = json.loads((world / SLUG / "part1" / "video" / "queue.json").read_text(encoding="utf-8"))
    assert queue["jobs"][0]["state"] == "failed"


def test_failed_generation_keeps_reservation(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    lab_mod.approve(SLUG, "video.shot", force=True)
    approve_frame(tmp_path)
    with pytest.raises(video_mod.ProviderError):
        run(world, provider=FakeProvider(states=("running", "failed")), ledger=ledger, only=SHOT)
    assert len(ledger.unsettled()) == 1                    # провайдер міг списати гроші — звірити з рахунком


def test_timeout(world: Path, tmp_path: Path, ledger: Ledger, automation_on: None) -> None:
    lab_mod.approve(SLUG, "video.shot", force=True)
    approve_frame(tmp_path)
    with pytest.raises(video_mod.ProviderError, match="немає результату"):
        run(world, provider=FakeProvider(states=("running",)), ledger=ledger, only=SHOT, timeout_s=0)


def test_lab_mode_blocks_before_submit(world: Path, tmp_path: Path, ledger: Ledger,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_ENABLED", "false")
    lab_mod.approve(SLUG, "video.shot", force=True)
    approve_frame(tmp_path)
    fake = FakeProvider()
    with pytest.raises(AutomationDisabled):
        run(world, provider=fake, ledger=ledger, only=SHOT)
    assert fake.submitted == []


def test_replicate_client_not_connected_yet() -> None:
    with pytest.raises(video_mod.VideoError, match="Replicate"):
        video_mod.ReplicateProvider()


def test_cli_dry_run(world: Path) -> None:
    r = CliRunner().invoke(app, ["video", SLUG, "1", "--out", str(world), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Відео la-garganta ч.1" in r.output and "⛔" in r.output and "queue.json" in r.output
