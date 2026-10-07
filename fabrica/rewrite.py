"""Переписувач студії (DESIGN §13, §16): «що не так» людини → правка ДЖЕРЕЛЬНИХ полів елемента + урок.

    p = propose("la-garganta", "p1-1.02-video", "камера трясеться, а треба штатив")
    apply("la-garganta", p["id"], save_lesson=True)

Джерело елемента (source_of): кадри й кліпи частини — поля шоту в оверлеї (frame, action, camera …); кастинг —
запис prompt_en.yaml (персонаж, учасник сімки, локація / її стан); репліка — delivery. LLM (бекенд REWRITE_BACKEND:
ollama — за замовчуванням, fabrica.local_llm, модель OLLAMA_MODEL; claude — офіційний SDK anthropic, `uv sync --extra
claude`, ключ ANTHROPIC_API_KEY з оточення / .env, у логи не йде) отримує поточний промпт, поля, які можна змінити,
правила ремесла (prompts/rewrite_rules.md), активні уроки елемента й відгук людини; повертає
{changes: [{field, value}], lesson: {problem, rule, scope}}. Невідомі поля — помилка; нові значення перевіряє збірка
промптів (шот-спека / prompt_en) — зламано → RewriteError, нічого не пишемо. Пропозиція тримається в пам'яті й у
.claude/tmp/studio_proposals.json; apply пише правки в series/<slug>/lab/overrides.yaml (ключ шоту «p<N>-<id>») і,
якщо треба, урок у lessons.yaml.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fabrica import config
from fabrica import lessons as lessons_mod
from fabrica import prompts as prompts_mod
from fabrica import shotspec as S

RULES = config.ROOT / "prompts" / "rewrite_rules.md"
PROPOSALS = config.ROOT / ".claude" / "tmp" / "studio_proposals.json"
CLAUDE_MODEL = "claude-opus-5-5"
CLAUDE_BETAS = ["server-side-fallback-2026-07-01"]
KEEP = 50                                   # скільки пропозицій пам'ятати
SHOT_FIELDS = ("frame", "end_frame", "action", "end_state", "camera", "sound", "people", "continuity", "clips",
               "window", "event_s")
EN_FIELDS = {   # що з prompt_en.yaml переписувач може змінити (плюс наявні ключі запису)
    "character": ("who", "tag", "dna", "wardrobe", "expression", "emotions", "voice", "voice_design", "preview_es"),
    "member": ("who", "tag", "look", "wardrobe", "wet", "voice_design", "preview_es"),
    "supporting": ("who", "tag", "look", "wardrobe", "voice", "voice_design", "preview_es"),
    "location": ("base", "light", "mood", "time", "framing"),
    "variant": ("desc", "light", "mood", "time", "framing"),
}
EN_SKIP = ("variants", "face_of", "replace", "ref", "id", "name")      # структура, не текст
DELIVERIES = ("normal", "quiet_fear", "whisper", "shout", "scream", "crying")
FORMATS = {
    "frame": "English text: static composition of the first instant",
    "end_frame": "English text: static composition of the last instant",
    "action": "English text: what moves",
    "end_state": "English text: visible end state",
    "camera": "one English camera sentence, OR JSON object text {size, move, speed, target, endpoint, angle, "
              "lens_mm, shake}; move: static|push_in|pull_out|pan_left|pan_right|tilt_up|tilt_down|follow|"
              "track_left|track_right|orbit|crane_up|crane_down|handheld|rack_focus|dolly_zoom",
    "sound": 'JSON object text {"ambience": ["..."], "sfx": ["..."]}',
    "people": 'JSON array text [{"id", "view", "screen", "facing", "state"}]; view: face|three_quarter|profile|'
              "back|silhouette|blurred|distant|hidden; screen: left|center|right",
    "continuity": "array of English strings",
    "clips": 'JSON array text [{"action", "end_state", "camera"}] — one per clip',
    "window": "[start, end] seconds of the clip to keep",
    "event_s": "number: second of the event in the clip",
    "delivery": " | ".join(DELIVERIES),
}

Backend = Callable[[str, dict, str], dict]


class RewriteError(ValueError):
    """Переписати не вдалося — повідомлення українською пояснює, що зробити."""


# ---------------------------------------------------------------- бекенди LLM


def backend_name() -> str:
    return (config.get("REWRITE_BACKEND") or "ollama").strip().lower()


def _ollama(prompt: str, schema: dict, system: str) -> dict:
    from fabrica import local_llm

    return local_llm.generate_json(prompt, schema, system=system, temperature=0.3, max_tokens=3000)


def _claude(prompt: str, schema: dict, system: str) -> dict:
    """Claude через офіційний SDK (beta: серверний fallback при відмові); ключ — лише в клієнт, ніде не друкуємо."""
    try:
        import anthropic
    except ImportError:
        raise RewriteError("REWRITE_BACKEND=claude, але пакет anthropic не встановлено — виконай "
                           "`uv sync --extra claude` (або постав REWRITE_BACKEND=ollama у .env)") from None
    key = config.get("ANTHROPIC_API_KEY")
    if not key:
        raise RewriteError("REWRITE_BACKEND=claude, але ANTHROPIC_API_KEY порожній — впиши ключ у .env")
    client = anthropic.Anthropic(api_key=key)
    try:
        resp = client.beta.messages.create(
            model=CLAUDE_MODEL, max_tokens=16000, betas=CLAUDE_BETAS, fallbacks="default", system=system,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": strict_schema(schema)}},
            messages=[{"role": "user", "content": prompt}])
    except anthropic.APIConnectionError:
        raise RewriteError("Claude API недоступний (немає мережі?) — спробуй ще раз або REWRITE_BACKEND=ollama") from None
    except anthropic.APIStatusError as e:
        raise RewriteError(f"Claude API відповів помилкою {e.status_code} ({type(e).__name__}) — перевір ключ і "
                           "ліміти в консолі Anthropic") from None
    if resp.stop_reason == "refusal":
        raise RewriteError("Claude відмовився переписувати (фільтр безпеки) — переформулюй відгук спокійніше")
    if resp.stop_reason == "max_tokens":
        raise RewriteError("відповідь Claude обрізано (max_tokens) — спробуй коротший відгук")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        raise RewriteError("Claude повернув не JSON — спробуй ще раз") from None


BACKENDS: dict[str, Backend] = {"ollama": _ollama, "claude": _claude}


def strict_schema(schema):
    """Схема для Claude: кожен об'єкт — additionalProperties: false (вимога structured outputs)."""
    if isinstance(schema, dict):
        out = {k: strict_schema(v) for k, v in schema.items()}
        if out.get("type") == "object":
            out.setdefault("additionalProperties", False)
        return out
    return [strict_schema(x) for x in schema] if isinstance(schema, list) else schema


