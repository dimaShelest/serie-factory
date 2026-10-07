"""Шот-спека — режисерський шар: shots.json + script.json + оверлей → ShotSpec, з якої компілюються промпти.

Спека описує шот так, як його бачить режисер (docs/research/2026-10-07-generators.md, §6.1): що в кадрі
в першу мить (frame), що рухається (action), камера, звук, люди з ракурсом і місцем на екрані, репліки з
манерою, наскільки видно обличчя (face → маршрут відео). Промпти пишуть компілятори зі спеки, не руками.

Джерела:
    output/<slug>/part<N>/shots.json   — шоти (tier, тривалість, хто в кадрі, репліки)
    output/<slug>/part<N>/script.json  — манера реплік (delivery), якщо файл є
    series/<slug>/part<N>_prompts_en.yaml — англійський оверлей: v2 (version: 2, scenes, shots) строгий;
                                         v1 (шот → composition/action/camera/…) ще читається
    series/<slug>/lab/test_pack.yaml   — тест-пак: ті самі ShotSpec (set="test-pack", id T1, T4-face …)
Кліпи (§12): clips(spec, providers.generation()) ділить відео шоту за профілем довжини кліпу (dropshot — 5 с).

Помилки оверлею й тест-паку — SpecError українською з назвою файлу й шоту; що можна обійти (немає опису
шоту, персонаж без англійського опису) — warnings у спеці.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fabrica import bible as bible_mod
from fabrica.models import Script, Shot, Shots

if TYPE_CHECKING:
    from fabrica.prompts import Data

View = Literal["face", "three_quarter", "profile", "back", "silhouette", "blurred", "distant", "hidden"]
Screen = Literal["left", "center", "right"]
Move = Literal["static", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "follow",
               "track_left", "track_right", "orbit", "crane_up", "crane_down", "handheld", "rack_focus", "dolly_zoom"]
Mode = Literal["i2v", "first_last", "t2v", "still", "none"]
VideoMode = Literal["i2v", "first_last", "t2v"]
Face = Literal["none", "partial", "clear"]
Beat = Literal["establish", "investigate", "dread_hold", "reaction", "insert", "scare", "dialogue", "transition"]
Time = Literal["night", "dawn", "day", "dusk"]
Delivery = Literal["normal", "quiet_fear", "whisper", "shout", "scream", "crying"]

VIDEO_MODES = ("i2v", "first_last", "t2v")
REUSE = ("shot:", "plate:", "asset:")
GEN_MIN_S = 4                       # Seedance не генерує коротше за 4 с
UA = "[UA → EN]"                    # маркер українського тексту-заглушки в промпті
# shots.json framing → розмір кадру зі словника Seedance (§2.4)
SIZES = {"extreme_wide": "extreme wide", "wide": "wide", "medium_wide": "medium wide", "medium": "medium",
         "medium_close": "medium close-up", "close_up": "close-up", "insert": "extreme close-up"}
V1_KEYS = {"composition", "action", "camera", "light", "variant", "people", "framing"}
LIPS = ("face", "three_quarter", "profile")          # ракурси, де видно рот того, хто говорить
FRONTAL = ("face", "three_quarter")                   # обличчя до камери → face clear (маршрут з обличчям)
TIME_ADJ = {"day": "денний", "night": "нічний", "dawn": "світанковий", "dusk": "вечірній"}
TIER_RES = {"hero": "720p", "secondary": "480p", "found_footage": "480p"}
VideoTier = Literal["hero", "secondary", "found_footage"]
_LIGHT_TIME = [("dawn", r"\b(dawn|sunrise)\b"), ("dusk", r"\b(dusk|sunset|twilight)\b"),
               ("day", r"\b(day|daylight|daytime|sunlight|midday|noon)\b"), ("night", r"\b(night|moonlight)\b")]


class SpecError(ValueError):
    """Оверлей або тест-пак зламаний — повідомлення називає файл, шот і що виправити."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- спека


class Person(_Strict):
    id: str
    view: View = "face"
    screen: Screen | None = None
    facing: str | None = None
    state: list[str] = []            # ключі prompt_en.states (nosebleed, wet …)

    @field_validator("state", mode="before")
    @classmethod
    def _one_state(cls, v: object) -> object:
        return [v] if isinstance(v, str) else v       # v1: {id: beto, state: wet}


class Camera(_Strict):
    size: str | None = None          # extreme wide | wide | medium wide | medium | medium close-up | close-up …
    move: Move = "static"
    speed: str | None = None         # very slow | slow | steady | moderate
    target: str | None = None        # до чого / з чим рухається камера
    endpoint: str | None = None
    angle: str | None = None         # eye level | low angle | high angle | overhead | POV
    lens_mm: int | None = None
    shake: Literal["none", "light", "moderate", "strong"] = "none"
    text: str | None = None          # рядок camera: компілятор бере дослівно; move тоді невідомий, не static

    @model_validator(mode="after")
    def _text_or_move(self) -> Camera:
        if self.text and (self.move != "static" or self.speed or self.target or self.endpoint):
            raise ValueError("або рядок (text), або словник із move / speed / target / endpoint — не обидва: "
                             "рядок компілятор бере дослівно, рух зі словника загубився б")
        return self


class Sound(_Strict):
    ambience: list[str] = []
    sfx: list[str] = []              # музики немає ніколи: «No BGM»


class Line(_Strict):
    n: int
    speaker: str | None
    line_id: str | None = None       # репліка script.json, якщо є
    text_es: str
    delivery: Delivery = "normal"
    on_screen: bool = False          # рот того, хто говорить, у кадрі → lip-sync
    offscreen: bool = False
    delivery_source: Literal["script", "overlay", "guess", "default"]


