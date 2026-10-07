"""Лабораторія промптів: шаблони prompts/templates/ + біблія + шот-спеки → пакет промптів для ручних тестів.

Кожен елемент пакета — рівно те, що отримає API: маршрут («<провайдер>:<модель>», prompts/providers.yaml),
payload (тіло запиту; файли — «ref:<id референсу>»), слоти референсів і порядок виробництва (STEPS). Промпти
компілює fabrica/compile.py зі структурованих даних (prompt_en.yaml, шот-спека fabrica/shotspec.py). Люди
тестують руками (dropshot AI Studio, AI Studio / Gemini, Replicate, ElevenLabs), пишуть результат у журнал
(`fabrica lab log`) і затверджують golden (`fabrica lab approve`). Автоматика бере лише golden.

Набори:
    casting    — обличчя-якорі, ракурси й емоції, сімка 1994 (+ мокрі), локації (плити й стани), голоси
    test-pack  — series/<slug>/lab/test_pack.yaml: стартові кадри + відео (кліпи)
    1 … 4      — частина: output/<slug>/part<N>/shots.json + series/<slug>/part<N>_prompts_en.yaml
Послідовність (series/<slug>/lab/sequences.yaml, напр. first30) — шоти частини + усе з кастингу, без чого
їх не зробити (sequence_items). Англійські описи — series/<slug>/prompt_en.yaml (той самий id, що в bible.yaml).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

import jinja2
import yaml

from fabrica import bible as bible_mod
from fabrica import config

TEMPLATES = config.ROOT / "prompts" / "templates"
OUT = config.ROOT / "prompts" / "out"
OUTPUT = config.ROOT / "output"
KINDS = ("image", "video", "voice")
SHA_SKIP = ("success", "manual", "edit_window", "state_in", "state_out")    # extra, що не входить у prompt_sha


class PromptError(ValueError):
    """Шаблон або дані для промпту зламані — повідомлення пояснює, що виправити."""


# ---------------------------------------------------------------- порядок виробництва


@dataclass(frozen=True)
class Step:
    n: int
    key: str
    title: str          # заголовок кроку
    todo: str           # що робить людина і що означає «готово»
    tool: str           # де


STEPS = (
    Step(1, "identity", "Обличчя-якорі",
         "Згенеруй якір лише текстом (без референсів), 2–3 спроби; найкращий запиши в журнал з оцінкою ≥ 4 і затверди "
         "(golden) — це обличчя героя для всіх наступних кадрів.",
         "Nano Banana Pro (AI Studio / dropshot / Replicate)"),
    Step(2, "views", "Ракурси, емоції, мокрі",
         "Прикріпи затверджений якір як Image 1 і згенеруй ракурс / емоцію / мокрий варіант; готово — обличчя, "
         "волосся й одяг збігаються з якорем.", "Nano Banana 2.1 (Replicate) або Pro"),
    Step(3, "locations", "Локації",
         "Порожня плита локації лише текстом; стан того самого місця — з плитою як Image 1. Готово — у кадрі нікого "
         "і жодних написів.", "Nano Banana 2.1 (Replicate) або Pro"),
    Step(4, "voices", "Голоси (Voice Design)",
         "Створи голос за описом, вибери найкраще прев'ю, збережи голос і впиши voice_id у bible.yaml.",
         "ElevenLabs Voice Design"),
    Step(5, "frames", "Стартові й кінцеві кадри",
         "Прикріпи референси строго в порядку слотів (Image 1 — локація, далі люди зліва направо) і згенеруй статичний "
         "кадр першої миті шоту. Готово — розстановка, ракурси й світло як в описі.", "Nano Banana 2.1 / Pro"),
    Step(6, "video", "Відео (кліпи)",
         "Завантаж затверджений стартовий кадр (кліп k ≥ 2 — останній кадр кліпу k-1), встав промпт і налаштування з "
         "картки. Готово — одна безперервна дія без склейок, обличчя й одяг як на кадрі.",
         "dropshot AI Studio (Seedance 2.5) / Replicate / Cloudflare"),
    Step(7, "lines", "Репліки (озвучка)",
         "Озвуч репліку затвердженим голосом: текст із тегом і налаштування рівно з payload.",
         "ElevenLabs (eleven_v4)"),
)
STEP = {s.key: s.n for s in STEPS}


# ---------------------------------------------------------------- шаблони


@dataclass(frozen=True)
class Template:
    id: str
    kind: str
    version: int
    description: str
    params: dict
    prompt: str
    negative: str
    settings: dict
    path: Path
    sha: str               # хеш вмісту файлу: правка без нової версії ламає golden
    route: str = ""        # маршрут за замовчуванням (prompts/providers.yaml)
    profile: str = ""      # граматика моделі: seedance-2.5 | nano-banana | eleven_v4 | eleven_ttv_v3
    payload: dict = field(default_factory=dict)          # типові поля payload для всіх маршрутів
    route_payload: dict = field(default_factory=dict)    # {маршрут: додаткові поля} (напр. use_virtual_avatar)

    @property
    def ref(self) -> str:
        return f"{self.id}@v{self.version}"


def load_templates(root: Path = TEMPLATES) -> dict[str, Template]:
    out: dict[str, Template] = {}
    for path in sorted(root.rglob("*.yaml")):
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        data = yaml.safe_load(raw.decode("utf-8-sig"))
        tid, kind = data.get("id"), data.get("kind")
        if kind not in KINDS or not str(tid).startswith(f"{kind}."):
            raise PromptError(f"{path.name}: id «{tid}» має починатися з kind («{kind}.»), kind — image/video/voice")
        if not isinstance(data.get("version"), int) or data["version"] < 1:
            raise PromptError(f"{path.name}: version має бути цілим ≥ 1")
        if tid in out:
            raise PromptError(f"{path.name}: id «{tid}» уже є в {out[tid].path.name}")
        rp = data.get("route_payload") or {}
        if not isinstance(data.get("payload") or {}, dict) or not isinstance(rp, dict) \
                or not all(isinstance(v, dict) for v in rp.values()):
            raise PromptError(f"{path.name}: payload — словник полів; route_payload — {{маршрут: словник полів}}")
        if not isinstance(data.get("route") or "", str):
            raise PromptError(f"{path.name}: route — рядок «<провайдер>:<модель>»")
        out[tid] = Template(tid, kind, data["version"], data.get("description", ""), data.get("params") or {},
                            data.get("prompt") or "", data.get("negative") or "", data.get("settings") or {},
                            path, hashlib.sha256(raw).hexdigest()[:12], data.get("route") or "",
                            data.get("profile") or "", data.get("payload") or {}, rp)
    return out


_ENV = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)
_ENV.filters["capfirst"] = lambda s: s[:1].upper() + s[1:] if s else s     # capitalize() псує решту рядка


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"([.;!?])(?=[A-Za-zÁÉÍÓÚÑáéíóúñ¡¿«\[])", r"\1 ", text)   # «ghost.plain» → «ghost. plain»; «.[0s-»
    text = re.sub(r"\.(\s+\.)+", ".", text)                              # «стан. .» → «стан.»
    return re.sub(r"(?<!\.)\.\.(?!\.)", ".", text)                        # «..» → «.», але «...» лишається


def render(t: Template, ctx: dict) -> tuple[str, str]:
    try:
        return _clean(_ENV.from_string(t.prompt).render(**ctx)), _clean(_ENV.from_string(t.negative).render(**ctx))
    except jinja2.UndefinedError as e:
        raise PromptError(f"шаблон {t.ref}: бракує даних — {e.message}") from None


def seed_for(item_id: str) -> int:
    """Стабільний сід для елемента: той самий у кожному пакеті й у автоматиці."""
    return int(hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:8], 16) % 2_147_483_647


# ---------------------------------------------------------------- елементи


@dataclass
class Item:
    id: str                 # cast-mateo-front, loc-mina-dawn, tp-T1-frame, p1-4.03-video, p1-4.03-video-2 …
    set: str
    kind: str
    title: str
    template: Template
    prompt: str
    negative: str
    params: dict
    refs: list[str] = field(default_factory=list)      # id референсів у порядку слотів payload (Image 1 …)
    produces: str | None = None                        # який референс дає цей елемент
    extra: dict = field(default_factory=dict)          # прев'ю голосу, критерії успіху, інструкції, вікно монтажу …
    warnings: list[str] = field(default_factory=list)  # дані + «lint: …» + «API: …»
    step: int = 0                                      # порядок виробництва (STEPS)
    route: str = ""                                    # «<провайдер>:<модель>» з prompts/providers.yaml
    payload: dict = field(default_factory=dict)        # тіло запиту до API; файли — «ref:<id референсу>»
    needs: list[str] = field(default_factory=list)     # референси, без яких елемент не зробити

    @property
    def prompt_sha(self) -> str:
        """Хеш того, що йде в API (промпт, payload, маршрут, референси, шаблон) + змістовні extra. Не входить те, що
        генерацію не змінює: поверхня (params.tool), вікно монтажу, стан для картки (state_in / state_out),
        інструкції, критерії успіху — інакше нове вікно монтажу ламало б golden уже оплаченого кліпу."""
        extra = {k: v for k, v in self.extra.items() if k not in SHA_SKIP}
        if isinstance(extra.get("clip"), dict):
            extra["clip"] = {k: v for k, v in extra["clip"].items() if k != "window"}
        payload = {"prompt": self.prompt, "negative": self.negative, "refs": self.refs, "template": self.template.ref,
                   "params": {k: v for k, v in self.params.items() if k != "tool"}, "route": self.route,
                   "payload": self.payload, "extra": extra}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- правки студії (overrides.yaml)

OVERRIDE_KEYS = ("shots", "scenes", "prompt_en")
_PENDING: ContextVar[dict[str, dict] | None] = ContextVar("pending_overrides", default=None)


def overrides_path(slug: str) -> Path:
    return bible_mod.SERIES / slug / "lab" / "overrides.yaml"


def deep_merge(base, over):
    """Словники — рекурсивно; списки й значення — заміна (prompt_en: characters.mateo.dna — увесь список)."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return copy.deepcopy(over)
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(base.get(k), v) if k in base else copy.deepcopy(v)
    return out


