"""Етап voice (fabrica/voice.py): без мережі — ElevenLabs підмінено, облік витрат на тимчасовій SQLite."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import shotlist as shotlist_mod
from fabrica import voice as voice_mod
from fabrica.cli import app
from fabrica.ledger import BudgetNotConfigured, Ledger, Limits
from fabrica.models import Script, Shots

pytestmark = pytest.mark.usefixtures("automation_on")   # платний шлях — явно

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "la-garganta" / "part1.script.json"
SHOTLIST = ROOT / "series" / "la-garganta" / "part1_shotlist.md"
RATE = 0.30


class FakeElevenLabs:
    def __init__(self, fail: voice_mod.ElevenLabsError | None = None) -> None:
        self.calls: list[tuple[str, str, str, dict]] = []
        self.fail = fail

    def tts(self, voice_id: str, text: str, model: str, settings: dict) -> tuple[bytes, str]:
        self.calls.append((voice_id, text, model, settings))
        if self.fail:
            raise self.fail
        return b"ID3fake-mp3", f"req-{len(self.calls)}"


@pytest.fixture
def out(tmp_path: Path) -> Path:
    folder = tmp_path / "la-garganta" / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(SHOTLIST, bible_mod.load("la-garganta"), 1, script)
    (folder / "shots.json").write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8")
    return tmp_path


@pytest.fixture
def voices(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Усі, хто говорить, мають голос (у справжній біблії voice_id поки null)."""
    data = bible_mod.load("la-garganta").data
    ids = {k: f"v_{k}" for k in voice_mod.voice_ids(data)}
    monkeypatch.setattr(voice_mod, "voice_ids", lambda _data: ids)
    return ids


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    lg = Ledger(tmp_path / "fabrica.sqlite", Limits.of(per_episode=50, daily=50, monthly=500))
    yield lg
    lg.close()


def run(out: Path, **kw) -> voice_mod.Plan:
    kw.setdefault("rate_per_1k", RATE)
    kw.setdefault("duration", lambda _p: 1.5)
    kw.setdefault("log", lambda *_: None)
    return voice_mod.run("la-garganta", 1, out, **kw)


def test_collect_takes_every_spoken_line_with_delivery(out: Path) -> None:
    folder = out / "la-garganta" / "part1"
    shots = Shots.model_validate_json((folder / "shots.json").read_text(encoding="utf-8"))
    script = Script.model_validate_json((folder / "script.json").read_text(encoding="utf-8"))
    lines = voice_mod.collect(shots, script)
    assert len(lines) == sum(len(sh.dialogue) for sh in shots.shots)
    by_line = {ln.line_id: ln for ln in lines if ln.line_id}
    assert by_line["l01"].delivery == "shout" and by_line["l02"].delivery == "whisper"
    assert all(ln.text for ln in lines)


def test_dry_run_needs_no_network_rate_or_voices(out: Path) -> None:
    p = voice_mod.run("la-garganta", 1, out, dry_run=True, log=lambda *_: None)   # ставка в COSTS.md — TODO
    assert p.items and p.missing                       # у біблії voice_id ще не затверджено
    assert not (out / "la-garganta" / "part1" / "voice").exists()


def test_run_generates_files_manifest_and_ledger(out: Path, voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs()
    p = run(out, client=fake, ledger=ledger)
    folder = out / "la-garganta" / "part1" / "voice"
    assert len(fake.calls) == len(p.items) == len({i.key for i in p.items})
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert [m["file"] for m in manifest["items"]] == [i.file for i in p.items]
    assert all((folder / m["file"]).read_bytes() == b"ID3fake-mp3" and m["duration_s"] == 1.5
               for m in manifest["items"])
    assert ledger.spent("la-garganta", 1) == pytest.approx(p.chars / 1000 * RATE, abs=1e-6)
    assert ledger.unsettled() == []
    shout = next(c for c in fake.calls if c[1].startswith("¡Chuy"))
    assert shout[0] == "v_lupita" and shout[3] == voice_mod.SETTINGS["shout"]


def test_second_run_is_cached_and_free(out: Path, voices: dict, ledger: Ledger) -> None:
    run(out, client=FakeElevenLabs(), ledger=ledger)
    spent = ledger.spent()
    again = FakeElevenLabs()
    p = run(out, client=again, ledger=ledger)
    assert again.calls == [] and all(i.cached for i in p.items) and ledger.spent() == spent


def test_http_4xx_is_not_charged(out: Path, voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs(voice_mod.ElevenLabsError("HTTP 401: invalid api key", charged=False))
    with pytest.raises(voice_mod.ElevenLabsError):
        run(out, client=fake, ledger=ledger)
    assert ledger.spent() == 0 and ledger.unsettled() == []


def test_http_5xx_keeps_reservation(out: Path, voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs(voice_mod.ElevenLabsError("HTTP 503", charged=True))
    with pytest.raises(voice_mod.ElevenLabsError):
        run(out, client=fake, ledger=ledger)
    assert len(ledger.unsettled()) == 1 and ledger.spent() > 0
    assert not list((out / "la-garganta" / "part1" / "voice").glob("*.mp3"))


def test_missing_voices_stop_before_any_call(out: Path, ledger: Ledger) -> None:
    fake = FakeElevenLabs()
    with pytest.raises(voice_mod.VoiceError, match="голоси"):
        run(out, client=fake, ledger=ledger)
    assert fake.calls == []


def test_missing_rate_stops_real_run(out: Path, voices: dict, ledger: Ledger, monkeypatch) -> None:
    monkeypatch.setattr(voice_mod.costs_mod, "rate", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("TODO")))
    with pytest.raises(voice_mod.VoiceError):
        run(out, client=FakeElevenLabs(), ledger=ledger, rate_per_1k=None)


def test_no_budget_limits_no_calls(out: Path, voices: dict, tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(env))
    for key in ("BUDGET_PER_EPISODE_USD", "BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD"):
        monkeypatch.delenv(key, raising=False)
    fake = FakeElevenLabs()
    with pytest.raises(BudgetNotConfigured):
        run(out, client=fake)
    assert fake.calls == []


def test_cache_key_depends_on_everything() -> None:
    base = voice_mod.cache_key("Hola", "v1", "m1", voice_mod.SETTINGS["normal"])
    assert base != voice_mod.cache_key("Hola", "v2", "m1", voice_mod.SETTINGS["normal"])
    assert base != voice_mod.cache_key("Hola", "v1", "m2", voice_mod.SETTINGS["normal"])
    assert base != voice_mod.cache_key("Hola", "v1", "m1", voice_mod.SETTINGS["whisper"])
    assert base == voice_mod.cache_key("Hola", "v1", "m1", dict(voice_mod.SETTINGS["normal"]))


def _runs(exe: str) -> bool:
    """FFmpeg є і справді запускається (на Mac після оновлення Homebrew він буває зламаний)."""
    if not shutil.which(exe):
        return False
    return subprocess.run([exe, "-version"], capture_output=True, timeout=30).returncode == 0


@pytest.mark.skipif(not (_runs("ffmpeg") and _runs("ffprobe")), reason="FFmpeg немає або він не запускається")
def test_probe_duration_real_mp3(tmp_path: Path) -> None:
    mp3 = tmp_path / "tone.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.2",
                    "-ac", "1", str(mp3)], check=True, timeout=60)
    assert voice_mod.probe_duration(mp3) == pytest.approx(1.2, abs=0.08)


def test_cli_dry_run(out: Path) -> None:
    r = CliRunner().invoke(app, ["voice", "la-garganta", "1", "--out", str(out), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Озвучка la-garganta ч.1" in r.output and "voice_id" in r.output