_STATUS: dict[str, tuple[float, dict]] = {}


def backend_status() -> dict:
    """{"name", "model", "ok", "note"} для шапки студії. Ollama перевіряємо раз на хвилину (localhost, 3 с)."""
    import time

    name = backend_name()
    if name == "claude":
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return {"name": name, "model": CLAUDE_MODEL, "ok": False, "note": "не встановлено: uv sync --extra claude"}
        ok = bool(config.get("ANTHROPIC_API_KEY"))
        return {"name": name, "model": CLAUDE_MODEL, "ok": ok, "note": "" if ok else "немає ANTHROPIC_API_KEY у .env"}
    if name != "ollama":
        return {"name": name, "model": "", "ok": name in BACKENDS,
                "note": "" if name in BACKENDS else f"невідомий REWRITE_BACKEND «{name}» (ollama | claude)"}
    from fabrica import local_llm

    _, model = local_llm.settings()
    hit = _STATUS.get(model)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    try:
        have = local_llm.available_models()
        ok = any(m == model or m.split(":")[0] == model for m in have)
        note = "" if ok else f"модель не завантажена: ollama pull {model}"
    except local_llm.LocalLLMError:
        ok, note = False, "Ollama не запущена — відкрий застосунок Ollama або `ollama serve`"
    out = {"name": name, "model": model, "ok": ok, "note": note}
    _STATUS[model] = (time.monotonic(), out)
    return out