def merge_fields(base, over: dict) -> dict:
    """Шот / сцена: заміна поля цілком (camera, people …); lines — за номером репліки, поле в поле."""
    out = dict(base) if isinstance(base, dict) else {}
    for k, v in over.items():
        if k == "lines" and isinstance(v, dict) and isinstance(out.get(k), dict):
            lines = {_n(n): dict(x) if isinstance(x, dict) else x for n, x in out[k].items()}
            for n, x in v.items():
                lines[_n(n)] = {**lines.get(_n(n), {}), **x} if isinstance(x, dict) else x
            out[k] = lines
        else:
            out[k] = copy.deepcopy(v)
    return out


def _n(n):
    return int(n) if isinstance(n, str) and n.isdigit() else n


def merge_overrides(base: dict, patch: dict) -> dict:
    """Шар правок поверх шару: shots / scenes — merge_fields на шот; prompt_en — deep_merge."""
    out = {k: copy.deepcopy(base.get(k) or {}) for k in OVERRIDE_KEYS}
    for block in ("shots", "scenes"):
        for key, body in (patch.get(block) or {}).items():
            out[block][str(key)] = merge_fields(out[block].get(str(key)), body or {})
    out["prompt_en"] = deep_merge(out["prompt_en"], patch.get("prompt_en") or {})
    return out


