"""Етап voice (fabrica/voice.py): тіло запиту — payload скомпільованих реплік (voice.line) без змін, розкладений
providers.split; без мережі — ElevenLabs підмінено, prompts.build підмінено, облік витрат на тимчасовій SQLite."""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import prompts as P
from fabrica import providers as providers_mod
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
EL = "elevenlabs:eleven_v4"
TPL = P.Template("voice.line", "voice", 2, "", {}, "", "", {}, Path("line.yaml"), "voiceline0001")


class FakeElevenLabs:
    ids = itertools.count(1)                 # request-id унікальний на весь тест (журнал витрат його перевіряє)

    def __init__(self, fail: voice_mod.ElevenLabsError | None = None, billed=None) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self.fail, self.billed = fail, billed        # billed(body) → заголовок character-cost; None — його немає

    def tts(self, voice_id: str, body: dict, query: dict | None = None) -> tuple[bytes, str, int | None]:
        self.calls.append((voice_id, body, query))
        if self.fail:
            raise self.fail
        return b"ID3fake-mp3", f"req-{next(self.ids)}", self.billed(body) if self.billed else None


@pytest.fixture
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "la-garganta" / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(SHOTLIST, bible_mod.load("la-garganta"), 1, script)
    (folder / "shots.json").write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8")
    monkeypatch.delenv("ELEVENLABS_MODEL", raising=False)
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    return tmp_path


def compile_lines(out: Path) -> list[P.Item]:
    """Як компілятор voice.line: payload з тегом манери, сідом, мовою — і полем, якого запасний шлях не додає."""
    folder = out / "la-garganta" / "part1"
    shots = Shots.model_validate_json((folder / "shots.json").read_text(encoding="utf-8"))
    script = Script.model_validate_json((folder / "script.json").read_text(encoding="utf-8"))
    lines, items = voice_mod.collect(shots, script), []
    for sh in shots.shots:
        for n, ln in enumerate((x for x in lines if x.shot_id == sh.id), 1):
            iid = f"p1-{sh.id}-voice{n}"
            payload = {**voice_mod.line_payload(ln, None, "eleven_v4", iid), "seed": 1000 + len(items),
                       "apply_text_normalization": "auto"}
            del payload["voice_id"]                                     # у біблії voice_id ще немає
            items.append(P.Item(iid, "1", "voice", f"репліка {iid}", TPL, payload["text"], "", {}, [], None,
                                {"shot": sh.id, "character": ln.character_id, "line_id": ln.line_id,
                                 "delivery": ln.delivery}, [], 7, EL, payload, []))
    return items


@pytest.fixture
def compiled(out: Path, monkeypatch: pytest.MonkeyPatch) -> list[P.Item]:
    items = compile_lines(out)
    monkeypatch.setattr(P, "build", lambda slug, set_name, kinds=None, only=None, out_root=None, templates=None:
                        [i for i in items if not kinds or i.kind in kinds])
    return items


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


def test_dry_run_needs_no_network_rate_or_voices(out: Path, compiled: list[P.Item]) -> None:
    p = voice_mod.run("la-garganta", 1, out, dry_run=True, log=lambda *_: None)
    assert p.compiled and len(p.items) == len(compiled) and p.missing      # у біблії voice_id ще не затверджено
    assert not (out / "la-garganta" / "part1" / "voice").exists()


