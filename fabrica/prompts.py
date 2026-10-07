"""Лабораторія промптів: шаблони prompts/templates/ + біблія → пакет промптів для ручних тестів.

Кожен елемент пакета — рівно той промпт, який автоматика відправить в API: текст, negative, параметри, сід,
референси. Люди тестують його руками (SYNTX, Gemini / Nano Banana, Dreamina, Replicate, ElevenLabs), пишуть
результат у журнал (`fabrica lab log`) і затверджують golden (`fabrica lab approve`). Автоматика бере лише golden.

Набори:
    casting    — герої (анфас, 3/4, профіль, повний зріст, 3 емоції, голос), сімка 1994 (+ мокрі), локації
    test-pack  — series/<slug>/lab/test_pack.yaml: стартові кадри + відео
    1 … 4      — частина: output/<slug>/part<N>/shots.json + series/<slug>/part<N>_prompts_en.yaml
Англійські описи — series/<slug>/prompt_en.yaml (той самий id, що в bible.yaml).
"""

from __future__ import annotations

import hashlib
import json
import re
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
VIEWS = [("front", "front"), ("three_quarter", "34"), ("profile", "profile"), ("full_body", "full")]
RESOLUTION = {"hero": "720p", "secondary": "480p", "found_footage": "480p"}


class PromptError(ValueError):
    """Шаблон або дані для промпту зламані — повідомлення пояснює, що виправити."""


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
        out[tid] = Template(tid, kind, data["version"], data.get("description", ""), data.get("params") or {},
                            data.get("prompt") or "", data.get("negative") or "", data.get("settings") or {},
                            path, hashlib.sha256(raw).hexdigest()[:12])
    return out


_ENV = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False, trim_blocks=True, lstrip_blocks=True)
_ENV.filters["capfirst"] = lambda s: s[:1].upper() + s[1:] if s else s     # capitalize() псує решту рядка


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"([.;!?])(?=[A-Za-zÁÉÍÓÚÑáéíóúñ¡¿«])", r"\1 ", text)   # «ghost.plain» → «ghost. plain»
    return re.sub(r"\.(\s*\.)+", ".", text)


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
    id: str                 # cast-mateo-front, loc-mina-dawn, tp-T1-frame, p1-4.03-video …
    set: str
    kind: str
    title: str
    template: Template
    prompt: str
    negative: str
    params: dict
    refs: list[str] = field(default_factory=list)      # id референсів (mateo.front, mina.dawn, tp.T1.frame …)
    produces: str | None = None                        # який референс дає цей елемент
    extra: dict = field(default_factory=dict)          # прев'ю голосу, критерії успіху, налаштування …
    warnings: list[str] = field(default_factory=list)

    @property
    def prompt_sha(self) -> str:
        payload = {"prompt": self.prompt, "negative": self.negative, "params": self.params, "refs": self.refs,
                   "template": self.template.ref, "extra": {k: v for k, v in self.extra.items() if k != "success"}}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


