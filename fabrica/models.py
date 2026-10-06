"""Схеми JSON між етапами: script.json (етап script) і shots.json (етап shots).

Одна частина історії = один script.json і один shots.json. Мітки бітів — docs/PLAYBOOK.md → «Мітки бітів».

Два рівні перевірки:
- **модель** (Script / Shots) — структура: типи, діапазони, унікальні ID. Невалідний JSON не завантажиться;
- **редакторські правила** — список помилок, порожній = гаразд. Список зручно віддати LLM на виправлення:
  script_errors / shots_errors — мітки, тизери 30–40 с, скрімери (PLAYBOOK);
  check_refs — ID персонажів, локацій і підказок існують у біблії;
  check_shots — shots.json покриває script.json (сцени, репліки, мітки).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

if TYPE_CHECKING:
    from fabrica.bible import Bible

SCHEMA_VERSION = 1

Segment = Literal["main", "title", "recap", "end_card"]
FILM_EXCLUDE = frozenset({"recap", "end_card"})          # фільм: без «Anteriormente en…» і «Continuará…»
TEASER_SKIP = frozenset({"title", "recap", "end_card"})  # тизер перестрибує ці сегменти

LabelName = Literal["HOOK_OPEN", "MIDPOINT", "SCREAMER", "TEASER_START", "TEASER_CUT_BEFORE", "CLIFF"]
TEASER_SECONDS = (30.0, 40.0)
SCRIPT_TOLERANCE_S = 5.0     # у script час орієнтовний (~0:33), точно тизер міряємо в shots
SCREAMER_SECONDS = (0.5, 2.0)
SHOT_MIN_SECONDS = 1.0       # звичайний шот; коротші — лише SCREAMER
SCREAMER_BUILDUP_S = (3.0, 10.0)  # тиша або наростання за 3–10 с до скрімера

# Tier шота: що і в якій якості генеруємо (part1_shotlist.md → «Tier»)
Tier = Literal["hero", "secondary", "found_footage", "still", "montage"]
GENERATED_TIERS = frozenset({"hero", "secondary", "found_footage"})   # платне відео (Seedance)

Id = Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
ShotId = Annotated[str, Field(pattern=r"^[a-z0-9_.]+$")]       # «1.07» з розкадровки теж годиться
Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$")]
ClueId = Annotated[str, Field(pattern=r"^(C\d{2}|F\d+)$")]   # C01 — підказка, F1 — хибний слід
# Перевикористання: shot:<id> — готовий кадр іншого шота; plate:<location_id> — плита локації;
# asset:<slug> — інший готовий матеріал (реквізит-стіл з кастингу тощо)
Reuse = Annotated[str, Field(pattern=r"^(shot:[a-z0-9_.]+|plate:[a-z0-9_]+|asset:[a-z0-9_]+)$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Label(_Strict):
    """Мітка біта. В одному біті їх може бути кілька (SCREAMER + TEASER_CUT_BEFORE + CLIFF)."""

    label: LabelName
    n: int | None = Field(None, ge=1, description="номер тизера; лише для TEASER_*")
    approx_s: float | None = Field(
        None, ge=0, description="script: ~секунда від початку частини; у shots мітка стоїть на початку шота")
    line_id: Id | None = Field(None, description="репліка, до якої прив'язана мітка")
    moment: str | None = Field(None, description="момент дії, якщо мітка не на репліці")

    @model_validator(mode="after")
    def _teaser_n(self) -> Label:
        if self.label.startswith("TEASER_") != (self.n is not None):
            raise ValueError(f"{self.label}: n потрібен для TEASER_START / TEASER_CUT_BEFORE і лише для них")
        return self

    @property
    def key(self) -> str:
        """Назва як у story.md: TEASER1_START, CLIFF, …"""
        return f"TEASER{self.n}_{self.label.removeprefix('TEASER_')}" if self.n else self.label


class Line(_Strict):
    id: Id
    character_id: Id
    text_es: str = Field(min_length=1)
    delivery: Literal["normal", "whisper", "shout", "scream"] = "normal"
    emotion: str | None = None
    offscreen: bool = Field(False, description="голос за кадром: телевізор, рація, VHS")


class Clues(_Strict):
    planted: list[ClueId] = []
    revealed: list[ClueId] = []


Footage = Literal["camera", "phone", "vhs"]


class Scene(_Strict):
    """Сцена = біт зі story.md."""

    id: Id
    segment: Segment = "main"
    approx_start_s: float = Field(ge=0)
    approx_end_s: float = Field(gt=0)
    location_id: Id | None = Field(None, description="None — картка (title/recap/end_card) або монтаж")
    characters: list[Id] = []
    action: str
    footage: Footage = "camera"
    wow: bool = Field(False, description="[ВАУ] — фізика сили")
    vfx: str | None = Field(None, description="телекінез за bible.rules.telekinesis")
    overlay_text: str | None = Field(None, description="текст, що накладає assemble («LA GARGANTA», «Continuará…»)")
    lines: list[Line] = []
    labels: list[Label] = []
    clues: Clues = Clues()

    @model_validator(mode="after")
    def _check(self) -> Scene:
        if self.approx_end_s <= self.approx_start_s:
            raise ValueError(f"{self.id}: approx_end_s має бути більшим за approx_start_s")
        line_ids = {ln.id for ln in self.lines}
        for lb in self.labels:
            if lb.line_id and lb.line_id not in line_ids:
                raise ValueError(f"{self.id}: мітка {lb.key} посилається на чужу репліку {lb.line_id}")
            if lb.approx_s is not None and not self.approx_start_s <= lb.approx_s <= self.approx_end_s:
                raise ValueError(f"{self.id}: мітка {lb.key} ({lb.approx_s} с) поза межами сцени")
        return self


class Script(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    story: Slug
    part: int = Field(ge=1, le=4)
    title_es: str
    target_seconds: int = Field(ge=360, le=480)
    scenes: list[Scene] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Script:
        _unique("сцен", [s.id for s in self.scenes])
        _unique("реплік", [ln.id for s in self.scenes for ln in s.lines])
        for a, b in zip(self.scenes, self.scenes[1:]):
            if b.approx_start_s < a.approx_start_s:
                raise ValueError(f"сцени не за часом: {b.id} раніше за {a.id}")
        return self


def script_errors(script: Script) -> list[str]:
    """Правила міток PLAYBOOK для script.json (час орієнтовний — тизер з допуском)."""
    units = [Unit(s.segment, s.approx_start_s, s.approx_end_s, i) for i, s in enumerate(script.scenes)]
    marks = [Mark(lb.key, i, lb.approx_s, lb.approx_s) if lb.approx_s is not None
             else Mark(lb.key, i, s.approx_start_s, s.approx_end_s)
             for i, s in enumerate(script.scenes) for lb in s.labels]
    return label_errors(units, marks, tolerance=SCRIPT_TOLERANCE_S)


# ---------------------------------------------------------------- shots.json


class Sfx(_Strict):
    type: Literal["sting", "silence", "riser", "ambience"]
    at_s: float = Field(ge=0, description="від початку шота")


class Dialogue(_Strict):
    """Репліка, що звучить у шоті. line_id — посилання на script.json, якщо репліка звідти."""

    text_es: str = Field(min_length=1)
    character_id: Id | None = None
    line_id: Id | None = None
    offscreen: bool = False


class Shot(_Strict):
    id: ShotId
    scene_id: Id
    segment: Segment = "main"
    duration_s: float = Field(ge=SCREAMER_SECONDS[0], le=10)
    tier: Tier
    location_id: Id | None = None
    characters: list[Id] = []
    framing: Literal["extreme_wide", "wide", "medium_wide", "medium", "medium_close", "close_up",
                     "insert"] | None = None
    camera: str = Field("", description="ракурс і рух камери, як у розкадровці")
    action: str = Field(description="що відбувається в кадрі")
    prompt_video: str = Field("", description="промпт для відеомоделі; порожній для still / montage")
    footage: Footage = "camera"
    dialogue: list[Dialogue] = []
    has_dialogue_visible: bool = Field(False, description="рот того, хто говорить, у кадрі → lip-sync")
    sfx: list[Sfx] = []
    labels: list[Label] = []
    clues: Clues = Clues()
    reuse: Reuse | None = Field(None, description="шот не генеруємо — беремо готовий матеріал")
    reuse_note: str | None = Field(None, description="перевикористання як у розкадровці («→ ч.3», «7.01 на ТБ»)")
    billed_seconds: float | None = Field(
        None, ge=0, description="оплачувані секунди генерації; None — рахувати з duration_s і tier")
    subject_x: float = Field(0.5, ge=0, le=1, description="центр героя по горизонталі — для reframe у 9:16")
    overlay_text: str | None = None
    notes: list[str] = []

    @computed_field
    @property
    def film_exclude(self) -> bool:
        return self.segment in FILM_EXCLUDE

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: object) -> object:
        """film_exclude є в записаному shots.json; при читанні він лише має збігатися з segment."""
        if isinstance(data, dict) and "film_exclude" in data:
            data = dict(data)
            given = data.pop("film_exclude")
            if given != (data.get("segment", "main") in FILM_EXCLUDE):
                raise ValueError(f"{data.get('id')}: film_exclude={given} не відповідає segment={data.get('segment')}")
        return data

    @property
    def generated(self) -> bool:
        """Платна генерація відео: hero / secondary / found_footage і не перевикористання."""
        return self.tier in GENERATED_TIERS and self.reuse is None

    @property
    def billable_seconds(self) -> float:
        if self.billed_seconds is not None:
            return self.billed_seconds
        return self.duration_s if self.generated else 0.0

    @model_validator(mode="after")
    def _check(self) -> Shot:
        for fx in self.sfx:
            if fx.at_s > self.duration_s:
                raise ValueError(f"{self.id}: sfx {fx.type} на {fx.at_s} с — після кінця шота")
        if self.billed_seconds and not self.generated:
            raise ValueError(f"{self.id}: billed_seconds > 0, але шот не генерується ({self.tier}, reuse={self.reuse})")
        if self.has_dialogue_visible and not self.dialogue:
            raise ValueError(f"{self.id}: has_dialogue_visible без реплік")
        return self


class Shots(_Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    story: Slug
    part: int = Field(ge=1, le=4)
    shots: list[Shot] = Field(min_length=1)

    def starts(self) -> list[float]:
        """Секунда початку кожного шота від початку частини."""
        out, t = [], 0.0
        for sh in self.shots:
            out.append(t)
            t += sh.duration_s
        return out

    @model_validator(mode="after")
    def _check(self) -> Shots:
        _unique("шотів", [sh.id for sh in self.shots])
        return self


def shots_errors(shots: Shots) -> list[str]:
    """Правила PLAYBOOK для shots.json: мітки, точні тизери по межах шотів, скрімери."""
    starts = shots.starts()
    order: dict[str, int] = {}
    for sh in shots.shots:
        order.setdefault(sh.scene_id, len(order))
    units = [Unit(sh.segment, t, t + sh.duration_s, order[sh.scene_id]) for sh, t in zip(shots.shots, starts)]
    # тизер ріжемо по межах шотів: START і CUT_BEFORE — початок шота
    marks = [Mark(lb.key, i, t, t) for i, (sh, t) in enumerate(zip(shots.shots, starts)) for lb in sh.labels]
    errors = label_errors(units, marks, tolerance=0.0)

    s_lo, s_hi = SCREAMER_SECONDS
    b_lo, b_hi = SCREAMER_BUILDUP_S
    buildup = [t + fx.at_s for sh, t in zip(shots.shots, starts) for fx in sh.sfx if fx.type in ("silence", "riser")]
    for sh, t in zip(shots.shots, starts):
        if any(lb.label == "SCREAMER" for lb in sh.labels):
            if not s_lo <= sh.duration_s <= s_hi:
                errors.append(f"{sh.id}: SCREAMER-шот має тривати {s_lo:g}–{s_hi:g} с, а не {sh.duration_s:g}")
            if not any(fx.type == "sting" for fx in sh.sfx):
                errors.append(f"{sh.id}: SCREAMER без звукового удару (sfx sting)")
            if not any(t - b_hi <= b <= t - b_lo for b in buildup):
                errors.append(f"{sh.id}: перед SCREAMER потрібна тиша або наростання (sfx silence/riser) "
                              f"за {b_lo:g}–{b_hi:g} с")
        elif sh.duration_s < SHOT_MIN_SECONDS:
            errors.append(f"{sh.id}: шот коротший за {SHOT_MIN_SECONDS:g} с дозволено лише для SCREAMER")
    return errors


# ---------------------------------------------------------------- правила міток


@dataclass(frozen=True)
class Unit:
    """Сцена або шот на часовій осі частини. group — порядковий номер сцени (біта)."""

    segment: str
    start: float
    end: float
    group: int


@dataclass(frozen=True)
class Mark:
    """Мітка на осі: [lo, hi] — де вона може бути (lo == hi, якщо час відомий)."""

    key: str
    unit: int
    lo: float | None
    hi: float | None


def teaser_seconds(units: list[Unit], start: float, cut: float) -> float:
    """Тривалість тизера від start до cut без сегментів, які тизер перестрибує (рекап, картки)."""
    skipped = sum(max(0.0, min(u.end, cut) - max(u.start, start)) for u in units if u.segment in TEASER_SKIP)
    return cut - start - skipped


def label_errors(units: list[Unit], marks: list[Mark], tolerance: float) -> list[str]:
    """Правила PLAYBOOK для однієї частини. Спільні для story.md, script і shots."""
    errors: list[str] = []
    count = Counter(m.key for m in marks)
    for key in ("HOOK_OPEN", "MIDPOINT", "CLIFF"):
        if count[key] != 1:
            errors.append(f"{key}: має бути рівно один на частину, а є {count[key]}")
    if count["SCREAMER"] > 2:
        errors.append(f"SCREAMER: не більше 2 на частину, а є {count['SCREAMER']}")

    for m in marks:
        if units[m.unit].segment != "main":
            errors.append(f"{m.key}: мітка в сегменті {units[m.unit].segment}, а має бути в main")
    last_main = max((u.group for u in units if u.segment == "main"), default=None)
    for m in marks:
        if m.key == "HOOK_OPEN" and units[m.unit].group != units[0].group:
            errors.append("HOOK_OPEN: має бути в першому біті, до рекапу й назви")
        if m.key == "CLIFF" and units[m.unit].group != last_main:
            errors.append("CLIFF: має бути в останньому біті частини (перед «Continuará…»)")

    teasers: dict[int, dict[str, list[Mark]]] = {}
    for m in marks:
        if m.key.startswith("TEASER"):
            n, kind = m.key.removeprefix("TEASER").split("_", 1)
            teasers.setdefault(int(n), {}).setdefault(kind, []).append(m)
    if sorted(teasers) != list(range(1, len(teasers) + 1)):
        errors.append(f"тизери мають іти по порядку з 1, а є {sorted(teasers)}")
    lo_s, hi_s = TEASER_SECONDS
    for n, kinds in sorted(teasers.items()):
        starts, cuts = kinds.get("START", []), kinds.get("CUT_BEFORE", [])
        if len(starts) != 1 or len(cuts) != 1:
            errors.append(f"TEASER{n}: потрібна рівно одна пара START + CUT_BEFORE, "
                          f"а є {len(starts)} START і {len(cuts)} CUT_BEFORE")
            continue
        s, c = starts[0], cuts[0]
        if s.lo != s.hi or c.lo != c.hi or s.lo is None or c.lo is None:
            errors.append(f"TEASER{n}: для START і CUT_BEFORE потрібен час (approx_s)")
            continue
        if c.lo <= s.lo:
            errors.append(f"TEASER{n}: CUT_BEFORE має бути після START")
            continue
        sec = teaser_seconds(units, s.lo, c.lo)
        if not lo_s - tolerance <= sec <= hi_s + tolerance:
            errors.append(f"TEASER{n}: {sec:g} с, а має бути {lo_s:g}–{hi_s:g}"
                          + (f" (±{tolerance:g} — час у script орієнтовний)" if tolerance else ""))
        for m in marks:
            if m.key == "SCREAMER" and m.lo is not None and s.lo < m.lo and m.hi < c.lo:
                errors.append(f"TEASER{n}: містить SCREAMER — тизер має обриватися ДО скрімера")
    return errors


# ---------------------------------------------------------------- перевірки з біблією і між етапами


def check_refs(doc: Script | Shots, bible: Bible) -> list[str]:
    """ID персонажів, локацій і підказок зі script.json / shots.json мають існувати в bible.yaml / clues.md."""
    errors = []
    if doc.story != bible.slug:
        errors.append(f"story «{doc.story}» ≠ біблія «{bible.slug}»")
    people = bible.character_ids | bible.supporting_ids
    items = doc.scenes if isinstance(doc, Script) else doc.shots
    for it in items:
        if it.location_id and it.location_id not in bible.location_ids:
            errors.append(f"{it.id}: невідома локація {it.location_id}")
        speakers = [ln.character_id for ln in it.lines] if isinstance(it, Scene) else \
            [d.character_id for d in it.dialogue if d.character_id]
        for c in [*it.characters, *speakers]:
            if c not in people:
                errors.append(f"{it.id}: невідомий персонаж {c}")
        for clue in it.clues.planted + it.clues.revealed:
            if clue not in bible.clue_ids:
                errors.append(f"{it.id}: невідома підказка {clue} (немає в clues.md)")
    return errors


def check_shots(shots: Shots, script: Script) -> list[str]:
    """shots.json має покривати script.json: ті самі сцени по порядку, усі репліки, ті самі мітки."""
    errors = []
    if (shots.story, shots.part) != (script.story, script.part):
        errors.append(f"shots для {shots.story} ч.{shots.part}, а script — {script.story} ч.{script.part}")
    scenes = {s.id: (i, s) for i, s in enumerate(script.scenes)}
    last = -1
    for sh in shots.shots:
        if sh.scene_id not in scenes:
            errors.append(f"{sh.id}: невідома сцена {sh.scene_id}")
            continue
        i, scene = scenes[sh.scene_id]
        if i < last:
            errors.append(f"{sh.id}: сцена {sh.scene_id} після пізнішої — шоти не по порядку")
        last = max(last, i)
        if sh.segment != scene.segment:
            errors.append(f"{sh.id}: сегмент {sh.segment}, а в сцени {scene.id} — {scene.segment}")
        own = {ln.id for ln in scene.lines}
        errors += [f"{sh.id}: репліка {d.line_id} не з сцени {scene.id}"
                   for d in sh.dialogue if d.line_id and d.line_id not in own]
    covered = {d.line_id for sh in shots.shots for d in sh.dialogue}
    errors += [f"репліка {ln.id} ({s.id}) «{ln.text_es}» не потрапила в жоден шот"
               for s in script.scenes for ln in s.lines if ln.id not in covered]
    want = Counter(lb.key for s in script.scenes for lb in s.labels)
    got = Counter(lb.key for sh in shots.shots for lb in sh.labels)
    if want != got:
        errors.append(f"мітки shots ≠ script: бракує {dict(want - got)}, зайві {dict(got - want)}")
    return errors


def _unique(what: str, ids: list[str]) -> None:
    dup = [i for i, k in Counter(ids).items() if k > 1]
    if dup:
        raise ValueError(f"повторюються ID {what}: {dup}")