# ---------------------------------------------------------------- джерело елемента


def _part(item: prompts_mod.Item) -> int | None:
    return int(item.set) if str(item.set).isdigit() else None


def _shots(slug: str, part: int):
    from fabrica.models import Shots

    path = prompts_mod.OUTPUT / slug / f"part{part}" / "shots.json"
    if not path.exists():
        raise RewriteError(f"немає {path.name} частини {part} — спершу `fabrica shotlist {slug} {part}`")
    return Shots.model_validate_json(path.read_text(encoding="utf-8-sig"))


def shot_in(data: prompts_mod.Data, part: int, key: str, cache: dict | None = None) -> tuple[dict, list[str]]:
    """Поточні поля шоту (оверлей + overrides студії) як JSON-словник + які поля змінено через студію.
    cache — словник на одну збірку стану студії (оверлей частини читаємо раз)."""
    cache = {} if cache is None else cache
    if part not in cache:
        shots = _shots(data.slug, part)
        ovr = S.part_overrides(data, part, {s.id for s in shots.shots}, {s.scene_id for s in shots.shots})
        cache[part] = (S.load_overlay(data.slug, part, overrides=ovr), ovr)
    ov, ovr = cache[part]
    shot = (ov.get("shots") or {}).get(key)
    fields = shot.model_dump(mode="json", exclude_unset=True) if shot else {}
    return fields, sorted((ovr.get("shots") or {}).get(key) or {})


def _en_entry(data: prompts_mod.Data, item: prompts_mod.Item) -> tuple[str, str, list[str], dict] | None:
    """Кастинг → (kind, key, шлях у prompt_en, запис)."""
    owner, _, what = (item.produces or "").partition(".")
    en = data.en
    if owner in (en.get("locations") or {}):
        loc = en["locations"][owner]
        if what == "plate":
            return "location", owner, ["locations", owner], {k: v for k, v in loc.items() if k != "variants"}
        v = (loc.get("variants") or {}).get(what)
        return "variant", f"{owner}.{what}", ["locations", owner, "variants", what], \
            dict(v) if isinstance(v, dict) else {"desc": v}
    for kind, block in (("character", "characters"), ("member", "members"), ("supporting", "supporting")):
        if isinstance((en.get(block) or {}).get(owner), dict):
            return kind, owner, [block, owner], dict(en[block][owner])
    return None


def source_of(slug: str, item: prompts_mod.Item, data: prompts_mod.Data | None = None,
              cache: dict | None = None) -> dict:
    """Звідки компілюється елемент і що в ньому можна правити:
    {"kind": shot|line|character|member|supporting|location|test, "key", "fields", "editable", "target",
     "part"?, "n"?, "path"?, "overridden"?}."""
    data = data or prompts_mod.Data(slug)
    part, shot = _part(item), item.extra.get("shot")
    if item.template.id == "voice.line" and part and shot:
        m = re.search(r"-voice(\d+)$", item.id)
        n = int(m.group(1)) if m else 1
        return _mark({"kind": "line", "key": shot, "part": part, "n": n, "target": "line",
                      "fields": {"delivery": item.extra.get("delivery"), "speaker": item.extra.get("character"),
                                 "delivery_source": item.extra.get("delivery_source")}, "editable": ["delivery"]},
                     ["delivery"] if _line_overridden(data, part, shot, n) else [])
    if part and shot:
        fields, overridden = shot_in(data, part, shot, cache)
        return _mark({"kind": "shot", "key": shot, "part": part, "target": "overlay", "fields": fields,
                      "editable": list(SHOT_FIELDS)}, overridden)
    if item.set == "test-pack":
        return {"kind": "test", "key": shot or item.id, "target": None, "fields": _test_fields(slug, shot),
                "editable": []}
    hit = _en_entry(data, item)
    if hit is None:
        return {"kind": "other", "key": item.id, "target": None, "fields": {}, "editable": []}
    kind, key, path, entry = hit
    editable = list(dict.fromkeys([*EN_FIELDS[kind], *(k for k in entry if k not in EN_SKIP)]))
    kind = "location" if kind == "variant" else kind               # стан локації — та сама локація, key «mina.tunnel»
    over = (data.overrides.get("prompt_en") or {})
    for p in path:
        over = over.get(p) if isinstance(over, dict) else None
    return _mark({"kind": kind, "key": key, "target": "prompt_en", "path": path,
                  "fields": {k: v for k, v in entry.items() if k not in EN_SKIP}, "editable": editable},
                 sorted(over) if isinstance(over, dict) else [])