def load_overrides(slug: str) -> dict:
    """series/<slug>/lab/overrides.yaml (правки студії, у Git) + правки «на пробу» (pending_overrides) →
    {shots, scenes, prompt_en}. Ключ шоту / сцени «1.02» — для будь-якої частини, «p1-1.02» — лише для частини 1
    (shotspec.part_specs). Файлу немає — порожньо."""
    path = overrides_path(slug)
    raw = {}
    if path.exists():
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        except yaml.YAMLError as e:
            raise PromptError(f"{path.name}: зламаний YAML — {e}") from None
    if not isinstance(raw, dict) or set(raw) - set(OVERRIDE_KEYS) \
            or not all(isinstance(raw.get(k) or {}, dict) for k in OVERRIDE_KEYS):
        raise PromptError(f"{path.name}: очікую словник із shots, scenes, prompt_en (кожен — словник)")
    bad = [f"{block}.{key}" for block in ("shots", "scenes") for key, body in (raw.get(block) or {}).items()
           if body is not None and not isinstance(body, dict)]
    if bad:
        raise PromptError(f"{path.name}: правка шоту / сцени має бути словником полів — не так у {', '.join(bad)}")
    out = merge_overrides({}, raw)
    pending = (_PENDING.get() or {}).get(slug)
    return merge_overrides(out, pending) if pending else out


