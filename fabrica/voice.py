"""Етап voice: озвучка реплік частини через ElevenLabs (Issue #6).

Вхід:  output/<slug>/part<N>/shots.json — `dialogue[]` кожного шота (усе, що звучить у монтажі);
       output/<slug>/part<N>/script.json — подача реплік (whisper / shout …), якщо є;
       series/<slug>/bible.yaml — `voice.voice_id` кожного, хто говорить.
Вихід: output/<slug>/part<N>/voice/<key>.mp3 + voice/manifest.json (репліка → файл, тривалість, символи).

- Кеш за вмістом: key = sha256(текст, voice_id, модель, налаштування, формат). Той самий вхід — без нового виклику.
- Гроші: кожен виклик — Ledger.charge(); ставка — docs/COSTS.md («| ElevenLabs | voice | 1K символів | … |»).
  HTTP 4xx — ElevenLabs не списує → резерв знімаємо; 5xx / обрив — могли списати → резерв лишається.
- Маніфест пишемо після кожної репліки: перерваний запуск продовжиться з місця зупинки.
- Сухий режим (dry_run): без мережі й витрат — план, символи, кошторис, яких голосів бракує.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fabrica import bible as bible_mod
from fabrica import config
from fabrica import costs as costs_mod
from fabrica.ledger import Ledger
from fabrica.models import Script, Shots

API = "https://api.elevenlabs.io"
DEFAULT_MODEL = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
TIMEOUT_S = 120

# Подача → налаштування голосу ElevenLabs. Емоцію робить текст і голос, налаштування лише підсилюють.
SETTINGS: dict[str, dict[str, float | bool]] = {
    "normal": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.25, "use_speaker_boost": True},
    "whisper": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": False},
    "shout": {"stability": 0.3, "similarity_boost": 0.8, "style": 0.7, "use_speaker_boost": True},
    "scream": {"stability": 0.2, "similarity_boost": 0.8, "style": 0.9, "use_speaker_boost": True},
}


class VoiceError(RuntimeError):
    """Етап не може працювати: бракує голосів, ключа, ставки або ffprobe."""


class ElevenLabsError(RuntimeError):
    def __init__(self, message: str, charged: bool) -> None:
        super().__init__(message)
        self.charged = charged       # False — гроші точно не списано (4xx або запит не пішов)


@dataclass
class VoiceLine:
    shot_id: str
    character_id: str | None
    text: str
    line_id: str | None = None
    delivery: str = "normal"
    offscreen: bool = False


@dataclass
class Item:
    line: VoiceLine
    voice_id: str | None
    key: str
    chars: int
    file: str = ""
    duration_s: float | None = None
    cached: bool = False


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    missing: dict[str, list[str]] = field(default_factory=dict)   # хто без voice_id → шоти

    @property
    def chars(self) -> int:
        return sum(i.chars for i in self.items)

    @property
    def new_chars(self) -> int:
        return sum(i.chars for i in self.items if not i.cached)


# ---------------------------------------------------------------- план


def collect(shots: Shots, script: Script | None = None) -> list[VoiceLine]:
    """Репліки в порядку монтажу. Подача — зі script.json за line_id."""
    delivery = {ln.id: ln.delivery for sc in (script.scenes if script else []) for ln in sc.lines}
    return [VoiceLine(sh.id, d.character_id, d.text_es.strip(), d.line_id,
                      delivery.get(d.line_id or "", "normal"), d.offscreen)
            for sh in shots.shots for d in sh.dialogue]


def voice_ids(data: dict) -> dict[str, str | None]:
    """id → voice_id для героїв, другорядних і учасників сімки (поле `voice.voice_id` у bible.yaml)."""
    people = [*data.get("characters", []), *data.get("supporting", [])]
    people += [m for s in data.get("supporting", []) for m in s.get("members", [])]
    return {p["id"]: (p.get("voice") or {}).get("voice_id") for p in people}


def cache_key(text: str, voice_id: str, model: str, settings: dict, fmt: str = OUTPUT_FORMAT) -> str:
    payload = json.dumps({"text": text, "voice_id": voice_id, "model": model, "settings": settings, "format": fmt},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def plan(lines: list[VoiceLine], voices: dict[str, str | None], model: str, folder: Path) -> Plan:
    p = Plan()
    for ln in lines:
        vid = voices.get(ln.character_id or "")
        if not vid:
            p.missing.setdefault(ln.character_id or "?", []).append(ln.shot_id)
        key = cache_key(ln.text, vid or "?", model, SETTINGS.get(ln.delivery, SETTINGS["normal"]))
        file = folder / f"{key}.mp3"
        p.items.append(Item(ln, vid, key, len(ln.text), file=file.name, cached=bool(vid) and file.exists()))
    return p


# ---------------------------------------------------------------- ElevenLabs


class ElevenLabs:
    """Мінімальний клієнт на stdlib. Ключ ніде не друкуємо."""

    def __init__(self, api_key: str, base: str = API) -> None:
        self.api_key, self.base = api_key, base.rstrip("/")

    def _open(self, req: urllib.request.Request):
        try:
            return urllib.request.urlopen(req, timeout=TIMEOUT_S)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:500]
            raise ElevenLabsError(f"ElevenLabs HTTP {e.code}: {detail}", charged=e.code >= 500) from None
        except urllib.error.URLError as e:
            # запит не пішов (DNS, відмова з'єднання) — гроші не списано; таймаут читання — могли списати
            sent = isinstance(e.reason, TimeoutError)
            raise ElevenLabsError(f"ElevenLabs недоступний: {e.reason}", charged=sent) from None
        except (TimeoutError, ConnectionError) as e:
            raise ElevenLabsError(f"З'єднання з ElevenLabs обірвалось: {e!r}", charged=True) from None

    def tts(self, voice_id: str, text: str, model: str, settings: dict) -> tuple[bytes, str | None]:
        body = json.dumps({"text": text, "model_id": model, "voice_settings": settings}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}/v1/text-to-speech/{voice_id}?output_format={OUTPUT_FORMAT}", data=body, method="POST",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        with self._open(req) as resp:
            return resp.read(), resp.headers.get("request-id") or resp.headers.get("x-request-id")

    def voices(self) -> list[dict]:
        req = urllib.request.Request(f"{self.base}/v1/voices", headers={"xi-api-key": self.api_key})
        with self._open(req) as resp:
            return json.loads(resp.read().decode("utf-8")).get("voices", [])


def client_from_env() -> ElevenLabs:
    key = config.get("ELEVENLABS_API_KEY")
    if not key:
        raise VoiceError("Немає ELEVENLABS_API_KEY у .env (на Mac A — платні виклики лише звідти).")
    return ElevenLabs(key)


def model_from_env() -> str:
    return config.get("ELEVENLABS_MODEL") or DEFAULT_MODEL


# ---------------------------------------------------------------- тривалість


def probe_duration(path: Path) -> float:
    exe = shutil.which("ffprobe")
    if not exe:
        raise VoiceError("Немає ffprobe (FFmpeg): Mac — `brew install ffmpeg`, Windows — `winget install Gyan.FFmpeg`.")
    r = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1",
                        str(path)], capture_output=True, text=True, timeout=60)
    if "Library not loaded" in r.stderr:     # Homebrew: FFmpeg зібрано під стару версію бібліотеки
        raise VoiceError("FFmpeg зламаний після оновлення бібліотек Homebrew — виконай `brew upgrade ffmpeg` "
                         f"(деталі: {r.stderr.strip().splitlines()[0][:160]})")
    if r.returncode != 0 or not r.stdout.strip():
        raise VoiceError(f"ffprobe не прочитав {path.name}: {r.stderr.strip()[:200]}")
    return round(float(r.stdout.strip()), 3)


# ---------------------------------------------------------------- запуск


def _write_manifest(folder: Path, slug: str, part: int, model: str, p: Plan) -> None:
    data = {"story": slug, "part": part, "model": model, "format": OUTPUT_FORMAT,
            "items": [{**asdict(i.line), "voice_id": i.voice_id, "key": i.key, "file": i.file, "chars": i.chars,
                       "duration_s": i.duration_s} for i in p.items]}
    tmp = folder / "manifest.json.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(folder / "manifest.json")


def run(slug: str, part: int, out: Path, *, dry_run: bool = False, client: ElevenLabs | None = None,
        ledger: Ledger | None = None, model: str | None = None, rate_per_1k: float | None = None,
        force: bool = False, duration=probe_duration, log=print) -> Plan:
    folder = out / slug / f"part{part}"
    shots = Shots.model_validate_json((folder / "shots.json").read_text(encoding="utf-8-sig"))
    script_path = folder / "script.json"
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8-sig")) if script_path.exists() else None
    model = model or model_from_env()
    voice_dir = folder / "voice"
    p = plan(collect(shots, script), voice_ids(bible_mod.load(slug).data), model, voice_dir)
    if rate_per_1k is None:
        try:
            rate_per_1k = costs_mod.rate("ElevenLabs")
        except ValueError as e:
            if not dry_run:
                raise VoiceError(str(e)) from None
    est = None if rate_per_1k is None else round(p.new_chars / 1000 * rate_per_1k, 4)
    log(f"Озвучка {slug} ч.{part}: {len(p.items)} реплік, {p.chars} символів, нових {p.new_chars}"
        + (f" ≈ ${est:.2f}" if est is not None else " (ставка ElevenLabs у COSTS.md — TODO)") + f", модель {model}")
    if p.missing:
        log("Немає voice_id (bible.yaml → voice.voice_id): "
            + "; ".join(f"{who} — шоти {', '.join(shots_)}" for who, shots_ in sorted(p.missing.items())))
    if dry_run:
        return p
    if p.missing:
        raise VoiceError("Спершу затвердь голоси для: " + ", ".join(sorted(p.missing)) + " (`fabrica voices`).")
    client = client or client_from_env()
    own_ledger = ledger is None
    ledger = ledger or Ledger(out / "fabrica.sqlite")
    voice_dir.mkdir(parents=True, exist_ok=True)
    try:
        for item in p.items:
            path = voice_dir / item.file
            if not path.exists():
                settings = SETTINGS.get(item.line.delivery, SETTINGS["normal"])
                with ledger.charge(slug, part, "voice", "elevenlabs", estimate_usd=item.chars / 1000 * rate_per_1k,
                                   units=item.chars, unit="char", input_hash=item.key, force=force,
                                   note=f"{item.line.shot_id} {item.line.character_id}") as c:
                    for w in c.warnings:
                        log(f"  ⚠️ {w}")
                    try:
                        audio, c.request_id = client.tts(item.voice_id, item.line.text, model, settings)
                    except ElevenLabsError as e:
                        c.not_charged = not e.charged
                        raise
                    tmp = path.with_suffix(".part")
                    tmp.write_bytes(audio)
                    tmp.replace(path)
                log(f"  ✓ {item.line.shot_id} {item.line.character_id}: «{item.line.text[:40]}»")
            else:
                item.cached = True
            item.duration_s = duration(path)
            _write_manifest(voice_dir, slug, part, model, p)
    finally:
        if own_ledger:
            ledger.close()
    return p
