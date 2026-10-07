"""Етап voice: озвучка реплік частини через ElevenLabs (Issue #6).

Вхід:  скомпільовані репліки `prompts.build(<slug>, <N>, ["voice"])` (шаблон voice.line): маршрут
       elevenlabs:eleven_v4 + payload — рівно те, що лабораторія показала людям. Тіло запиту = payload,
       розкладений providers.split: voice_id → шлях, output_format → query, решта (text з тегом манери, model_id,
       language_code "es", voice_settings лише stability + similarity_boost, seed) → тіло без змін;
       output/<slug>/part<N>/shots.json (+ script.json) — хто й що каже (маніфест), series/<slug>/bible.yaml —
       `voice.voice_id`, якщо в payload його ще немає.
       Скомпільованих реплік немає (старий формат пакета) — запасний шлях: те саме тіло з shots.json (line_payload).
Вихід: output/<slug>/part<N>/voice/<key>.mp3 + voice/manifest.json (репліка → файл, тривалість, символи).

- Кеш за вмістом: key = sha256(voice_id, query, тіло — разом із seed). Той самий вхід — без нового виклику.
- Гроші: кожен виклик — Ledger.charge(); ставка — docs/COSTS.md («| ElevenLabs | voice | 1K символів | … |»).
  Резерв — символи тексту × ставка; факт — заголовок відповіді `character-cost` (скільки символів списано:
  ціна v4 за 1K не підтверджена, §1.8 / C18) × ставка; заголовка немає — лишається оцінка.
  HTTP 4xx — ElevenLabs не списує → резерв знімаємо; 5xx / обрив — могли списати → резерв лишається.
- Маніфест: delivery — манера, з якою репліку скомпільовано (extra.delivery елемента voice.line), а не
  script.json: звук і маніфест мають збігатися.
- Маніфест пишемо після кожної репліки: перерваний запуск продовжиться з місця зупинки.
- Сухий режим (dry_run): без мережі й витрат — план, символи, кошторис, яких голосів бракує.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fabrica import bible as bible_mod
from fabrica import config
from fabrica import costs as costs_mod
from fabrica import prompts as prompts_mod
from fabrica import providers as providers_mod
from fabrica.ledger import Ledger
from fabrica.models import Script, Shots

API = "https://api.elevenlabs.io"
ROUTE = "elevenlabs:eleven_v4"
DEFAULT_MODEL = "eleven_v4"
OUTPUT_FORMAT = "mp3_44100_192"          # §5.2: тариф Creator
TIMEOUT_S = 120
TAGGED = ("eleven_v4", "eleven_v3")      # теги манери в [дужках] розуміють лише v3 / v4
LANGUAGE = ("eleven_v4", "eleven_v3", "eleven_flash_v2_5", "eleven_turbo_v2_5")    # language_code — лише ці (§5.6)

# Манера → тег і налаштування (§5.4; v4 приймає лише stability і similarity_boost). Джерело правди — шаблон
# voice.line (settings); це — запас, якщо шаблону немає.
DELIVERY: dict[str, dict] = {
    "normal": {"tag": "", "stability": 0.5, "similarity_boost": 0.75},
    "quiet_fear": {"tag": "[quietly, with controlled fear]", "stability": 0.4, "similarity_boost": 0.75},
    "whisper": {"tag": "[whispering]", "stability": 0.4, "similarity_boost": 0.7},
    "shout": {"tag": "[shouting]", "stability": 0.3, "similarity_boost": 0.8},
    "scream": {"tag": "[screaming in terror]", "stability": 0.25, "similarity_boost": 0.8},
    "crying": {"tag": "[sobbing, voice breaking]", "stability": 0.3, "similarity_boost": 0.75},
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
    item_id: str = ""                                    # p<N>-<шот>-voice<n> — елемент лабораторії
    route: str = ROUTE
    payload: dict = field(default_factory=dict)         # повний payload (voice_id, output_format, тіло)
    warnings: list[str] = field(default_factory=list)   # «API: …» — payload не пройде
    billed_chars: int | None = None                     # заголовок character-cost (факт списання)

    def request(self) -> dict[str, dict]:
        """{"path", "query", "body"} — providers.split; тіло — payload без змін. Моделі немає в каталозі (запасний
        шлях з ELEVENLABS_MODEL) — поля розкладаємо за маршрутом eleven_v4: шлях і query в TTS ті самі."""
        try:
            providers_mod.route(self.route)
            route = self.route
        except providers_mod.ProviderError:
            route = ROUTE
        return providers_mod.split(route, {**self.payload, "voice_id": self.voice_id or "?"})


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    missing: dict[str, list[str]] = field(default_factory=dict)   # хто без voice_id → шоти
    compiled: bool = True                                         # False — запасний шлях (без voice.line)

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


def cache_key(voice_id: str, body: dict, query: dict | None = None) -> str:
    """sha256(voice_id, query, тіло): текст, модель, мова, налаштування, сід — усе, що змінює звук."""
    data = json.dumps({"voice_id": voice_id, "query": query or {}, "body": body}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:24]


def delivery_map() -> dict[str, dict]:
    """Манера → {tag, stability, similarity_boost}: з шаблону voice.line, інакше DELIVERY."""
    try:
        t = prompts_mod.load_templates().get("voice.line")
    except prompts_mod.PromptError:
        t = None
    return (t.settings if t is not None else None) or DELIVERY


def line_payload(line: VoiceLine, voice_id: str | None, model: str, item_id: str,
                 deliveries: dict[str, dict] | None = None) -> dict:
    """Запасний шлях без скомпільованих реплік: тіло як у шаблону voice.line (§5.2) — тег манери лише для v3 / v4,
    language_code "es" лише для моделей, що його приймають, voice_settings — stability + similarity_boost, сід."""
    src = deliveries or DELIVERY
    how = src.get(line.delivery) or src.get("normal") or DELIVERY["normal"]
    tag = (how.get("tag") or "") if model in TAGGED else ""
    p = {"voice_id": voice_id, "output_format": OUTPUT_FORMAT, "text": f"{tag} {line.text}".strip(), "model_id": model}
    if model in LANGUAGE:
        p["language_code"] = "es"
    p["voice_settings"] = {k: how.get(k, DELIVERY["normal"][k]) for k in ("stability", "similarity_boost")}
    p["seed"] = prompts_mod.seed_for(item_id)
    return p


def _ext(fmt: str | None) -> str:
    return (fmt or OUTPUT_FORMAT).split("_")[0] or "mp3"


def _api_errors(route: str, payload: dict) -> list[str]:
    try:
        return providers_mod.validate(route, payload)
    except providers_mod.ProviderError:                  # моделі немає в каталозі — перевіряти нема чим
        return []


def _int(v) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _compiled_line(it: prompts_mod.Item, shot: str, own: list[VoiceLine], n: int) -> VoiceLine:
    """Репліка маніфесту для скомпільованого елемента: текст / line_id — з shots.json (n-та репліка шоту), манера —
    з якою скомпільовано (extra.delivery). Рядка в shots.json немає — усе з елемента (текст без тегу манери)."""
    x = it.extra
    if n <= len(own):
        return dataclasses.replace(own[n - 1], delivery=x.get("delivery") or own[n - 1].delivery)
    text = re.sub(r"^\[[^\]]*\]\s*", "", str(it.payload.get("text") or it.prompt)).strip()
    return VoiceLine(shot, x.get("character"), text, x.get("line_id"), x.get("delivery") or "normal",
                     bool(x.get("offscreen")))


def _shot_line(item: prompts_mod.Item, part: int | None) -> tuple[str, int]:
    """(шот, номер репліки) елемента p<N>-<шот>-voice<n>."""
    m = re.match((rf"^p{part}-" if part else r"^p\d-") + r"(.+)-voice(\d+)$", item.id)
    shot = item.extra.get("shot") or (m.group(1) if m else item.id)
    return shot, int(m.group(2)) if m else 1


def plan(lines: list[VoiceLine], voices: dict[str, str | None], model: str, folder: Path,
         items: list[prompts_mod.Item] | None = None, part: int | None = None) -> Plan:
    """План озвучки. items — скомпільовані репліки (voice.line): payload як є; None / [] — запасний шлях з lines."""
    p = Plan(compiled=bool(items))
    by_shot: dict[str, list[VoiceLine]] = {}
    for ln in lines:
        by_shot.setdefault(ln.shot_id, []).append(ln)
    if items:
        rows = []
        for it in items:
            shot, n = _shot_line(it, part)
            rows.append((_compiled_line(it, shot, by_shot.get(shot, []), n), it.id, it.route, dict(it.payload)))
    else:
        deliveries, rows = delivery_map(), []
        for shot, own in by_shot.items():
            for n, line in enumerate(own, 1):
                item_id = f"p{part or 0}-{shot}-voice{n}"
                rows.append((line, item_id, f"elevenlabs:{model}", line_payload(line, None, model, item_id,
                                                                                 deliveries)))
    for line, item_id, route, payload in rows:
        vid = payload.get("voice_id") or voices.get(line.character_id or "")
        if not vid:
            p.missing.setdefault(line.character_id or "?", []).append(line.shot_id)
        payload["voice_id"] = vid
        it = Item(line, vid, "", 0, item_id=item_id, route=route, payload=payload)
        req = it.request()
        it.key = cache_key(vid or "?", req["body"], req["query"])
        it.chars = len(str(req["body"].get("text") or ""))
        it.file = f"{it.key}.{_ext(req['query'].get('output_format'))}"
        it.cached = bool(vid) and (folder / it.file).exists()
        it.warnings = _api_errors(route, payload) if vid else []
        p.items.append(it)
    return p


def compiled_items(slug: str, part: int, out: Path) -> list[prompts_mod.Item]:
    """Скомпільовані репліки частини (маршрут TTS + payload). Старий формат пакета (без payload) — []."""
    out_items = []
    for it in prompts_mod.build(slug, str(part), ["voice"], out_root=out):
        try:
            tts = bool(it.route and it.payload) and providers_mod.route(it.route).kind == "voice"
        except providers_mod.ProviderError:
            tts = False
        if tts:
            out_items.append(it)
    return out_items


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

    def tts(self, voice_id: str, body: dict, query: dict | None = None) -> tuple[bytes, str | None, int | None]:
        """POST /v1/text-to-speech/<voice_id>?<query> з тілом body як є → (аудіо, request-id, character-cost)."""
        q = urllib.parse.urlencode(query or {})
        req = urllib.request.Request(
            f"{self.base}/v1/text-to-speech/{urllib.parse.quote(voice_id, safe='')}" + (f"?{q}" if q else ""),
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        with self._open(req) as resp:
            return (resp.read(), resp.headers.get("request-id") or resp.headers.get("x-request-id"),
                    _int(resp.headers.get("character-cost")))

    def voices(self) -> list[dict]:
        req = urllib.request.Request(f"{self.base}/v1/voices", headers={"xi-api-key": self.api_key})
        with self._open(req) as resp:
            return json.loads(resp.read().decode("utf-8")).get("voices", [])


def client_from_env() -> ElevenLabs:
    key = config.get("ELEVENLABS_API_KEY")
    if not key:
        raise VoiceError("Немає ELEVENLABS_API_KEY у .env (на Mac A — платні виклики лише звідти).")
    return ElevenLabs(key)


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
    data = {"story": slug, "part": part, "model": model, "compiled": p.compiled,
            "items": [{**asdict(i.line), "item": i.item_id, "route": i.route, "voice_id": i.voice_id, "key": i.key,
                       "file": i.file, "chars": i.chars, "billed_chars": i.billed_chars, "seed": i.payload.get("seed"),
                       "format": i.payload.get("output_format"), "duration_s": i.duration_s} for i in p.items]}
    tmp = folder / "manifest.json.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    config.replace_atomic(tmp, folder / "manifest.json")


def _source(slug: str, part: int, out: Path, dry_run: bool, log) -> list[prompts_mod.Item]:
    """Скомпільовані репліки; не зібрались — у dry-run попередження й запасний шлях, у справжньому запуску — стоп
    (автоматика шле лише те, що бачила лабораторія)."""
    try:
        items = compiled_items(slug, part, out)
    except prompts_mod.PromptError as e:
        if not dry_run:
            raise VoiceError(f"репліки не скомпілювались ({e}) — виправ і перезбери `fabrica prompts {slug} {part}`")
        log(f"  ⚠️ репліки не скомпілювались ({e}) — план із shots.json (запасний шлях)")
        return []
    if not items:
        log("  ⚠️ скомпільованих реплік (voice.line з payload) немає — тіло складаю з shots.json (запасний шлях)")
    return items


def run(slug: str, part: int, out: Path, *, dry_run: bool = False, client: ElevenLabs | None = None,
        ledger: Ledger | None = None, model: str | None = None, rate_per_1k: float | None = None,
        force: bool = False, duration=probe_duration, log=print) -> Plan:
    folder = out / slug / f"part{part}"
    shots = Shots.model_validate_json((folder / "shots.json").read_text(encoding="utf-8-sig"))
    script_path = folder / "script.json"
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8-sig")) if script_path.exists() else None
    voice_dir = folder / "voice"
    items = _source(slug, part, out, dry_run, log)
    explicit = model or config.get("ELEVENLABS_MODEL")
    model = (items[0].payload.get("model_id") if items else None) or explicit or DEFAULT_MODEL
    if items and explicit and explicit != model:
        log(f"  ⚠️ модель {explicit} ігнорую: репліки скомпільовано під {model} — шлю payload як є "
            "(модель змінюють у шаблоні voice.line)")
    p = plan(collect(shots, script), voice_ids(bible_mod.load(slug).data), model, voice_dir, items, part)
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
    bad = [i for i in p.items if i.warnings]
    for i in bad[:5]:
        log(f"  ⛔ {i.item_id}: {'; '.join(i.warnings)}")
    if dry_run:
        return p
    if p.missing:
        raise VoiceError("Спершу затвердь голоси для: " + ", ".join(sorted(p.missing)) + " (`fabrica voices`).")
    if bad:
        raise VoiceError(f"{len(bad)} реплік не пройдуть API (див. ⛔ вище) — виправ шаблон voice.line / дані")
    client = client or client_from_env()
    own_ledger = ledger is None
    ledger = ledger or Ledger(out / "fabrica.sqlite")
    voice_dir.mkdir(parents=True, exist_ok=True)
    try:
        for item in p.items:
            path = voice_dir / item.file
            if not path.exists():
                req = item.request()
                with ledger.charge(slug, part, "voice", "elevenlabs", estimate_usd=item.chars / 1000 * rate_per_1k,
                                   units=item.chars, unit="char", input_hash=item.key, force=force,
                                   note=f"{item.item_id} {item.line.character_id}") as c:
                    for w in c.warnings:
                        log(f"  ⚠️ {w}")
                    try:
                        audio, c.request_id, item.billed_chars = client.tts(item.voice_id, req["body"], req["query"])
                    except ElevenLabsError as e:
                        c.not_charged = not e.charged
                        raise
                    if item.billed_chars is not None:             # факт списання; немає заголовка — оцінка
                        c.actual_usd = round(item.billed_chars / 1000 * rate_per_1k, 6)
                    tmp = path.with_suffix(".part")
                    tmp.write_bytes(audio)
                    config.replace_atomic(tmp, path)
                log(f"  ✓ {item.line.shot_id} {item.line.character_id}: «{item.line.text[:40]}»")
            else:
                item.cached = True
            item.duration_s = duration(path)
            _write_manifest(voice_dir, slug, part, model, p)
    finally:
        if own_ledger:
            ledger.close()
    return p