class ClipIn(_Strict):
    """Кліп довгого шоту (§12): кліп k ≥ 2 стартує з останнього кадру кліпу k-1."""

    action: str
    end_state: str | None = None
    camera: Camera | None = None

    @field_validator("camera", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return _camera_before(v)


class ShotSpec(_Strict):
    id: str                          # 4.03 · T1 · T4-face
    set: str                         # "1"…"4" · "test-pack"
    title: str
    scene_id: str | None
    tier: str
    beat: Beat | None = None
    mode: Mode
    edit_s: float                    # довжина в монтажі (shots.json duration_s)
    gen_s: int                       # довжина кліпу: max(4, ceil(edit_s)); 0 — відео немає
    location: str
    variant: str | None
    light: str | None                # None — світло плити (prompt_en.yaml)
    time: Time | None
    footage: Literal["vhs", "phone"] | None
    frame: str                       # статична композиція ПЕРШОЇ миті (без дієслів руху)
    end_frame: str | None            # mode first_last: композиція останньої миті
    action: str                      # рух, фізично, з прислівниками міри; спершу причина, потім реакція
    end_state: str | None
    camera: Camera
    sound: Sound
    people: list[Person]
    lines: list[Line]
    face: Face
    video_id: str = "video"          # суфікс відео-елемента: tp-T4-buildup
    window: tuple[float, float] | None = None     # §12: що з кліпу лишити в монтажі (с від початку кліпу)
    event_s: float | None = None                  # §12: секунда події (скрімер) у кліпі
    clips: list[ClipIn] = []                      # §12: кліпи довгого шоту по порядку
    handoff: Literal["cut", "continue"] = "cut"   # §12: continue — старт з останнього кадру попереднього шоту
    continuity: list[str] = []       # видимі факти, що тримаються (стан сцени + шоту)
    success: list[str] = []
    notes: list[str] = []
    warnings: list[str] = []

    @property
    def prefix(self) -> str:
        """Префікс id елементів: p1-4.03 · tp-T4-face."""
        return f"tp-{self.id}" if self.set == "test-pack" else f"p{self.set}-{self.id}"

    @property
    def frame_ref(self) -> str:
        return f"{self.prefix.replace('-', '.')}.frame"

    @property
    def end_ref(self) -> str:
        return f"{self.prefix.replace('-', '.')}.end"


# ---------------------------------------------------------------- оверлей (вхід)


def _people_before(v: object) -> object:
    return [{"id": p} if isinstance(p, str) else p for p in v] if isinstance(v, list) else v


def _camera_before(v: object) -> object:
    if isinstance(v, str):
        return {"text": v}
    if v is None or isinstance(v, (dict, BaseModel)):
        return v
    raise ValueError("має бути рядком або словником {size, move, …}")


class LineIn(_Strict):
    delivery: Delivery | None = None
    on_screen: bool | None = None


class SceneIn(_Strict):
    """Типові значення для всіх шотів сцени (ключ — scene_id з shots.json: «s04» або «4»)."""

    time: Time | None = None
    variant: str | None = None
    light: str | None = None
    state: dict[str, list[str]] = {}          # {vale: [nosebleed]}; ключ може бути групою
    continuity: list[str] = []
    sound: Sound | None = None

    @field_validator("state", mode="before")
    @classmethod
    def _one_state(cls, v: object) -> object:
        return {k: [s] if isinstance(s, str) else s for k, s in v.items()} if isinstance(v, dict) else v


class ShotIn(_Strict):
    beat: Beat | None = None
    mode: VideoMode | None = None             # None → i2v (still / montage / reuse — з tier)
    location: str | None = None               # None → shots.json location_id
    variant: str | None = None
    time: Time | None = None
    light: str | None = None
    people: list[Person] | None = None        # None → characters із shots.json
    frame: str | None = None
    end_frame: str | None = None
    action: str | None = None
    end_state: str | None = None
    camera: Camera | None = None
    sound: Sound | None = None
    continuity: list[str] = []                # додається до continuity сцени
    face: Face | None = None
    lines: dict[int, LineIn] = {}             # n репліки в шоті (з 1) → delivery / on_screen
    success: list[str] = []
    notes: list[str] = []
    # §12 (кліпи й стики; розбивку на кліпи робить окрема фаза — тут лише читаємо й перевіряємо форму)
    window: tuple[float, float] | None = None # що з кліпу лишити в монтажі, с від початку кліпу
    event_s: float | None = Field(None, ge=0) # секунда події (скрімер) у кліпі
    clips: list[ClipIn] = []                  # кліпи довгого шоту по порядку
    handoff: Literal["cut", "continue"] = "cut"

    @field_validator("people", mode="before")
    @classmethod
    def _ids(cls, v: object) -> object:
        return _people_before(v)

    @field_validator("camera", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return _camera_before(v)

    @model_validator(mode="after")
    def _ends(self) -> ShotIn:
        if self.mode == "first_last" and not self.end_frame:
            raise ValueError("mode first_last потребує end_frame (композиція останньої миті)")
        if self.end_frame and self.mode != "first_last":
            raise ValueError("end_frame лише для mode first_last")
        if self.window and not 0 <= self.window[0] < self.window[1]:
            raise ValueError(f"window {list(self.window)}: потрібно [початок, кінець], 0 ≤ початок < кінець")
        if self.window and self.event_s is not None and not self.window[0] <= self.event_s <= self.window[1]:
            raise ValueError(f"event_s {self.event_s:g} поза window {list(self.window)}")
        return self


# ---------------------------------------------------------------- тест-пак (вхід)


class TPVideo(_Strict):
    id: str = "video"
    resolution: Literal["480p", "720p"] | None = None     # v1; без tier — tier з роздільності
    tier: VideoTier | None = None
    duration_s: float = Field(gt=0)
    mode: VideoMode = "i2v"
    action: str
    end_state: str | None = None
    end_frame: str | None = None
    camera: Camera | None = None
    light: str | None = None
    sound: Sound = Sound()
    beat: Beat | None = None
    face: Face | None = None
    notes: list[str] = []

    @field_validator("camera", mode="before")
    @classmethod
    def _text(cls, v: object) -> object:
        return _camera_before(v)


class TPFrame(_Strict):
    id: str | None = None            # лише extra_frames
    location: str
    variant: str | None = None
    light: str | None = None
    time: Time | None = None
    footage: Literal["vhs", "phone"] | None = None
    people: list[Person] = []
    framing: str | None = None       # v1 → camera.size
    composition: str | None = None   # v1 → frame
    frame: str | None = None
    end_frame: str | None = None
    camera: Camera | None = None     # статична частина: size / angle / lens_mm
    continuity: list[str] = []
    beat: Beat | None = None
    face: Face | None = None
    notes: list[str] = []
    videos: list[TPVideo] = []       # лише extra_frames

    @field_validator("people", mode="before")
    @classmethod
    def _ids(cls, v: object) -> object:
        return _people_before(v)

    @model_validator(mode="after")
    def _one_text(self) -> TPFrame:
        if bool(self.frame) == bool(self.composition):
            raise ValueError("потрібен рівно один опис кадру: frame (або старий composition)")
        if self.camera and self.camera.text:
            raise ValueError("camera кадру — лише словник (size / angle / lens_mm); рядок camera — у videos")
        return self


class TPTest(_Strict):
    id: str
    title: str
    frame: TPFrame
    videos: list[TPVideo] = []
    extra_frames: list[TPFrame] = []
    success: list[str] = []
    notes: list[str] = []

    @model_validator(mode="after")
    def _shape(self) -> TPTest:
        if self.frame.id or self.frame.videos:
            raise ValueError("frame тесту без id і videos: відео — у videos тесту, додаткові кадри — в extra_frames")
        if any(not ef.id for ef in self.extra_frames):
            raise ValueError("кожен extra_frames потребує id")
        if len(self.videos) > 1 or any(len(ef.videos) > 1 for ef in self.extra_frames):
            raise ValueError("один кадр — одне відео; друге відео з того самого кадру — окремим extra_frames")
        return self


# ---------------------------------------------------------------- помилки українською


_WHY = {"extra_forbidden": "зайве поле", "missing": "бракує поля", "string_type": "має бути рядком",
        "int_type": "має бути цілим числом", "int_parsing": "має бути цілим числом",
        "int_from_float": "має бути цілим числом", "float_type": "має бути числом", "float_parsing": "має бути числом",
        "bool_type": "має бути true / false", "bool_parsing": "має бути true / false", "list_type": "має бути списком",
        "dict_type": "має бути словником", "model_type": "має бути словником",
        "model_attributes_type": "має бути словником"}


def _why(e: dict) -> str:
    loc = ".".join(str(x) for x in e["loc"] if x != "[key]")
    t, ctx = e["type"], e.get("ctx") or {}
    if t == "literal_error":
        allowed = str(ctx.get("expected", "")).replace("'", "").replace(" or ", ", ")
        msg = f"невідоме значення «{e['input']}» (можна: {allowed})"
    elif t == "value_error":
        msg = str(ctx.get("error", e["msg"]))
    elif t in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        sign = {"greater_than": ">", "greater_than_equal": "≥", "less_than": "<", "less_than_equal": "≤"}[t]
        msg = f"має бути {sign} {next(iter(ctx.values()))}"
    else:
        msg = _WHY.get(t, e["msg"])
    return f"{loc}: {msg}" if loc else msg


def _validate(model: type[BaseModel], raw: object, where: str) -> tuple[BaseModel | None, list[str]]:
    try:
        return model.model_validate({} if raw is None else raw), []
    except ValidationError as e:
        return None, [f"{where}: {_why(err)}" for err in e.errors(include_url=False)]


def _read_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise SpecError(f"{path.name}: зламаний YAML — {e}") from None


def _key(key: object, what: str, name: str) -> tuple[str | None, str | None]:
    """Ключ шоту / сцени як рядок. 4.10 без лапок YAML читає як число 4.1 — це помилка."""
    if isinstance(key, str):
        return key, None
    if isinstance(key, int) and not isinstance(key, bool):
        return str(key), None
    if isinstance(key, float):
        return None, f"{name}: id {what} «{key}» без лапок — YAML читає його як число; візьми в лапки (\"4.10\")"
    return None, f"{name}: id {what} «{key}» має бути рядком"


# ---------------------------------------------------------------- оверлей


def overlay_path(slug: str, part: int) -> Path:
    return bible_mod.SERIES / slug / f"part{part}_prompts_en.yaml"


def _from_v1(body: object) -> object:
    """Шот v1 → v2: composition → frame, framing → camera.size, рядок camera → camera.text."""
    if not isinstance(body, dict):
        return body
    out = {k: v for k, v in body.items() if k not in ("composition", "framing")}
    if "composition" in body:
        out["frame"] = body["composition"]
    cam = body.get("camera")
    if body.get("framing") and (cam is None or isinstance(cam, (str, dict))):
        out["camera"] = {**({"text": cam} if isinstance(cam, str) else cam or {}), "size": str(body["framing"]).lower()}
    return out


def load_overlay(slug: str, part: int, path: Path | None = None) -> dict:
    """Оверлей частини → {version, path, scenes: {id: SceneIn}, shots: {id: ShotIn}}; {} — файлу немає.

    v1 (без version: верхній рівень — шоти з composition/action/camera/light/variant/people/framing) приводиться
    до форми v2; v2 — строгий (version: 2, scenes, shots). Усі помилки — одним SpecError.
    """
    path = path or overlay_path(slug, part)
    if not path.exists():
        return {}
    raw = _read_yaml(path)
    if raw is None:
        return {}
    name = path.name
    if not isinstance(raw, dict):
        raise SpecError(f"{name}: очікую словник (version: 2, scenes, shots)")
    errors: list[str] = []
    if "version" not in raw:
        if found := [k for k in ("scenes", "shots") if k in raw]:
            raise SpecError(f"{name}: є {', '.join(found)}, але немає version: 2 — додай рядок version: 2 на початок")
        version, scenes_raw = 1, {}
        shots_raw = {}
        for k, body in raw.items():
            if isinstance(body, dict) and (extra := sorted(set(body) - V1_KEYS, key=str)):
                errors.append(f"{name} · шот {k}: поля {extra} — не з v1 (нові поля — в оверлеї version: 2)")
                body = {f: v for f, v in body.items() if f in V1_KEYS}
            shots_raw[k] = _from_v1(body)
    else:
        version = raw["version"]
        if version != 2:
            raise SpecError(f"{name}: version {version!r} — підтримую лише version: 2 (або старий v1 без version)")
        extra = sorted(set(raw) - {"version", "scenes", "shots"}, key=str)
        if extra:
            errors.append(f"{name}: зайві ключі верхнього рівня {extra} (є version, scenes, shots)")
        scenes_raw, shots_raw = raw.get("scenes") or {}, raw.get("shots") or {}
        for what, block in (("scenes", scenes_raw), ("shots", shots_raw)):
            if not isinstance(block, dict):
                raise SpecError(f"{name}: {what} має бути словником (id → опис)")
    scenes: dict[str, SceneIn] = {}
    shots: dict[str, ShotIn] = {}
    for out, block, model, what in ((scenes, scenes_raw, SceneIn, "сцени"), (shots, shots_raw, ShotIn, "шоту")):
        for key, body in block.items():
            k, err = _key(key, what, name)
            if err:
                errors.append(err)
                continue
            if k in out:
                errors.append(f"{name}: id {what} «{k}» повторюється")
                continue
            obj, errs = _validate(model, body, f"{name} · {'сцена' if model is SceneIn else 'шот'} {k}")
            errors += errs
            if obj is not None:
                out[k] = obj
    if errors:
        raise SpecError("\n".join(errors))
    return {"version": version, "path": path, "scenes": scenes, "shots": shots}


# ---------------------------------------------------------------- виведення (чисті функції)


def gen_seconds(edit_s: float, route_max: int = 30) -> int:
    """Скільки секунд генерувати: max(4, ceil(edit_s)), не більше ліміту маршруту."""
    return min(route_max, max(GEN_MIN_S, math.ceil(round(edit_s, 3))))


def edit_window(spec: ShotSpec) -> str | None:
    """Підказка для монтажу: «кліп 4 с → у монтаж 1 с». None — відео немає."""
    if spec.mode not in VIDEO_MODES:
        return None
    return f"кліп {spec.gen_s} с → у монтаж {spec.edit_s:g} с"


class Clip(_Strict):
    """Кліп відео шоту (§12): що генерувати одним викликом і що з нього лишити в монтажі."""

    index: int                       # 1 … of
    of: int
    gen_s: int                       # довжина генерації, с
    window: tuple[float, float]      # що лишити в монтажі, с від початку кліпу
    action: str
    end_state: str | None = None
    camera: Camera
    start: Literal["frame", "prev_last", "none"]   # стартовий кадр шоту / останній кадр попереднього / t2v
    warnings: list[str] = []


def clip_plan(edit_s: float, profile: dict) -> tuple[int, int]:
    """(довжина кліпу, скільки кліпів) за профілем: clip_s — найменша дозволена ≥ edit_s, інакше найбільша × n;
    clip_min_s…clip_max_s — max(min, ceil(edit_s)), довше за максимум — n рівних кліпів."""
    edit = round(edit_s, 3)
    if "clip_s" in profile:
        allowed = sorted(profile["clip_s"])
        fit = [c for c in allowed if c >= edit]
        return (fit[0], 1) if fit else (allowed[-1], math.ceil(edit / allowed[-1]))
    lo, hi = profile["clip_min_s"], profile["clip_max_s"]
    n = max(1, math.ceil(edit / hi))
    return max(lo, math.ceil(round(edit / n, 3))), n


def _window(spec: ShotSpec, gen_s: int) -> tuple[tuple[float, float], list[str]]:
    """Вікно одного кліпу: window з оверлею → навколо event_s (скрімер) → (0, edit_s)."""
    keep = min(spec.edit_s, gen_s)
    if spec.window:
        a, b = spec.window
        if b <= gen_s:
            return (a, b), [f"window {b - a:g} с ≠ edit_s {spec.edit_s:g} с (shots.json) — у монтажі шот вийде "
                            "іншої довжини"] if abs((b - a) - spec.edit_s) > 0.05 else []
        return (a, float(gen_s)) if a < gen_s else (0.0, keep), [
            f"window {list(spec.window)} виходить за кліп {gen_s} с — обрізано"]
    if spec.event_s is not None:
        if spec.event_s > gen_s:
            return (0.0, keep), [f"event_s {spec.event_s:g} за межами кліпу {gen_s} с — вікно з початку"]
        a = min(max(0.0, spec.event_s - keep / 2), gen_s - keep)
        return (round(a, 3), round(a + keep, 3)), []
    return (0.0, keep), []


def clips(spec: ShotSpec, profile: dict) -> list[Clip]:
    """Кліпи відео шоту за профілем генерації (providers.generation()); [] — шот без відео.

    Шот довший за кліп → n кліпів; кліп k ≥ 2 стартує з останнього кадру кліпу k-1. Дія / кінцевий стан / камера
    кліпу — з clips оверлею, інакше та сама дія («continues») + попередження. handoff continue — перший кліп
    стартує з останнього кадру попереднього шоту. Попередження — у warnings першого кліпу.
    """
    if spec.mode not in VIDEO_MODES:
        return []
    clip_s, n = clip_plan(spec.edit_s, profile)
    first = "prev_last" if spec.handoff == "continue" else "none" if spec.mode == "t2v" else "frame"
    warnings: list[str] = []
    if n == 1:
        window, warnings = _window(spec, clip_s)
        return [Clip(index=1, of=1, gen_s=clip_s, window=window, action=spec.action, end_state=spec.end_state,
                     camera=spec.camera, start=first, warnings=warnings)]
    if spec.window or spec.event_s is not None:
        warnings.append(f"window / event_s — лише для шоту з одного кліпу; тут {n} кліпи — ігнорую")
    if not spec.clips:
        warnings.append(f"шот {spec.edit_s:g} с довший за кліп {clip_s} с → {n} кліпи: опиши clips: [{{action, "
                        "end_state, camera}] в оверлеї — поки та сама дія в кожному")
    elif len(spec.clips) != n:
        warnings.append(f"clips: в оверлеї {len(spec.clips)}, а кліпів {n} (шот {spec.edit_s:g} с, кліп {clip_s} с)")
    out = []
    for k in range(1, n + 1):
        own = spec.clips[k - 1] if k <= len(spec.clips) else None
        last = k == n
        if own:
            action, end, cam = own.action, own.end_state, own.camera or spec.camera
            end = end or (spec.end_state if last else None)
        else:
            action = spec.action if k == 1 else f"The same action continues. {spec.action}"
            end, cam = spec.end_state if last else None, spec.camera
        keep = round(spec.edit_s - clip_s * (n - 1), 3) if last else float(clip_s)
        out.append(Clip(index=k, of=n, gen_s=clip_s, window=(0.0, keep), action=action, end_state=end, camera=cam,
                        start=first if k == 1 else "prev_last", warnings=warnings if k == 1 else []))
    return out


def derive_mode(tier: str, reuse: str | None = None, mode: str | None = None) -> str:
    """montage / перевикористання → none; still → still; інакше mode оверлею або i2v."""
    if tier == "montage" or (reuse or "").startswith(REUSE):
        return "none"
    if tier == "still":
        return "still"
    return mode or "i2v"


def derive_face(people: list[Person], camera: Camera | None = None) -> str:
    """clear — хтось анфас / 3/4 (будь-який розмір кадру); partial — лише профіль / здалеку; інакше none.

    Розмір кадру маршрут не змінює: Seedance на Replicate відхиляє фронтальне обличчя й на загальному
    (дослідження §6.2 п.3, C1) — тож clear → маршрут з обличчям. Далекі фігури без читабельного обличчя —
    view: distant. camera лишено в підписі для сумісності.
    """
    views = {p.view for p in people}
    if views & set(FRONTAL):
        return "clear"
    if views & {"profile", "distant"}:
        return "partial"
    return "none"


def guess_delivery(text: str) -> str | None:
    """¡…! → shout; «…» в кінці або ¿…? → normal (тихо, але без шепоту); шепіт не вгадуємо ніколи."""
    if re.search(r"¡[^!]*!", text):
        return "shout"
    t = text.strip()
    if t.endswith(("…", "...")) or re.search(r"¿[^?]*\?", t):
        return "normal"
    return None


def _union(*lists: list[str]) -> list[str]:
    return list(dict.fromkeys(x for lst in lists for x in lst))


def expand_people(entries: list[Person], groups: dict[str, list[str]],
                  state: dict[str, list[str]] | None = None) -> list[Person]:
    """Групи (los_cuatro) → учасники з тим самим view / facing / state і screen=None.

    Явний запис людини виграє в групи незалежно від порядку («четвірка, але Vale спиною»); між групами —
    перший виграє. state — стан сцени {id або група: [ключі]}: іде перед власним станом людини.
    """
    scene: dict[str, list[str]] = {}
    for key, st in (state or {}).items():
        for pid in groups.get(key, [key]):
            scene[pid] = _union(scene.get(pid, []), st)
    explicit = {p.id for p in entries if p.id not in groups}
    out: dict[str, Person] = {}
    for p in entries:
        for pid in groups.get(p.id, [p.id]):
            if pid not in out and (pid == p.id or pid not in explicit):
                one = p if pid == p.id else p.model_copy(update={"id": pid, "screen": None})
                out[pid] = one.model_copy(update={"state": _union(scene.get(pid, []), one.state)})
    return list(out.values())


def derive_lines(shot: Shot, people: list[Person], script_delivery: dict[str, str] | None = None,
                 overlay: dict[int, LineIn] | None = None) -> tuple[list[Line], list[str]]:
    """Репліки шоту → Line. Манера: script.json → оверлей → вгадана → normal (delivery_source — звідки).

    script.json «normal» = не задано (model_dump пише normal у кожну репліку) — тоді діє оверлей.
    on_screen: has_dialogue_visible, той, хто говорить, у people з видимим ротом (анфас / 3/4 / профіль) і не
    за кадром; оверлей може перевизначити, але не всупереч цьому. Повертає (репліки, попередження).
    """
    script_delivery, overlay = script_delivery or {}, overlay or {}
    lips = {p.id for p in people if p.view in LIPS}
    lines, warnings = [], []
    for n, d in enumerate(shot.dialogue, 1):
        o = overlay.get(n) or LineIn()
        if script_delivery.get(d.line_id, "normal") != "normal":
            how, src = script_delivery[d.line_id], "script"
            if o.delivery and o.delivery != how:
                warnings.append(f"репліка {n}: delivery «{o.delivery}» з оверлею не діє — script.json каже «{how}»")
        elif o.delivery:
            how, src = o.delivery, "overlay"
        elif guess := guess_delivery(d.text_es):
            how, src = guess, "guess"
        else:
            how, src = "normal", "default"
        can = d.character_id in lips and not d.offscreen
        on = shot.has_dialogue_visible and can
        if o.on_screen and not can:
            why = ("мовець за кадром" if d.offscreen else
                   "рота мовця не видно (немає в people з view face / three_quarter / profile)")
            warnings.append(f"репліка {n}: on_screen з оверлею неможливий — {why}")
        elif o.on_screen is not None:
            on = o.on_screen
        lines.append(Line(n=n, speaker=d.character_id, line_id=d.line_id, text_es=d.text_es, delivery=how,
                          on_screen=on, offscreen=d.offscreen, delivery_source=src))
    return lines, warnings


def plate_time(data: Data, location: str, variant: str | None = None) -> str | None:
    """Час доби плити: time стану, інакше (якщо стан не replace) time локації."""
    loc = (data.en.get("locations") or {}).get(location) or {}
    v = (loc.get("variants") or {}).get(variant) if variant else None
    if isinstance(v, dict):
        if v.get("time"):
            return v["time"]
        if v.get("replace"):
            return None
    return loc.get("time")


def light_time(light: str | None) -> str | None:
    """Час доби зі слів світла: dawn / dusk / day / night."""
    low = (light or "").lower()
    return next((t for t, rx in _LIGHT_TIME if re.search(rx, low)), None)


def _time(data: Data, location: str, variant: str | None, time: str | None, light: str | None
          ) -> tuple[str | None, list[str]]:
    plate, said = plate_time(data, location, variant), time or light_time(light)
    if plate and plate not in TIME_ADJ:
        return said, [f"prompt_en.yaml: time «{plate}» у {location}.{variant or 'plate'} — можна "
                      f"{', '.join(TIME_ADJ)}"]
    if said and plate and said != plate:
        loc = (data.en.get("locations") or {}).get(location) or {}
        names = sorted((k for k in loc.get("variants") or {} if plate_time(data, location, k) == said),
                       key=lambda k: not (variant and str(k).startswith(variant)))   # living → living_day першим
        fit = [f"variant {' або '.join(map(str, names))}"] if names else []
        fit += ["плиту без variant"] if variant and loc.get("time") == said else []
        fix = f"візьми {' або '.join(fit)}" if fit else f"потрібен окремий {TIME_ADJ.get(said, said)} стан локації"
        return said, [f"час шоту «{said}» ≠ час плити «{plate}» ({location}.{variant or 'plate'}) — {fix}"]
    return said or plate, []


# ---------------------------------------------------------------- перевірки з prompt_en.yaml


def _known(data: Data) -> set[str]:
    """Хто може бути в people: characters, members і supporting з tag / look (другорядні — лише текстом, без
    референсу обличчя; supporting лише з голосом — не в кадрі)."""
    sup = {k for k, v in (data.en.get("supporting") or {}).items()
           if isinstance(v, dict) and (v.get("tag") or v.get("look"))}
    return set(data.en.get("characters") or {}) | set(data.en.get("members") or {}) | sup


def _check_place(data: Data, location: str, variant: str | None, where: str) -> list[str]:
    locs = data.en.get("locations") or {}
    if location not in locs:
        return [f"{where}: локації «{location}» немає в prompt_en.yaml"]
    variants = locs[location].get("variants") or {}
    if variant and variant not in variants:
        return [f"{where}: у локації «{location}» немає стану «{variant}» (є: {', '.join(map(str, variants)) or '—'})"]
    return []


def _check_people(data: Data, people: list[Person], where: str) -> list[str]:
    known = _known(data)
    ids = [p.id for p in people]
    bad = [pid for pid in ids if pid not in known and pid not in data.groups]
    bad += [m for pid in ids for m in data.groups.get(pid, []) if m not in known]
    return [f"{where}: невідомий персонаж «{pid}» (немає в prompt_en.yaml characters / members / supporting з tag "
            f"і в групах біблії)" for pid in dict.fromkeys(bad)] + [
        f"{where}: «{pid}» у people двічі — залиш один запис" for pid in dict.fromkeys(ids) if ids.count(pid) > 1]


def _check_states(data: Data, people: list[Person], where: str) -> list[str]:
    states = data.en.get("states")
    if states is None:                        # старий prompt_en без states — перевіряти нема з чим
        return []
    return [f"{where}: невідомий стан «{s}» у {p.id} (є в prompt_en.yaml states: {', '.join(map(str, states)) or '—'})"
            for p in people for s in p.state if s not in states]


# ---------------------------------------------------------------- частина


def _scene_aliases(scene_id: str) -> set[str]:
    """s04 ↔ «4» / «04»: в оверлеї сцену можна назвати номером біта."""
    m = re.fullmatch(r"s(\d+)", scene_id)
    return {scene_id} | ({m.group(1), str(int(m.group(1)))} if m else set())


def _pick(shot: BaseModel, scene: BaseModel, field: str) -> object:
    """Значення шоту, якщо його задано (навіть null), інакше — сцени."""
    return getattr(shot, field) if field in shot.model_fields_set else getattr(scene, field)


def _sound(scene: Sound | None, shot: Sound | None) -> Sound:
    scene, shot = scene or Sound(), shot or Sound()
    return Sound(**{f: getattr(shot if f in shot.model_fields_set else scene, f) for f in Sound.model_fields})


# поля оверлею, що не діють, коли шот лише кадр (still) або не генерується (none)
IGNORED = {"still": ("mode", "end_frame", "action", "end_state", "window", "event_s", "clips", "handoff"),
           "none": ("mode", "frame", "end_frame", "action", "end_state", "camera", "face", "window", "event_s",
                    "clips", "handoff")}


def _part_spec(data: Data, part: int, sh: Shot, en: ShotIn | None, scene: SceneIn | None,
               delivery: dict[str, str], name: str) -> tuple[ShotSpec | None, list[str]]:
    where = f"{name} · шот {sh.id}"
    o, sc = en or ShotIn(), scene or SceneIn()
    mode = derive_mode(sh.tier, sh.reuse, o.mode)
    generated, video = mode != "none", mode in VIDEO_MODES
    warnings: list[str] = []
    if ignored := [f for f in IGNORED.get(mode, ()) if getattr(o, f) not in (None, "", [], "cut")]:
        warnings.append(f"{', '.join(ignored)} з оверлею не {'діє' if len(ignored) == 1 else 'діють'}: шот "
                        f"{'still (лише кадр)' if mode == 'still' else 'не генерується'}")
    location = o.location or sh.location_id or ""
    variant = _pick(o, sc, "variant")
    errors = []
    if generated and not location:
        errors.append(f"{where}: шот генерується, але без локації — додай location в оверлей або location_id "
                      "у розкадровку")
    elif generated:                           # плиту не генеруємо — і місце не перевіряємо
        errors += _check_place(data, location, variant, where)
    if o.people is None:
        known = [c for c in sh.characters if c in _known(data) or c in data.groups]
        if generated:
            warnings += [f"персонаж «{c}» без опису в prompt_en.yaml — його немає в people (опиши у frame)"
                         for c in sh.characters if c not in known]
        entries = [Person(id=c) for c in known]
    else:
        entries = o.people
        errors += _check_people(data, entries, where)
    errors += _check_states(data, entries, where)             # стан сцени перевіряє part_specs — один раз
    people = expand_people(entries, data.groups, sc.state)
    bad = sorted(n for n in o.lines if not 1 <= n <= len(sh.dialogue))
    if bad:
        errors.append(f"{where}: lines {bad} — у шоті {len(sh.dialogue)} реплік(и), нумерація з 1")
    if errors:
        return None, errors

    size = SIZES.get(sh.framing or "")
    if o.camera is not None and generated:
        camera = o.camera if o.camera.size else o.camera.model_copy(update={"size": size})
    elif en is None and generated and sh.camera:
        camera = Camera(size=size, text=f"{UA} {sh.camera}")
    else:
        camera = Camera(size=size)
    frame, action = (o.frame or "") if generated else "", (o.action or "") if video else ""
    if generated:
        if en is None:
            warnings.append(f"немає англійського опису шоту в {name} — у промпті український текст")
        elif not frame:
            warnings.append(f"немає frame (стартовий кадр) у {name} — у промпті український текст")
        if en is not None and not action and video:
            warnings.append(f"немає action у {name} — у промпті український текст")
        if o.people == [] and sh.characters and o.face is None:
            warnings.append(f"people порожній, а в shots.json є {', '.join(sh.characters)}: face=none → Replicate; "
                            "задай people з view або face")
        frame = frame or f"{UA} {sh.action}"
        action = action or (f"{UA} {sh.action}" if video else "")
    light, time = _pick(o, sc, "light"), _pick(o, sc, "time")
    time, tw = _time(data, location, variant, time, light) if generated else (time, [])
    lines, lw = derive_lines(sh, people, delivery, o.lines)
    speaks = any(ln.on_screen for ln in lines)     # рот у кадрі → маршрут з обличчям (§6.2 п.4)
    face = (o.face if generated else None) or ("clear" if speaks else derive_face(people, camera))
    if speaks and face != "clear":
        warnings.append(f"face «{face}» з оверлею, а репліка on_screen — потрібен маршрут з обличчям (face clear)")
    return ShotSpec(
        id=sh.id, set=str(part), title=f"Ч.{part} · {sh.id}", scene_id=sh.scene_id, tier=sh.tier, beat=o.beat,
        mode=mode, edit_s=sh.duration_s, gen_s=gen_seconds(sh.duration_s) if video else 0,
        location=location, variant=variant, light=light, time=time,
        footage=sh.footage if sh.footage in ("vhs", "phone") else None, frame=frame,
        end_frame=o.end_frame if mode == "first_last" else None, action=action,
        end_state=o.end_state if video else None, camera=camera, sound=_sound(sc.sound, o.sound), people=people,
        lines=lines, face=face, continuity=_union(sc.continuity, o.continuity), success=o.success, notes=o.notes,
        window=o.window if video else None, event_s=o.event_s if video else None, clips=o.clips if video else [],
        handoff=o.handoff if video else "cut", warnings=warnings + tw + lw), []


def part_specs(data: Data, part: int, out_root: Path | None = None, overlay: Path | None = None) -> list[ShotSpec]:
    """Спеки всіх шотів частини в порядку shots.json (montage / reuse — mode none, але з репліками).

    out_root=None → prompts.OUTPUT на момент виклику; overlay=None → series/<slug>/part<N>_prompts_en.yaml.
    """
    from fabrica import prompts                # prompts імпортує цей модуль — лише тут

    folder = (out_root or prompts.OUTPUT) / data.slug / f"part{part}"
    shots_path, script_path = folder / "shots.json", folder / "script.json"
    if not shots_path.exists():
        raise SpecError(f"немає {shots_path.as_posix()} — спершу `fabrica shotlist {data.slug} {part}`")
    docs = {}
    for path, model in ((shots_path, Shots), (script_path, Script)):
        if path.exists():
            try:
                docs[path.name] = model.model_validate_json(path.read_text(encoding="utf-8-sig"))
            except ValidationError as e:
                raise SpecError("\n".join(f"{path.name}: {_why(err)}" for err in e.errors(include_url=False))) from None
    shots, script = docs["shots.json"], docs.get("script.json")
    # манера зі script.json; normal там = «не задано» (derive_lines тоді бере оверлей)
    delivery = {ln.id: ln.delivery for sc in (script.scenes if script else []) for ln in sc.lines}
    ov = load_overlay(data.slug, part, overlay)
    name = (ov.get("path") or overlay or overlay_path(data.slug, part)).name
    scenes_ov, shots_ov = ov.get("scenes", {}), ov.get("shots", {})
    ids = {sh.id for sh in shots.shots}
    errors = [f"{name} · шот {k}: такого шоту немає в shots.json частини {part}" for k in shots_ov if k not in ids]
    aliases = {sid: _scene_aliases(sid) for sid in {sh.scene_id for sh in shots.shots}}
    errors += [f"{name} · сцена {k}: такої сцени немає в shots.json частини {part} (є: "
               f"{', '.join(sorted(aliases))})" for k in scenes_ov if not any(k in a for a in aliases.values())]
    for sid, keys in sorted(aliases.items()):
        if len(found := sorted(k for k in keys if k in scenes_ov)) > 1:
            errors.append(f"{name}: сцена {sid} задана двічі ({', '.join(found)}) — залиш один ключ")
    for k, sc in scenes_ov.items():
        errors += _check_people(data, [Person(id=pid) for pid in sc.state], f"{name} · сцена {k} · state")
        errors += _check_states(data, [Person(id=pid, state=st) for pid, st in sc.state.items()],
                                f"{name} · сцена {k}")
    specs = []
    for sh in shots.shots:
        scene = next((scenes_ov[k] for k in sorted(aliases[sh.scene_id]) if k in scenes_ov), None)
        spec, errs = _part_spec(data, part, sh, shots_ov.get(sh.id), scene, delivery, name)
        errors += errs
        if spec:
            specs.append(spec)
    if errors:
        raise SpecError("\n".join(errors))
    return specs


# ---------------------------------------------------------------- тест-пак


def test_pack_path(slug: str) -> Path:
    return bible_mod.SERIES / slug / "lab" / "test_pack.yaml"


def _tp_spec(data: Data, sid: str, title: str, f: TPFrame, v: TPVideo | None, success: list[str],
             where: str) -> tuple[ShotSpec | None, list[str]]:
    errors = _check_place(data, f.location, f.variant, where) + _check_people(data, f.people, where)
    errors += _check_states(data, f.people, where)
    mode = v.mode if v else "still"
    end_frame = (v.end_frame if v else None) or f.end_frame
    if mode == "first_last" and not end_frame:
        errors.append(f"{where}: mode first_last потребує end_frame (композиція останньої миті)")
    if end_frame and mode != "first_last":
        errors.append(f"{where}: end_frame лише для mode first_last")
    # одне значення — в одному місці: друге мовчки губилося б
    if v and f.light and v.light and f.light != v.light:
        errors.append(f"{where}: light і в frame, і у videos — у спеки одне світло, залиш одне")
    if v and v.tier and v.resolution and TIER_RES[v.tier] != v.resolution:
        errors.append(f"{where}: tier {v.tier} — це {TIER_RES[v.tier]}, а resolution {v.resolution}; залиш одне")
    if f.framing and f.camera and f.camera.size:
        errors.append(f"{where}: framing і camera.size разом — залиш camera.size (framing — старий ключ)")
    cam = f.camera.model_dump(exclude_unset=True) if f.camera else {}
    if f.framing and "size" not in cam:
        cam["size"] = f.framing.lower()
    if v and v.camera:
        vcam = v.camera.model_dump(exclude_unset=True)
        if cam.get("size") and vcam.get("size") and cam["size"].lower() != vcam["size"].lower():
            errors.append(f"{where}: розмір кадру «{cam['size']}» у frame і «{vcam['size']}» у videos.camera — "
                          "задай один")
        cam |= vcam
    camera, errs = _validate(Camera, cam, f"{where} · camera (frame + videos)")
    errors += errs
    if errors:
        return None, errors
    people = expand_people(f.people, data.groups)
    tier = "still" if v is None else v.tier or ("hero" if v.resolution == "720p" else
                                                "found_footage" if f.footage else "secondary")
    light = f.light or (v.light if v else None)
    time, tw = _time(data, f.location, f.variant, f.time, light)
    face = (v.face if v else None) or f.face or derive_face(people, camera)
    return ShotSpec(
        id=sid, set="test-pack", title=title, scene_id=None, tier=tier, beat=(v.beat if v else None) or f.beat,
        mode=mode, edit_s=v.duration_s if v else 0.0, gen_s=gen_seconds(v.duration_s) if v else 0,
        location=f.location, variant=f.variant, light=light, time=time, footage=f.footage,
        frame=f.frame or f.composition or "", end_frame=end_frame, action=v.action if v else "",
        end_state=v.end_state if v else None, camera=camera, sound=v.sound if v else Sound(), people=people,
        lines=[], face=face, video_id=v.id if v else "video", continuity=f.continuity, success=success,
        notes=f.notes + (v.notes if v else []), warnings=tw), []


def test_pack_specs(data: Data, path: Path | None = None) -> list[ShotSpec]:
    """series/<slug>/lab/test_pack.yaml → ShotSpec: тест = кадр + (одне) відео; extra_frames — окремі спеки.

    Старий формат (composition, framing, рядок camera, people — id або {id, state}) і нові ключі (frame, camera —
    словник, end_state, sound, people з view / screen, mode, tier) читаються однаково.
    """
    path = path or test_pack_path(data.slug)
    if not path.exists():
        raise SpecError(f"немає {path.as_posix()} — тест-паку")
    raw = _read_yaml(path)
    name = path.name
    if not isinstance(raw, dict) or not isinstance(raw.get("tests"), list):
        raise SpecError(f"{name}: очікую словник з tests: [список тестів]")
    extra = sorted(set(raw) - {"tests", "version"}, key=str)
    errors = [f"{name}: зайві ключі верхнього рівня {extra} (є tests, version)"] if extra else []
    specs: list[ShotSpec] = []
    seen: set[str] = set()
    for i, body in enumerate(raw["tests"], 1):
        tid = body.get("id", f"#{i}") if isinstance(body, dict) else f"#{i}"
        t, errs = _validate(TPTest, body, f"{name} · тест {tid}")
        errors += errs
        if t is None:
            continue
        units = [(t.id, f"{t.id} · {t.title}", t.frame, t.videos)]
        units += [(f"{t.id}-{ef.id}", f"{t.id} · {t.title} ({ef.id})", ef, ef.videos) for ef in t.extra_frames]
        for sid, title, f, videos in units:
            if sid in seen:
                errors.append(f"{name} · тест {sid}: id повторюється")
                continue
            seen.add(sid)
            spec, errs = _tp_spec(data, sid, title, f, videos[0] if videos else None, t.success,
                                  f"{name} · тест {sid}")
            errors += errs
            if spec:
                specs.append(spec)
    if errors:
        raise SpecError("\n".join(errors))
    return specs