class Data:
    """Біблія (bible.yaml) + англійський шар (prompt_en.yaml) однієї історії."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.bible = bible_mod.load(slug).data
        path = bible_mod.SERIES / slug / "prompt_en.yaml"
        if not path.exists():
            raise PromptError(f"немає {path.relative_to(config.ROOT).as_posix()} — англійського шару для промптів")
        self.en = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        self.characters = {c["id"]: c for c in self.bible.get("characters", [])}
        self.members = {m["id"]: m for s in self.bible.get("supporting", []) for m in s.get("members", [])}
        self.groups = {g["id"]: g["members"] for g in self.bible.get("groups", [])}
        self.locations = {loc["id"]: loc for loc in self.bible.get("locations", [])}

    def common(self) -> dict:
        return {"style": self.en["style"], "rules": self.en["rules"], "negative": self.en["negative"],
                "uniform_1994": self.en["uniform_1994"], "wet_ghost": self.en["wet_ghost"]}

    def loc(self, loc_id: str) -> dict:
        try:
            return self.en["locations"][loc_id]
        except KeyError:
            raise PromptError(f"prompt_en.yaml: немає локації «{loc_id}»") from None

    def place(self, loc_id: str, variant: str | None = None, light: str | None = None) -> dict:
        """Опис, світло й настрій локації; стан (variant) — рядок або {desc, light}."""
        loc = self.loc(loc_id)
        v = (loc.get("variants") or {}).get(variant) if variant else None
        if variant and v is None:
            raise PromptError(f"prompt_en.yaml: у локації «{loc_id}» немає стану «{variant}»")
        v = v if isinstance(v, dict) else {"desc": v}
        return {"loc_desc": loc["base"] + (f"; {v['desc']}" if v.get("desc") else ""),
                "light": light or v.get("light") or loc["light"], "mood": v.get("mood") or loc["mood"]}

    def person(self, pid: str, state: str | None = None) -> dict:
        """name / desc (повна ДНК) / short (для відео) / ref (референс обличчя)."""
        if pid in self.en["characters"]:
            c = self.en["characters"][pid]
            return {"name": self.characters[pid]["name"], "desc": f"{c['who']}: {'; '.join(c['dna'])}; wearing "
                    f"{c['wardrobe']}", "short": "; ".join(c["dna"][:2]), "ref": f"{pid}.front"}
        if pid in self.en["members"]:
            m = self.en["members"][pid]
            desc = f"{m['who']}: {m['look']}; school uniform: {self.en['uniform_1994']}"
            if state == "wet":
                desc += f"; {self.en['wet_ghost']}"
            return {"name": self.members[pid]["name"], "desc": desc, "short": m["look"].split(",")[0],
                    "ref": f"{pid}.{'wet' if state == 'wet' else '1994'}"}
        raise PromptError(f"prompt_en.yaml: немає персонажа «{pid}» (characters / members)")

    def people(self, entries: list) -> list[dict]:
        out = []
        for e in entries:
            pid, state = (e, None) if isinstance(e, str) else (e["id"], e.get("state"))
            for one in self.groups.get(pid, [pid]):
                out.append(self.person(one, state))
        return out


def _item(data: Data, t: Template, item_id: str, set_name: str, title: str, ctx: dict, *, refs=(), produces=None,
          params=None, extra=None) -> Item:
    prompt, negative = render(t, {**data.common(), **ctx, "refs": list(refs)})
    p = {**t.params, **(params or {}), "seed": seed_for(item_id)}
    return Item(item_id, set_name, t.kind, title, t, prompt, negative, p, list(refs), produces, extra or {})


# ---------------------------------------------------------------- набори


def casting_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    items: list[Item] = []
    tc, tv = templates["image.character"], templates["voice.design"]
    for cid, ch in data.characters.items():
        c = data.en["characters"].get(cid)
        if c is None:
            raise PromptError(f"prompt_en.yaml: немає персонажа «{cid}»")
        base = {"c": c, "name": ch["name"]}
        for view, suffix in VIEWS:
            params = {"aspect_ratio": "2:3"} if view == "full_body" else None
            items.append(_item(data, tc, f"cast-{cid}-{suffix}", "casting", f"{ch['name']} — {view}",
                               {**base, "view": view, "emotion": ""}, refs=[] if view == "front" else [f"{cid}.front"],
                               produces=f"{cid}.{view}", params=params))
        for i, emotion in enumerate(c["emotions"], 1):
            items.append(_item(data, tc, f"cast-{cid}-emo{i}", "casting", f"{ch['name']} — емоція {i}",
                               {**base, "view": "emotion", "emotion": emotion}, refs=[f"{cid}.front"],
                               produces=f"{cid}.emotion{i}"))
        items.append(_item(data, tv, f"cast-{cid}-voice", "casting", f"{ch['name']} — голос", base,
                           produces=f"{cid}.voice", extra={"preview_es": c["preview_es"]}))
    tm = templates["image.member_1994"]
    for mid, member in data.members.items():
        m = data.en["members"].get(mid)
        if m is None:
            raise PromptError(f"prompt_en.yaml: немає учасника сімки «{mid}»")
        ctx = {"m": m, "name": member["name"], "member_id": mid}
        items.append(_item(data, tm, f"cast-{mid}-1994", "casting", f"{member['name']} — 1994",
                           {**ctx, "variant": "base"}, refs=["mateo.front"] if mid == "tomas" else [],
                           produces=f"{mid}.1994", params={"aspect_ratio": "3:4"}))
        items.append(_item(data, tm, f"cast-{mid}-wet", "casting", f"{member['name']} — мокрий",
                           {**ctx, "variant": "wet"}, refs=[f"{mid}.1994"], produces=f"{mid}.wet"))
    tl = templates["image.location"]
    for lid, loc in data.locations.items():
        en = data.loc(lid)
        items.append(_item(data, tl, f"loc-{lid}", "casting", f"{loc['name']} — плита", data.place(lid),
                           produces=f"{lid}.plate"))
        for variant in (en.get("variants") or {}):
            items.append(_item(data, tl, f"loc-{lid}-{variant}", "casting", f"{loc['name']} — {variant}",
                               data.place(lid, variant), refs=[f"{lid}.plate"], produces=f"{lid}.{variant}"))
    return items


def _frame_and_videos(data: Data, templates: dict[str, Template], set_name: str, prefix: str, title: str,
                      frame: dict, videos: list[dict], extra: dict) -> list[Item]:
    loc_id, variant, footage = frame["location"], frame.get("variant"), frame.get("footage")
    people = data.people(frame.get("people", []))
    loc_ref = f"{loc_id}.{variant}" if variant else f"{loc_id}.plate"
    frame_ref = f"{prefix.replace('-', '.')}.frame"
    refs = [p["ref"] for p in people] + [loc_ref]
    frame_item = _item(data, templates["image.start_frame"], f"{prefix}-frame", set_name, f"{title} — стартовий кадр",
                       {"composition": frame["composition"], "people": people, "footage": footage,
                        "framing": frame.get("framing", "Medium"), **data.place(loc_id, variant, frame.get("light"))},
                       refs=refs, produces=frame_ref, extra=extra)
    items = [frame_item]
    for v in videos:
        vid = f"{prefix}-video" if v["id"] == "video" else f"{prefix}-{v['id']}"
        items.append(_item(data, templates["video.shot"], vid, set_name, f"{title} — відео ({v['id']})",
                           {"action": v["action"], "camera": v["camera"], "light": v["light"], "people": people,
                            "footage": footage},
                           refs=[frame_ref] + [p["ref"] for p in people],
                           params={"resolution": v["resolution"], "duration_s": v["duration_s"]},
                           extra={**extra, "first_frame": frame_ref}))
    return items


def test_pack_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    path = bible_mod.SERIES / data.slug / "lab" / "test_pack.yaml"
    tp = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    items: list[Item] = []
    for t in tp["tests"]:
        extra = {"success": t.get("success", [])}
        items += _frame_and_videos(data, templates, "test-pack", f"tp-{t['id']}", f"{t['id']} · {t['title']}",
                                   t["frame"], t.get("videos", []), extra)
        for ef in t.get("extra_frames", []):
            items += _frame_and_videos(data, templates, "test-pack", f"tp-{t['id']}-{ef['id']}",
                                       f"{t['id']} · {t['title']} ({ef['id']})", ef, ef.get("videos", []), extra)
    return items


def overlay_file(slug: str, part: int) -> Path:
    """Англійські описи шотів частини: {shot_id: {composition, action, camera, light, variant}}."""
    return bible_mod.SERIES / slug / f"part{part}_prompts_en.yaml"


def part_items(data: Data, templates: dict[str, Template], part: int, out_root: Path | None = None) -> list[Item]:
    from fabrica.models import Script, Shots       # важкі моделі — лише коли збираємо частину

    folder = (out_root or OUTPUT) / data.slug / f"part{part}"
    shots_path = folder / "shots.json"
    if not shots_path.exists():
        raise PromptError(f"немає {shots_path} — спершу `fabrica shotlist {data.slug} {part}`")
    shots = Shots.model_validate_json(shots_path.read_text(encoding="utf-8-sig"))
    script_path = folder / "script.json"
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8-sig")) if script_path.exists() else None
    delivery = {ln.id: ln.delivery for sc in (script.scenes if script else []) for ln in sc.lines}
    overlay_path = overlay_file(data.slug, part)
    overlay = (yaml.safe_load(overlay_path.read_text(encoding="utf-8-sig")) or {}) if overlay_path.exists() else {}
    voices = {**{c: (data.characters[c].get("voice") or {}) for c in data.characters},
              **{m: (data.members[m].get("voice") or {}) for m in data.members},
              **{s["id"]: (s.get("voice") or {}) for s in data.bible.get("supporting", [])}}
    tv = templates["voice.line"]
    items: list[Item] = []
    for sh in shots.shots:
        prefix = f"p{part}-{sh.id}"
        if sh.tier not in ("montage",) and not (sh.reuse or "").startswith(("shot:", "plate:", "asset:")):
            en = overlay.get(sh.id) or {}
            warn = [] if en else [f"немає англійського опису шоту в {overlay_path.name} — у промпті український текст"]
            known = [c for c in sh.characters if c in data.en["characters"] or c in data.en["members"]
                     or c in data.groups]
            frame = {"location": sh.location_id or "mina", "variant": en.get("variant"),
                     "people": known, "footage": {"vhs": "vhs", "phone": "phone"}.get(sh.footage),
                     "framing": (sh.framing or "medium").replace("_", " ").capitalize(),
                     "composition": en.get("composition") or f"[UA → EN] {sh.action}"}
            videos = [] if sh.tier == "still" else [{
                "id": "video", "resolution": RESOLUTION.get(sh.tier, "480p"), "duration_s": sh.duration_s,
                "action": en.get("action") or f"[UA → EN] {sh.action}", "camera": en.get("camera") or sh.camera,
                "light": en.get("light") or data.place(sh.location_id or "mina")["light"]}]
            if sh.location_id is None:
                warn.append("у шоту немає location_id — взято mina")
            new = _frame_and_videos(data, templates, str(part), prefix, f"Ч.{part} · {sh.id}", frame, videos,
                                    {"tier": sh.tier})
            for it in new:
                it.warnings += warn
            items += new
        for n, d in enumerate(sh.dialogue, 1):
            v = voices.get(d.character_id or "", {})
            how = delivery.get(d.line_id or "", "normal")
            items.append(_item(data, tv, f"{prefix}-voice{n}", str(part), f"Ч.{part} · {sh.id} — репліка {n}",
                               {"text": d.text_es},
                               params={"voice_id": v.get("voice_id"), "voice": v.get("description"),
                                       "delivery": how, "settings": tv.settings.get(how, tv.settings["normal"])},
                               extra={"character": d.character_id, "offscreen": d.offscreen}))
    return items


def build(slug: str, set_name: str, kinds: list[str] | None = None, only: str | None = None,
          out_root: Path | None = None, templates: dict[str, Template] | None = None) -> list[Item]:
    """out_root=None → prompts.OUTPUT на момент виклику (тести й --out підміняють)."""
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
    if kinds:
        items = [i for i in items if i.kind in kinds]
    if only:
        items = [i for i in items if i.id == only or i.id.startswith(f"{only}-") or f"-{only}-" in f"{i.id}-"]
        if not items:
            raise PromptError(f"у наборі «{set_name}» немає елемента «{only}»")
    return items


def set_of(item_id: str) -> str:
    """Набір за префіксом id: cast-/loc- → casting, tp- → test-pack, p<N>- → N."""
    if item_id.startswith(("cast-", "loc-")):
        return "casting"
    if item_id.startswith("tp-"):
        return "test-pack"
    m = re.match(r"^p([1-4])-", item_id)
    if m:
        return m.group(1)
    raise PromptError(f"не впізнаю елемент «{item_id}»: очікую cast-…, loc-…, tp-… або p<N>-…")