@contextmanager
def pending_overrides(slug: str, patch: dict):
    """Правки «на пробу» (студія: пропозиція перед записом): Data й шот-спеки бачать їх поверх overrides.yaml.
    Лише в поточному потоці / контексті — інші запити студії їх не бачать."""
    token = _PENDING.set({**(_PENDING.get() or {}), slug: patch})
    try:
        yield
    finally:
        _PENDING.reset(token)


class Data:
    """Біблія (bible.yaml) + англійський шар (prompt_en.yaml) однієї історії + правки студії (overrides.yaml)."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.bible = bible_mod.load(slug).data
        path = bible_mod.SERIES / slug / "prompt_en.yaml"
        if not path.exists():
            raise PromptError(f"немає {path.relative_to(config.ROOT).as_posix()} — англійського шару для промптів")
        self.en = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        self.overrides = load_overrides(slug)
        if self.overrides["prompt_en"]:
            self.en = deep_merge(self.en, self.overrides["prompt_en"])
        self.characters = {c["id"]: c for c in self.bible.get("characters", [])}
        self.members = {m["id"]: m for s in self.bible.get("supporting", []) for m in s.get("members", [])}
        self.supporting = {s["id"]: s for s in self.bible.get("supporting", [])}
        self.groups = {g["id"]: g["members"] for g in self.bible.get("groups", [])}
        self.locations = {loc["id"]: loc for loc in self.bible.get("locations", [])}

    def loc(self, loc_id: str) -> dict:
        try:
            return self.en["locations"][loc_id]
        except KeyError:
            raise PromptError(f"prompt_en.yaml: немає локації «{loc_id}»") from None

    def place(self, loc_id: str, variant: str | None = None, light: str | None = None) -> dict:
        """Місце один раз (без подвоєння бази): desc — повний опис; base — плита; change — що змінює стан;
        replace — стан самодостатній (інше приміщення / ракурс); ref — батьківський референс стану; framing, time."""
        loc = self.loc(loc_id)
        v = (loc.get("variants") or {}).get(variant) if variant else None
        if variant and v is None:
            raise PromptError(f"prompt_en.yaml: у локації «{loc_id}» немає стану «{variant}»")
        v = v if isinstance(v, dict) else {"desc": v} if v else {}
        replace = bool(v.get("replace"))
        change = v.get("desc") or ""
        desc = change if replace else loc["base"] + (f"; {change}" if change else "")
        ref = v.get("ref") if replace else (v.get("ref") or f"{loc_id}.plate") if variant else None
        return {"desc": desc, "base": loc["base"], "change": change, "replace": replace, "ref": ref,
                "light": light or v.get("light") or loc["light"], "mood": v.get("mood") or loc.get("mood", ""),
                "framing": v.get("framing") or loc.get("framing") or "wide establishing shot",
                "plate_framing": loc.get("framing") or "wide establishing shot",
                "time": v.get("time") or (None if replace else loc.get("time"))}


# ---------------------------------------------------------------- набори


def casting_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    from fabrica import compile as compile_mod

    return (compile_mod.character_items(data, templates) + compile_mod.member_items(data, templates)
            + compile_mod.location_items(data, templates) + compile_mod.voice_design_items(data, templates))


def test_pack_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    from fabrica import compile as compile_mod
    from fabrica import shotspec

    return compile_mod.spec_items(shotspec.test_pack_specs(data), data, templates)


def part_items(data: Data, templates: dict[str, Template], part: int, out_root: Path | None = None) -> list[Item]:
    from fabrica import compile as compile_mod
    from fabrica import shotspec

    return compile_mod.spec_items(shotspec.part_specs(data, part, out_root), data, templates)


def by_step(items: list[Item]) -> list[Item]:
    """Порядок виробництва: (крок, порядок появи)."""
    return sorted(items, key=lambda i: i.step)


def select(items: list[Item], kinds: list[str] | None = None, only: str | None = None, where: str = "") -> list[Item]:
    """Фільтр --kind / --only (елемент, шот «4.03» чи префікс «tp-T1»)."""
    if kinds:
        items = [i for i in items if i.kind in kinds]
    if only:
        items = [i for i in items if i.id == only or i.id.startswith(f"{only}-") or f"-{only}-" in f"{i.id}-"]
        if not items:
            raise PromptError(f"у наборі «{where}» немає елемента «{only}»")
    return items


def build(slug: str, set_name: str, kinds: list[str] | None = None, only: str | None = None,
          out_root: Path | None = None, templates: dict[str, Template] | None = None) -> list[Item]:
    """out_root=None → prompts.OUTPUT на момент виклику (тести й --out підміняють). Порядок — за кроками."""
    templates = templates or load_templates()
    data = Data(slug)
    if set_name == "casting":
        items = casting_items(data, templates)
    elif set_name == "test-pack":
        items = test_pack_items(data, templates)
    elif set_name in {"1", "2", "3", "4"}:
        items = part_items(data, templates, int(set_name), out_root)
    else:
        raise PromptError(f"невідомий набір «{set_name}»: casting, test-pack або номер частини 1–4")
    return select(by_step(items), kinds, only, set_name)


# ---------------------------------------------------------------- послідовності


def sequences_path(slug: str) -> Path:
    return bible_mod.SERIES / slug / "lab" / "sequences.yaml"


def sequences(slug: str) -> dict[str, dict]:
    """series/<slug>/lab/sequences.yaml → {назва: {title, part, shots}}; файлу немає — {}."""
    path = sequences_path(slug)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    seqs = raw.get("sequences", raw) if isinstance(raw, dict) else None
    if not isinstance(seqs, dict):
        raise PromptError(f"{path.name}: очікую словник «назва: {{title, part, shots}}»")
    errors = []
    for name, s in seqs.items():
        ok = (isinstance(s, dict) and not set(s) - {"title", "part", "shots", "notes", "budget_usd"} and s.get("part") in (1, 2, 3, 4)
              and isinstance(s.get("title"), str) and bool(s["title"].strip()))
        if not ok or not isinstance(s.get("shots"), list) or not s["shots"] \
                or not all(isinstance(x, str) for x in s["shots"]):
            errors.append(f"{path.name} · {name}: потрібні title (непорожній рядок), part (1–4), shots — непорожній "
                          "список id у лапках (\"1.01\")")
        elif dup := sorted({x for x in s["shots"] if s["shots"].count(x) > 1}):
            errors.append(f"{path.name} · {name}: шоти повторюються: {', '.join(dup)}")
    if errors:
        raise PromptError("\n".join(errors))
    return seqs


def sequence_items(slug: str, name: str, out_root: Path | None = None,
                   templates: dict[str, Template] | None = None) -> list[Item]:
    """Елементи послідовності в порядку виробництва: замикання залежностей (кастинг → кадри → відео → репліки).

    Беремо елементи шотів послідовності, потім усе, що вони потребують (needs → produces; «….last» — кліп), рекурсивно
    — і з кастингу, і з частини (напр. попередній шот для handoff continue)."""
    seqs = sequences(slug)
    if name not in seqs:
        raise PromptError(f"немає послідовності «{name}» у {sequences_path(slug).name} (є: {', '.join(seqs) or '—'})")
    from fabrica import compile as compile_mod
    from fabrica import shotspec

    seq = seqs[name]
    templates = templates or load_templates()
    data = Data(slug)
    specs = shotspec.part_specs(data, seq["part"], out_root)
    if missing := [s for s in seq["shots"] if s not in {sp.id for sp in specs}]:
        raise PromptError(f"послідовність «{name}»: шотів {missing} немає в shots.json частини {seq['part']}")
    part = compile_mod.spec_items(specs, data, templates)
    pool = casting_items(data, templates) + part
    producer = {i.produces: i for i in pool if i.produces}
    chosen: dict[str, Item] = {}
    todo = [i for i in part if i.extra.get("shot") in seq["shots"]]
    while todo:
        it = todo.pop()
        if it.id in chosen:
            continue
        chosen[it.id] = it
        for need in it.needs:
            src = producer.get(need) or producer.get(need.removesuffix(".last"))
            if src and src.id not in chosen:
                todo.append(src)
    return by_step([i for i in pool if i.id in chosen])


def set_of(item_id: str) -> str:
    """Набір за префіксом id: cast-/loc- → casting, tp- → test-pack, p<N>- → N (і кліпи «-video-2»)."""
    if item_id.startswith(("cast-", "loc-")):
        return "casting"
    if item_id.startswith("tp-"):
        return "test-pack"
    m = re.match(r"^p([1-4])-", item_id)
    if m:
        return m.group(1)
    raise PromptError(f"не впізнаю елемент «{item_id}»: очікую cast-…, loc-…, tp-… або p<N>-…")