def _mark(src: dict, overridden: list[str]) -> dict:
    """«змінено через студію»: поле overridden — лише коли щось справді змінено (порожнього списку не віддаємо)."""
    return src | ({"overridden": overridden} if overridden else {})


def _line_overridden(data: prompts_mod.Data, part: int, shot: str, n: int) -> bool:
    for key in (shot, f"p{part}-{shot}"):
        lines = ((data.overrides.get("shots") or {}).get(key) or {}).get("lines") or {}
        if isinstance(lines, dict) and "delivery" in ({str(k): v for k, v in lines.items()}.get(str(n)) or {}):
            return True
    return False


def _test_fields(slug: str, shot: str | None) -> dict:
    try:
        raw = yaml.safe_load(S.test_pack_path(slug).read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    tid = (shot or "").split("-")[0]
    return next((t for t in raw.get("tests") or [] if isinstance(t, dict) and str(t.get("id")) == tid), {})


def item_tags(slug: str, item: prompts_mod.Item, data: prompts_mod.Data) -> list[str]:
    """Мітки елемента (як у компілятора) — з них урок вибирає scope.tags."""
    from fabrica import compile as compile_mod

    part, shot = _part(item), item.extra.get("shot")
    try:
        if part and shot:
            spec = next(s for s in S.part_specs(data, part) if s.id == shot)
            return sorted(compile_mod._tags(spec))
        if item.set == "test-pack" and shot:
            spec = next(s for s in S.test_pack_specs(data) if s.id == shot)
            return sorted(compile_mod._tags(spec))
    except (StopIteration, ValueError):
        return []
    owner, _, what = (item.produces or "").partition(".")
    if owner in data.locations:
        return [f"location:{owner}"] + ([f"variant:{what}"] if what != "plate" else [])
    return [f"character:{owner}"] if owner else []


# ---------------------------------------------------------------- пропозиція


def rules_text(path: Path | None = None) -> str:
    text = (path or RULES).read_text(encoding="utf-8-sig") if (path or RULES).exists() else ""
    return re.sub(r"<!--.*?-->\s*", "", text, flags=re.S).strip()


def schema_for(editable: list[str], kinds: tuple[str, ...], route: str, tags: list[str]) -> dict:
    """JSON-схема відповіді (проста — для малої локальної моделі)."""
    value = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "array", "items": {"type": "string"}},
                       {"type": "array", "items": {"type": "number"}}]}
    tag_items = {"type": "string", "enum": tags} if tags else {"type": "string"}
    return {"type": "object", "required": ["changes", "lesson"], "properties": {
        "changes": {"type": "array", "items": {"type": "object", "required": ["field", "value"], "properties": {
            "field": {"type": "string", "enum": editable}, "value": value}}},
        "lesson": {"type": "object", "required": ["problem", "rule", "scope"], "properties": {
            "problem": {"type": "string"}, "rule": {"type": "string"},
            "scope": {"type": "object", "required": ["kind", "route", "tags"], "properties": {
                "kind": {"type": "string", "enum": list(kinds)},
                "route": {"anyOf": [{"type": "null"}, {"type": "string", "enum": [route]}]},
                "tags": {"type": "array", "items": tag_items}}}}}}}