def test_body_is_compiled_payload(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs()
    p = run(out, client=fake, ledger=ledger)
    assert len(fake.calls) == len(p.items) == len(compiled) == len({i.key for i in p.items})
    for (vid, body, query), it, c in zip(fake.calls, p.items, compiled, strict=True):
        assert vid == voices[it.line.character_id] and query == {"output_format": "mp3_44100_192"}
        assert body == {k: v for k, v in c.payload.items() if k not in ("voice_id", "output_format")}   # без змін
        assert set(body["voice_settings"]) == {"stability", "similarity_boost"} and body["language_code"] == "es"
        assert body["model_id"] == "eleven_v4" and body["seed"] == c.payload["seed"]
        assert it.item_id == c.id and it.chars == len(body["text"]) and it.file.endswith(".mp3")
    shout = next(b for _v, b, _q in fake.calls if "¡Chuy" in b["text"])
    assert shout["text"].startswith("[shouting] ¡Chuy") and shout["voice_settings"] == {"stability": 0.3,
                                                                                        "similarity_boost": 0.8}
    folder = out / "la-garganta" / "part1" / "voice"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["compiled"] and [m["file"] for m in manifest["items"]] == [i.file for i in p.items]
    assert all((folder / m["file"]).read_bytes() == b"ID3fake-mp3" and m["duration_s"] == 1.5 and m["seed"]
               for m in manifest["items"])
    assert ledger.spent("la-garganta", 1) == pytest.approx(p.chars / 1000 * RATE, abs=1e-6)
    assert ledger.unsettled() == []


def test_character_cost_header_settles_actual(out: Path, compiled: list[P.Item], voices: dict,
                                             ledger: Ledger) -> None:
    """Факт списання — заголовок character-cost (ціна v4 не підтверджена), а не оцінка за довжиною тексту."""
    fake = FakeElevenLabs(billed=lambda body: 2 * len(body["text"]))
    p = run(out, client=fake, ledger=ledger)
    assert all(i.billed_chars == 2 * i.chars for i in p.items)
    assert ledger.spent("la-garganta", 1) == pytest.approx(2 * p.chars / 1000 * RATE, abs=1e-5)
    manifest = json.loads((out / "la-garganta" / "part1" / "voice" / "manifest.json").read_text(encoding="utf-8"))
    assert [m["billed_chars"] for m in manifest["items"]] == [2 * i.chars for i in p.items]


def test_manifest_delivery_is_compiled_one(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    """Без script.json collect() дає «normal», а звук скомпільовано з тегом манери — маніфест каже як у звуку;
    скомпільованих реплік більше, ніж у shots.json, — рядок маніфесту з елемента (текст без тегу)."""
    (out / "la-garganta" / "part1" / "script.json").unlink()
    first = compiled[0]
    extra = P.Item(f"p1-{first.extra['shot']}-voice9", "1", "voice", "зайва", TPL, "", "", {}, [], None,
                   {"shot": first.extra["shot"], "character": first.extra["character"], "delivery": "whisper",
                    "line_id": "lx", "offscreen": True}, [], 7, EL,
                   {**first.payload, "text": "[whispering] Otra línea.", "seed": 4242})
    compiled.append(extra)
    p = run(out, client=FakeElevenLabs(), ledger=ledger)
    manifest = json.loads((out / "la-garganta" / "part1" / "voice" / "manifest.json").read_text(encoding="utf-8"))
    rows = {m["item"]: m for m in manifest["items"]}
    shout = next(c for c in compiled if c.payload["text"].startswith("[shouting]"))
    assert rows[shout.id]["delivery"] == "shout" == shout.extra["delivery"]
    assert all(rows[c.id]["delivery"] == c.extra["delivery"] for c in compiled)
    x = rows[extra.id]
    assert (x["text"], x["character_id"], x["line_id"], x["offscreen"], x["shot_id"]) == (
        "Otra línea.", first.extra["character"], "lx", True, first.extra["shot"])
    assert len(p.items) == len(compiled)


def test_second_run_is_cached_and_free(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    run(out, client=FakeElevenLabs(), ledger=ledger)
    spent = ledger.spent()
    again = FakeElevenLabs()
    p = run(out, client=again, ledger=ledger)
    assert again.calls == [] and all(i.cached for i in p.items) and ledger.spent() == spent


def test_new_seed_is_a_new_take(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    run(out, client=FakeElevenLabs(), ledger=ledger)
    compiled[0].payload["seed"] += 1
    again = FakeElevenLabs()
    run(out, client=again, ledger=ledger)
    assert len(again.calls) == 1 and again.calls[0][1]["seed"] == compiled[0].payload["seed"]


def test_fallback_without_compiled_lines(out: Path, voices: dict, ledger: Ledger,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "build", lambda *a, **k: [])                     # старий формат пакета
    logs: list[str] = []
    fake = FakeElevenLabs()
    p = run(out, client=fake, ledger=ledger, log=logs.append)
    assert not p.compiled and any("запасний шлях" in m for m in logs) and len(fake.calls) == len(p.items)
    for (_vid, body, query), it in zip(fake.calls, p.items, strict=True):
        assert body["model_id"] == "eleven_v4" and body["language_code"] == "es" and query["output_format"]
        assert body["seed"] == P.seed_for(it.item_id) and it.item_id.startswith("p1-")
        assert providers_mod.validate(EL, {**body, **query, "voice_id": "v"}) == []
    whisper = next(b for _v, b, _q in fake.calls if b["text"].startswith("[whispering]"))
    assert set(whisper["voice_settings"]) == {"stability", "similarity_boost"}


def test_fallback_legacy_model_has_no_tags(out: Path, voices: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "build", lambda *a, **k: [])
    p = voice_mod.run("la-garganta", 1, out, dry_run=True, model="eleven_multilingual_v2", log=lambda *_: None)
    body = p.items[0].request()["body"]
    assert body["model_id"] == "eleven_multilingual_v2" and "language_code" not in body
    assert not any(i.request()["body"]["text"].startswith("[") for i in p.items)


def test_broken_compile_stops_real_run_only(out: Path, voices: dict, ledger: Ledger,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_a, **_k):
        raise P.PromptError("part1_prompts_en.yaml: зламано")

    monkeypatch.setattr(P, "build", broken)
    logs: list[str] = []
    assert not voice_mod.run("la-garganta", 1, out, dry_run=True, log=logs.append).compiled
    assert any("не скомпілювались" in m for m in logs)
    with pytest.raises(voice_mod.VoiceError, match="не скомпілювались"):
        run(out, client=FakeElevenLabs(), ledger=ledger)


def test_invalid_payload_stops_before_any_call(out: Path, compiled: list[P.Item], voices: dict,
                                               ledger: Ledger) -> None:
    compiled[1].payload["voice_settings"]["style"] = 0.5                     # v4 не приймає style
    logs: list[str] = []
    p = voice_mod.run("la-garganta", 1, out, dry_run=True, rate_per_1k=RATE, log=logs.append)
    assert any("⛔" in m and "voice_settings.style" in m for m in logs) and p.items[1].warnings
    fake = FakeElevenLabs()
    with pytest.raises(voice_mod.VoiceError, match="не пройдуть API"):
        run(out, client=fake, ledger=ledger)
    assert fake.calls == [] and ledger.spent() == 0


def test_explicit_model_does_not_override_compiled(out: Path, compiled: list[P.Item], voices: dict,
                                                   ledger: Ledger, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
    logs: list[str] = []
    fake = FakeElevenLabs()
    run(out, client=fake, ledger=ledger, log=logs.append)
    assert any("eleven_multilingual_v2 ігнорую" in m for m in logs)
    assert {b["model_id"] for _v, b, _q in fake.calls} == {"eleven_v4"}


def test_http_4xx_is_not_charged(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs(voice_mod.ElevenLabsError("HTTP 401: invalid api key", charged=False))
    with pytest.raises(voice_mod.ElevenLabsError):
        run(out, client=fake, ledger=ledger)
    assert ledger.spent() == 0 and ledger.unsettled() == []


def test_http_5xx_keeps_reservation(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger) -> None:
    fake = FakeElevenLabs(voice_mod.ElevenLabsError("HTTP 503", charged=True))
    with pytest.raises(voice_mod.ElevenLabsError):
        run(out, client=fake, ledger=ledger)
    assert len(ledger.unsettled()) == 1 and ledger.spent() > 0
    assert not list((out / "la-garganta" / "part1" / "voice").glob("*.mp3"))


def test_missing_voices_stop_before_any_call(out: Path, compiled: list[P.Item], ledger: Ledger) -> None:
    fake = FakeElevenLabs()
    with pytest.raises(voice_mod.VoiceError, match="голоси"):
        run(out, client=fake, ledger=ledger)
    assert fake.calls == []


def test_missing_rate_stops_real_run(out: Path, compiled: list[P.Item], voices: dict, ledger: Ledger,
                                     monkeypatch) -> None:
    monkeypatch.setattr(voice_mod.costs_mod, "rate", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("TODO")))
    with pytest.raises(voice_mod.VoiceError):
        run(out, client=FakeElevenLabs(), ledger=ledger, rate_per_1k=None)


def test_no_budget_limits_no_calls(out: Path, compiled: list[P.Item], voices: dict, tmp_path: Path,
                                   monkeypatch) -> None:
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
    body = {"text": "Hola", "model_id": "eleven_v4", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            "seed": 1}
    q = {"output_format": "mp3_44100_192"}
    base = voice_mod.cache_key("v1", body, q)
    assert base == voice_mod.cache_key("v1", json.loads(json.dumps(body)), dict(q))
    assert base != voice_mod.cache_key("v2", body, q)
    assert base != voice_mod.cache_key("v1", {**body, "seed": 2}, q)
    assert base != voice_mod.cache_key("v1", {**body, "model_id": "eleven_v3"}, q)
    assert base != voice_mod.cache_key("v1", {**body, "voice_settings": {"stability": 0.3, "similarity_boost": 0.8}}, q)
    assert base != voice_mod.cache_key("v1", body, {"output_format": "mp3_44100_128"})


def test_client_sends_body_and_query(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}
    headers = [{"request-id": "r1", "character-cost": "27"}, {"request-id": "r2", "character-cost": "n/a"}]

    class Resp:
        def __init__(self) -> None:
            self.headers = headers.pop(0)

        def read(self):
            return b"mp3"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        seen.update(url=req.full_url, body=json.loads(req.data.decode("utf-8")), key=req.get_header("Xi-api-key"))
        return Resp()

    monkeypatch.setattr(voice_mod.urllib.request, "urlopen", urlopen)
    body = {"text": "[whispering] ¿Hay alguien?", "model_id": "eleven_v4", "seed": 3}
    audio, rid, billed = voice_mod.ElevenLabs("k").tts("abc", body, {"output_format": "mp3_44100_192"})
    assert (audio, rid, billed) == (b"mp3", "r1", 27) and seen["body"] == body and seen["key"] == "k"
    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/abc?output_format=mp3_44100_192"
    assert voice_mod.ElevenLabs("k").tts("abc", body)[2] is None                # не число — оцінка лишається


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


def test_cli_dry_run(out: Path, compiled: list[P.Item]) -> None:
    r = CliRunner().invoke(app, ["voice", "la-garganta", "1", "--out", str(out), "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Озвучка la-garganta ч.1" in r.output and "voice_id" in r.output and "eleven_v4" in r.output