def build_prompt(item: prompts_mod.Item, src: dict, lessons: list[dict], tags: list[str], feedback: str) -> str:
    fields = {f: src["fields"].get(f) for f in src["editable"]}
    formats = {f: FORMATS[f] for f in src["editable"] if f in FORMATS}
    rows = [f"ITEM: {item.id} — {item.kind}, route {item.route or '—'}, template {item.template.ref}",
            f"SOURCE: {src['kind']} «{src['key']}» (the compiler builds the prompt from these fields)",
            "CURRENT PROMPT:", f'"""{item.prompt}"""',
            "EDITABLE FIELDS (current values as JSON; null = not set yet):",
            json.dumps(fields, ensure_ascii=False, indent=1)]
    if formats:
        rows += ["VALUE FORMATS:"] + [f"- {f}: {v}" for f, v in formats.items()]
    clip = item.extra.get("clip") if isinstance(item.extra.get("clip"), dict) else {}
    if (clip.get("of") or 1) > 1:
        rows.append(f"CLIP: this item is clip {clip['index']} of {clip['of']} — its action / end_state / camera come "
                    f"from clips[{clip['index'] - 1}]: to change them, return the whole `clips` array.")
    rows += ["ACTIVE LESSONS FOR THIS ITEM:"] + ([f"- {x['id']}: {x['rule']}" for x in lessons] or ["- none"])
    rows += [f"ITEM TAGS (for lesson scope.tags): {', '.join(tags) or '—'}",
             "HUMAN FEEDBACK (may be Ukrainian):", f'"""{feedback.strip()}"""',
             "TASK: return JSON {\"changes\": [{\"field\", \"value\"}], \"lesson\": {\"problem\", \"rule\", \"scope\": "
             "{\"kind\", \"route\", \"tags\"}}}. Change only the fields the feedback needs; each value is the COMPLETE new "
             "value of that field (not a diff). Keep the craft rules."]
    return "\n".join(rows)


def _value(field: str, value, old):
    """Значення від LLM → тип поля: JSON-текст ({…} / […]) розбираємо; список ↔ рядок не міняємо мовчки."""
    if isinstance(value, str) and value.strip()[:1] in "{[":
        try:
            value = json.loads(value)
        except ValueError:
            if field in ("sound", "people", "clips", "window"):
                raise RewriteError(f"поле {field}: LLM дав зламаний JSON — спробуй ще раз") from None
    if field == "delivery" and value not in DELIVERIES:
        raise RewriteError(f"delivery «{value}» — можна: {', '.join(DELIVERIES)}")
    if isinstance(old, list) and not isinstance(value, list):
        raise RewriteError(f"поле {field} — список, а LLM дав {type(value).__name__}; спробуй ще раз")
    if isinstance(old, str) and not isinstance(value, str):
        raise RewriteError(f"поле {field} — текст, а LLM дав {type(value).__name__}; спробуй ще раз")
    return value


def _patch(src: dict, changes: list[dict]) -> dict:
    """Зміни → шар overrides.yaml: шот «p<N>-<id>», репліка — lines.<n>.delivery, prompt_en — вкладений шлях."""
    if src["target"] == "overlay":
        return {"shots": {f"p{src['part']}-{src['key']}": {c["field"]: c["new"] for c in changes}}}
    if src["target"] == "line":
        return {"shots": {f"p{src['part']}-{src['key']}": {"lines": {src["n"]: {"delivery": changes[-1]["new"]}}}}}
    body: dict = {c["field"]: c["new"] for c in changes}
    for p in reversed(src["path"]):
        body = {p: body}
    return {"prompt_en": body}


def _find(items: list[prompts_mod.Item], item_id: str, after: bool = False) -> prompts_mod.Item:
    hit = next((i for i in items if i.id == item_id), None)
    if hit is None:
        raise RewriteError(f"після правки елемента «{item_id}» більше немає (змінилась кількість кліпів?) — "
                           "переформулюй відгук" if after else f"елемента «{item_id}» немає в наборі")
    return hit


def lesson_ids(item: prompts_mod.Item) -> list[str]:
    """Уроки, що стосуються елемента: ті, що в промпті (extra.lessons), і ті, що не вмістились (попередження)."""
    dropped = [m.group(1) for w in item.warnings if (m := re.match(r"урок (L\d+) не вмістився", w))]
    return list(dict.fromkeys([*(item.extra.get("lessons") or []), *dropped]))


def _lesson(raw: dict, item: prompts_mod.Item, tags: list[str], feedback: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    scope = raw.get("scope") if isinstance(raw.get("scope"), dict) else {}
    values = {t.split(":", 1)[-1] for t in tags}
    out_scope = {"kind": scope.get("kind") if scope.get("kind") in ("image", "video", "voice") else item.kind}
    if scope.get("route") and scope["route"] == item.route:
        out_scope["route"] = item.route
    if good := [t for t in scope.get("tags") or [] if isinstance(t, str) and (t in tags or t in values)]:
        out_scope["tags"] = list(dict.fromkeys(good))
    rule = re.sub(r"\s+", " ", str(raw.get("rule") or "")).strip()
    problem = re.sub(r"\s+", " ", str(raw.get("problem") or feedback)).strip()[:300]
    return {"problem": problem, "rule": rule, "scope": out_scope, "item": item.id, "route": item.route,
            "kind": item.kind}


_LOCK = threading.Lock()
_MEM: dict[str, dict] = {}


def _store(p: dict) -> None:
    with _LOCK:
        _MEM[p["id"]] = p
        disk = _disk()
        disk[p["id"]] = p
        keep = dict(sorted(disk.items(), key=lambda kv: kv[1].get("at", ""))[-KEEP:])
        PROPOSALS.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROPOSALS.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(keep, f, ensure_ascii=False, indent=1)
        tmp.replace(PROPOSALS)


def _disk() -> dict:
    try:
        raw = json.loads(PROPOSALS.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def get(proposal_id: str) -> dict:
    with _LOCK:
        p = _MEM.get(proposal_id) or _disk().get(proposal_id)
    if not p:
        raise RewriteError(f"пропозиції «{proposal_id}» немає (застаріла?) — натисни «Редагувати» ще раз")
    return p


def public(p: dict) -> dict:
    """Пропозиція для студії (без внутрішніх полів «_…»)."""
    return {k: v for k, v in p.items() if not k.startswith("_")}


def propose(slug: str, item_id: str, feedback: str, *, backend: str | None = None) -> dict:
    """Відгук людини → пропозиція {id, item, backend, changes, lesson, prompt_old, prompt_new, warnings_new}.
    Нічого не пише в series/: нові поля збираються в пам'яті (pending_overrides)."""
    if not (feedback or "").strip():
        raise RewriteError("опиши, що не так (поле «що не так» порожнє)")
    set_name = prompts_mod.set_of(item_id)
    data = prompts_mod.Data(slug)
    item = _find(prompts_mod.build(slug, set_name), item_id)
    src = source_of(slug, item, data)
    if not src["editable"]:
        raise RewriteError("цей елемент студія не переписує: тест-пак правиться в series/<slug>/lab/test_pack.yaml"
                           if src["kind"] == "test" else f"не знаю, з чого компілюється «{item_id}»")
    tags = item_tags(slug, item, data)
    known = {x.get("id"): x for x in lessons_mod.load(slug)}
    active = [known[i] for i in lesson_ids(item) if i in known]
    name = backend or backend_name()
    fn = BACKENDS.get(name)
    if fn is None:
        raise RewriteError(f"невідомий REWRITE_BACKEND «{name}» — ollama або claude")
    kinds = ("image", "video") if item.kind != "voice" else ("voice",)
    try:
        raw = fn(build_prompt(item, src, active, tags, feedback), schema_for(src["editable"], kinds, item.route, tags),
                 rules_text())
    except RewriteError:
        raise
    except Exception as e:                  # local_llm.LocalLLMError та ін. — людині одним рядком
        raise RewriteError(f"бекенд {name}: {e}") from None
    changes = []
    for c in (raw or {}).get("changes") or []:
        f = c.get("field") if isinstance(c, dict) else None
        if f not in src["editable"]:
            raise RewriteError(f"LLM хоче змінити невідоме поле «{f}» (можна: {', '.join(src['editable'])})")
        old = src["fields"].get(f)
        new = _value(f, c.get("value"), old)
        if new != old:
            changes.append({"target": src["target"], "key": src["key"], "field": f, "old": old, "new": new,
                            **({"part": src["part"]} if src.get("part") else {}),
                            **({"n": src["n"]} if src.get("n") else {})})
    lesson = _lesson((raw or {}).get("lesson"), item, tags, feedback)
    if not changes and not lesson["rule"]:
        raise RewriteError("LLM не запропонував ні правки, ні уроку — опиши проблему конкретніше")
    patch = _patch(src, changes) if changes else {}
    preview = {**lesson, "id": lessons_mod.next_id(slug), "active": True} if lesson["rule"] else None
    try:
        with prompts_mod.pending_overrides(slug, patch), lessons_mod.pending(slug, preview):
            new_item = _find(prompts_mod.build(slug, set_name), item_id, after=True)
    except (S.SpecError, prompts_mod.PromptError, lessons_mod.LessonError) as e:
        raise RewriteError(f"правка ламає дані — нічого не записано:\n{e}") from None
    p = {"id": f"rw-{uuid.uuid4().hex[:8]}", "story": slug, "item": item_id, "backend": name, "changes": changes,
         "lesson": lesson, "prompt_old": item.prompt, "prompt_new": new_item.prompt,
         "sha_old": item.prompt_sha, "sha_new": new_item.prompt_sha,
         "warnings_new": new_item.warnings + lessons_mod.lint_hits(slug, new_item.extra.get("lessons") or [],
                                                                  new_item.prompt),
         "feedback": feedback.strip(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "_patch": patch}
    _store(p)
    return p


# ---------------------------------------------------------------- запис


def _head(path: Path, default: str) -> str:
    if not path.exists():
        return default
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    end = next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith("#")), len(lines))
    head = "\n".join(lines[:end]).rstrip()
    return head + "\n" if head else default


OVERRIDES_HEAD = ("# Правки промптів через студію (`fabrica studio` → «Редагувати»). Компілятор накладає їх останніми:\n"
                  "# shots / scenes — поле в поле поверх part<N>_prompts_en.yaml (ключ «p1-1.02» — лише частина 1,\n"
                  "# «1.02» — будь-яка частина); prompt_en — вкладено поверх prompt_en.yaml. Можна правити й руками.\n")


def write_overrides(slug: str, patch: dict) -> Path:
    """Шар patch → series/<slug>/lab/overrides.yaml (шапку-коментар зберігаємо)."""
    path = prompts_mod.overrides_path(slug)
    raw = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    merged = prompts_mod.merge_overrides(raw if isinstance(raw, dict) else {}, patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    head = _head(path, OVERRIDES_HEAD)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n")
        yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False, width=110)
    tmp.replace(path)
    return path


def apply(slug: str, proposal_id: str, *, save_lesson: bool = True, rule: str | None = None) -> dict:
    """Записати пропозицію: правки → overrides.yaml (перевірка збіркою; зламалось — відкат), урок → lessons.yaml.
    → {"item": id, "lesson": id уроку або None}."""
    p = get(proposal_id)
    if p.get("story") != slug:
        raise RewriteError(f"пропозиція «{proposal_id}» — для історії {p.get('story')}, а не {slug}")
    if p.get("applied"):
        raise RewriteError(f"пропозицію «{proposal_id}» уже записано ({p['applied']}) — щоб змінити ще, «Редагувати»")
    path = prompts_mod.overrides_path(slug)
    before = path.read_bytes() if path.exists() else None
    if p.get("_patch"):
        write_overrides(slug, p["_patch"])
        try:
            prompts_mod.build(slug, prompts_mod.set_of(p["item"]))
        except (S.SpecError, prompts_mod.PromptError) as e:
            if before is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(before)
            raise RewriteError(f"після запису збірка ламається — відкотив overrides.yaml:\n{e}") from None
    lid = None
    lesson = dict(p.get("lesson") or {})
    if rule is not None and rule.strip():
        lesson["rule"] = rule.strip()
    if save_lesson and lesson.get("rule"):
        lid = lessons_mod.add(slug, lesson)
    _store({**p, "applied": datetime.now(timezone.utc).isoformat(timespec="seconds"), "lesson_id": lid})
    return {"item": p["item"], "lesson": lid}
