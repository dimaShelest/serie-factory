"""Каталог маршрутів генерації (prompts/providers.yaml): які поля приймає API, правила, ціна, ручна поверхня.

Маршрут = «<провайдер>:<модель>» (replicate:bytedance/seedance-2.5, cloudflare:…, elevenlabs:eleven_v4 …).
Компілятори промптів складають payload — рівно те тіло, яке отримає API (файли — рядки «ref:<id>»; поле, яке не
надсилаємо, — відсутнє, а не None), — і перевіряють його тут: validate() повертає "API: …" повідомлення,
порожній список — payload чистий. price() — вартість одного виклику, video_rates() — посекундні ставки для
кошторису (fabrica/costs.py), generation() — активний профіль довжини кліпу (env GENERATION_PROFILE).
route() / load() / generation() віддають копії: правка результату не зачіпає кеш каталогу.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from fabrica import config

CATALOG = config.ROOT / "prompts" / "providers.yaml"
PREFIX = "API: "
PROVIDERS = ("replicate", "cloudflare", "elevenlabs")
KINDS = ("image", "video", "voice", "voice_design", "lipsync")
TYPES = ("string", "uri", "uri_list", "string_list", "int", "number", "bool", "enum", "const", "object")
SPEC_KEYS = {"type", "values", "value", "min", "max", "also", "max_items", "min_chars", "max_chars", "pattern",
             "default", "required", "nullable", "in", "fields", "avoid", "policy", "why", "note"}
ROUTE_KEYS = {"provider", "model", "kind", "verified", "prompt_field", "prompt_max_chars", "fields", "rules", "price",
              "manual"}
PROFILE_KEYS = {"clip_s", "clip_min_s", "clip_max_s", "resolution", "resolution_by_tier", "surface", "url", "note"}
PRICE_UNITS = ("second", "image", "1k_chars")
REFS = ("reference_images", "reference_videos", "reference_audios")
URI_SCHEMES = ("http", "https", "ref", "data")


class ProviderError(ValueError):
    """Каталог маршрутів зламаний або маршруту немає — повідомлення пояснює, що виправити."""


@dataclass(frozen=True)
class Route:
    key: str
    provider: str
    model: str
    kind: str
    fields: dict             # ім'я → spec (див. шапку providers.yaml)
    rules: tuple[str, ...]
    prompt_field: str | None
    prompt_max_chars: int | None
    price: dict | None
    manual: dict             # surface, url, how (+ endpoint)
    verified: str

    @property
    def defaults(self) -> dict:
        """Що API візьме саме, якщо поле не надіслано."""
        return copy.deepcopy({k: s["default"] for k, s in self.fields.items() if "default" in s})


# ---------------------------------------------------------------- перевірка значень


def _set(v) -> bool:
    return v not in (None, "", [], {})


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _uri_error(v) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return "потрібен рядок: «ref:<id>», http(s)://… або локальний шлях"
    m = re.match(r"([A-Za-z][A-Za-z0-9+.-]+):", v)      # одна літера — диск Windows (C:\…), це шлях
    if not m:
        return None
    scheme = m.group(1).lower()
    if scheme not in URI_SCHEMES:
        return f"схема «{scheme}:» не підтримується — «ref:<id>», http(s)://…, data:… або локальний шлях"
    if scheme == "ref" and not v[4:].strip():
        return "«ref:» без id референсу"
    if scheme in ("http", "https") and not re.match(r"https?://[^\s/]+", v, re.IGNORECASE):
        return "неповний URL"
    return None


def _check(name: str, spec: dict, v, out: list[str], hints: dict | None = None) -> None:
    """Значення v проти spec (None доходить сюди лише для avoid-полів); помилки — в out без префікса."""
    t, n = spec["type"], len(out)
    if "avoid" in spec:
        out.append(f"«{name}» не надсилаємо: {spec['avoid']}")
        return
    if t in ("string", "uri") and not isinstance(v, str):
        out.append(f"«{name}» має бути рядком, а не {type(v).__name__}")
    elif t == "string":
        if "min_chars" in spec and len(v) < spec["min_chars"]:
            out.append(f"«{name}»: {len(v)} символів, мінімум {spec['min_chars']}")
        if "max_chars" in spec and len(v) > spec["max_chars"]:
            out.append(f"«{name}»: {len(v)} символів, максимум {spec['max_chars']}")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], v):
            out.append(f"«{name}»=«{v}» не відповідає шаблону {spec['pattern']}")
    elif t == "uri":
        if err := _uri_error(v):
            out.append(f"«{name}»: {err}")
    elif t in ("uri_list", "string_list"):
        if not isinstance(v, list):
            out.append(f"«{name}» має бути списком, а не {type(v).__name__}")
            return
        if "max_items" in spec and len(v) > spec["max_items"]:
            out.append(f"«{name}»: {len(v)} елементів, максимум {spec['max_items']}")
        for i, x in enumerate(v):
            if err := _uri_error(x) if t == "uri_list" else (None if isinstance(x, str) else "потрібен рядок"):
                out.append(f"«{name}»[{i}]: {err}")
    elif t in ("int", "number"):
        if not _num(v) or (t == "int" and not isinstance(v, int)):
            out.append(f"«{name}» має бути {'цілим числом' if t == 'int' else 'числом'}, а не {v!r}")
        elif v not in spec.get("also", ()) and not spec.get("min", v) <= v <= spec.get("max", v):
            also = f" (або {', '.join(map(str, spec['also']))})" if spec.get("also") else ""
            out.append(f"«{name}»={v} поза межами {spec.get('min', '…')}…{spec.get('max', '…')}{also}")
    elif t == "bool" and not isinstance(v, bool):
        out.append(f"«{name}» має бути true/false, а не {v!r}")
    elif t == "enum" and (not isinstance(v, str) or v not in spec["values"]):
        out.append(f"«{name}»=«{v}» — допустимо: {', '.join(map(str, spec['values']))}")
    elif t == "const" and (v != spec["value"] or type(v) is not type(spec["value"])):
        out.append(f"«{name}» має бути «{spec['value']}», а не «{v}»")
    elif t == "object":
        if not isinstance(v, dict):
            out.append(f"«{name}» має бути об'єктом, а не {type(v).__name__}")
            return
        _check_fields(spec["fields"], v, out, hints, prefix=f"{name}.")
    if "policy" in spec and len(out) == n and v != spec["policy"]:
        out.append(f"«{name}»={v!r} — тримаємо {spec['policy']!r}: {spec.get('why', 'рішення каталогу')}")


def _check_fields(fields: dict, payload: dict, out: list[str], hints: dict | None = None, prefix: str = "",
                  where: str = "") -> None:
    """Поля payload проти fields. None = API отримає null: можна лише для nullable-полів."""
    hints = hints or {}
    for k in payload:
        if k not in fields:
            hint = hints.get(f"{prefix}{k}") or (None if prefix else hints.get(k))    # «style» ≠ «voice_settings.style»
            out.append(f"невідоме поле «{prefix}{k}»{where}" + (f" — {hint}" if hint else " — прибери його"))
    for k, spec in fields.items():
        if spec.get("required") and payload.get(k) in (None, ""):
            out.append(f"бракує обов'язкового поля «{prefix}{k}»")
    for k, v in payload.items():
        if (spec := fields.get(k)) is None:
            continue
        if v is not None or "avoid" in spec:
            _check(prefix + k, spec, v, out, hints)
        elif not spec.get("nullable") and not spec.get("required"):
            out.append(f"«{prefix}{k}»=None — API отримає null; прибери ключ із payload")


# ---------------------------------------------------------------- іменовані правила


def _value(r: Route, p: dict, name: str):
    return p[name] if p.get(name) is not None else r.fields.get(name, {}).get("default")


def _frame_xor_reference(r: Route, p: dict) -> str | None:
    frame = [k for k in ("image", "last_frame_image") if _set(p.get(k))]
    refs = [k for k in REFS if _set(p.get(k))]
    if frame and refs:
        return (f"{' + '.join(frame)} не поєднується з {', '.join(refs)}: або кадровий режим (image / "
                "last_frame_image), або референсний (reference_*)")


def _last_frame_needs_image(r: Route, p: dict) -> str | None:
    if _set(p.get("last_frame_image")) and not _set(p.get("image")):
        return "last_frame_image без image: кінцевий кадр працює лише разом зі стартовим"


def _audio_needs_visual_ref(r: Route, p: dict) -> str | None:
    if _set(p.get("reference_audios")) and not (_set(p.get("reference_images")) or _set(p.get("reference_videos"))):
        return "reference_audios потребує хоча б одного reference_images або reference_videos (інакше E006)"


def _adaptive_with_frame(r: Route, p: dict) -> str | None:
    if _set(p.get("image")) and (ar := _value(r, p, "aspect_ratio")) != "adaptive":
        return f"зі стартовим кадром (image) aspect_ratio має бути «adaptive», а не «{ar}»"


def _match_input_needs_image(r: Route, p: dict) -> str | None:
    if _value(r, p, "aspect_ratio") == "match_input_image" and not _set(p.get("image_input")):
        return "aspect_ratio «match_input_image» без image_input — задай співвідношення явно (напр. «16:9»)"


def _text_or_auto_text(r: Route, p: dict) -> str | None:
    if not _set(p.get("text")) and p.get("auto_generate_text") is not True:
        s = r.fields["text"]
        return f"бракує text ({s.get('min_chars', 1)}–{s.get('max_chars', '…')} символів) або auto_generate_text: true"


RULES = {   # правило → (поля, без яких воно не має сенсу; перевірка)
    "frame_xor_reference": (("image",), _frame_xor_reference),
    "last_frame_needs_image": (("image", "last_frame_image"), _last_frame_needs_image),
    "audio_needs_visual_ref": (("reference_audios",), _audio_needs_visual_ref),
    "adaptive_with_frame": (("image", "aspect_ratio"), _adaptive_with_frame),
    "match_input_needs_image": (("image_input", "aspect_ratio"), _match_input_needs_image),
    "text_or_auto_text": (("text", "auto_generate_text"), _text_or_auto_text),
}


# ---------------------------------------------------------------- каталог


def _spec_errors(name: str, spec, errs: list[str]) -> None:
    n = len(errs)
    if not isinstance(spec, dict):
        errs.append(f"поле «{name}»: потрібен словник {{type: …}}")
        return
    if extra := set(spec) - SPEC_KEYS:
        errs.append(f"поле «{name}»: невідомі ключі {sorted(extra)} (можна: {', '.join(sorted(SPEC_KEYS))})")
    t = spec.get("type")
    if t not in TYPES:
        errs.append(f"поле «{name}»: type «{t}» — має бути одним із {', '.join(TYPES)}")
        return
    if t == "enum":
        vals = spec.get("values")
        if not isinstance(vals, list) or not vals or not all(isinstance(x, str) for x in vals):
            errs.append(f"поле «{name}»: enum потребує непорожнього списку values-рядків "
                        f"(on/off, «16:9» — в лапках, інакше YAML зробить bool / число): {vals!r}")
    if t == "const" and "value" not in spec:
        errs.append(f"поле «{name}»: const потребує value")
    if t == "object":
        if not isinstance(spec.get("fields"), dict) or not spec["fields"]:
            errs.append(f"поле «{name}»: object потребує fields")
        else:
            for k, s in spec["fields"].items():
                _spec_errors(f"{name}.{k}", s, errs)
    for k in ("min", "max"):
        if k in spec and not _num(spec[k]):
            errs.append(f"поле «{name}»: {k} має бути числом")
    for k in ("max_items", "min_chars", "max_chars"):
        if k in spec and (not _int(spec[k]) or spec[k] < 0):
            errs.append(f"поле «{name}»: {k} має бути цілим ≥ 0")
    for k in ("required", "nullable"):
        if k in spec and not isinstance(spec[k], bool):
            errs.append(f"поле «{name}»: {k} — true або false")
    if "also" in spec and not isinstance(spec["also"], list):
        errs.append(f"поле «{name}»: also має бути списком")
    if spec.get("in", "body") not in ("body", "query", "path"):
        errs.append(f"поле «{name}»: in — body, query або path")
    if "pattern" in spec:
        try:
            re.compile(spec["pattern"])
        except (re.error, TypeError) as e:
            errs.append(f"поле «{name}»: pattern не regex ({e})")
    if "default" in spec and spec["default"] is not None and len(errs) == n:     # default сам має бути валідним
        bad: list[str] = []
        _check(name, {k: v for k, v in spec.items() if k not in ("avoid", "policy")}, spec["default"], bad)
        errs += [f"default: {m}" for m in bad]


def _route_errors(key: str, raw, errs: list[str]) -> None:
    if not isinstance(raw, dict):
        errs.append("потрібен словник із provider, model, kind, fields …")
        return
    if extra := set(raw) - ROUTE_KEYS:
        errs.append(f"невідомі ключі {sorted(extra)} (можна: {', '.join(sorted(ROUTE_KEYS))})")
    provider, _, model = key.partition(":")
    if raw.get("provider") != provider or raw.get("model") != model or not model:
        errs.append(f"ключ має бути «<provider>:<model>» = «{raw.get('provider')}:{raw.get('model')}»")
    if provider not in PROVIDERS:
        errs.append(f"provider «{provider}» — має бути одним із {', '.join(PROVIDERS)}")
    if raw.get("kind") not in KINDS:
        errs.append(f"kind «{raw.get('kind')}» — має бути одним із {', '.join(KINDS)}")
    if not isinstance(raw.get("verified"), str) or not raw["verified"].strip():
        errs.append("verified: звідки і коли взято схему (або «UNVERIFIED: …»)")
    fields = raw.get("fields")
    if not isinstance(fields, dict) or not fields:
        errs.append("fields: словник полів payload")
        return
    for name, spec in fields.items():
        _spec_errors(name, spec, errs)
    pf, pmax = raw.get("prompt_field"), raw.get("prompt_max_chars")
    if pf is not None and pf not in fields:
        errs.append(f"prompt_field «{pf}» немає серед fields")
    if pmax is not None and (not _int(pmax) or pmax < 1 or pf is None):
        errs.append("prompt_max_chars — ціле ≥ 1 і лише разом із prompt_field")
    if pf in fields and pmax is not None and "max_chars" in (fields[pf] or {}):
        errs.append(f"«{pf}»: межу задай один раз — prompt_max_chars або max_chars у полі")
    rules = raw.get("rules") or []
    if not isinstance(rules, list):
        errs.append("rules має бути списком")
        rules = []
    for rule in rules:
        if rule not in RULES:
            errs.append(f"правило «{rule}» невідоме (є: {', '.join(RULES)})")
        elif missing := [f for f in RULES[rule][0] if f not in fields]:
            errs.append(f"правило «{rule}» потребує полів {missing}")
    _price_errors(raw.get("price"), fields, errs)
    manual = raw.get("manual")
    if not isinstance(manual, dict) or any(not isinstance(manual.get(k), str) or not manual[k].strip()
                                           for k in ("surface", "url", "how")):
        errs.append("manual: потрібні рядки surface, url, how (інструкція людині українською)")


def _price_errors(p, fields: dict, errs: list[str]) -> None:
    if p is None:
        return
    if not isinstance(p, dict) or p.get("unit") not in PRICE_UNITS:
        errs.append(f"price: словник з unit ∈ {', '.join(PRICE_UNITS)} (або null, якщо ціна невідома)")
        return
    if extra := set(p) - {"unit", "by", "values", "rate", "video_input", "note"}:
        errs.append(f"price: невідомі ключі {sorted(extra)}")
    if "by" not in p:
        if "rate" not in p or not (p["rate"] is None or _num(p["rate"])):
            errs.append("price: потрібні by + values або rate (число чи null)")
        return
    by = p["by"]
    if by not in fields:
        errs.append(f"price.by «{by}» немає серед fields")
    tables = {k: p[k] for k in ("values", "video_input") if k in p}
    for k, table in tables.items():
        if not isinstance(table, dict) or not table or not all(_num(x) for x in table.values()):
            errs.append(f"price.{k}: словник «значення поля → ставка USD»")
    if "values" not in p:
        errs.append("price: з by потрібні values")
    values, spec = p.get("values"), fields.get(by)
    if not isinstance(values, dict):
        return
    if isinstance(spec, dict) and spec.get("type") == "enum" and isinstance(spec.get("values"), list) \
            and set(values) != set(spec["values"]):       # нова роздільність без ставки → price() мовчки None
        errs.append(f"price.values: ключі {sorted(map(str, values))} ≠ значенням «{by}» "
                    f"{sorted(map(str, spec['values']))} — ставка на кожне значення")
    if isinstance(vi := p.get("video_input"), dict) and not set(vi) <= set(values):
        errs.append(f"price.video_input: зайві ключі {sorted(map(str, set(vi) - set(values)))} — їх немає у values")


def _generation_errors(gen, resolutions: set[str], errs: list[str]) -> None:
    """Блок generation: profile — один із profiles; профіль — clip_s або clip_min_s ≤ clip_max_s; роздільності."""
    if not isinstance(gen, dict) or not isinstance(gen.get("profiles"), dict) or not gen["profiles"]:
        errs.append("generation: потрібні profile і profiles {назва: {clip_s | clip_min_s + clip_max_s, resolution…}}")
        return
    if extra := set(gen) - {"profile", "profiles"}:
        errs.append(f"generation: невідомі ключі {sorted(extra)} (можна: profile, profiles)")
    if gen.get("profile") not in gen["profiles"]:
        errs.append(f"generation.profile «{gen.get('profile')}» немає серед profiles "
                    f"({', '.join(map(str, gen['profiles']))})")
    for name, p in gen["profiles"].items():
        where = f"generation.profiles.{name}"
        if not isinstance(p, dict):
            errs.append(f"{where}: потрібен словник")
            continue
        if extra := set(p) - PROFILE_KEYS:
            errs.append(f"{where}: невідомі ключі {sorted(extra)} (можна: {', '.join(sorted(PROFILE_KEYS))})")
        fixed, ranged = "clip_s" in p, "clip_min_s" in p or "clip_max_s" in p
        if fixed == ranged:
            errs.append(f"{where}: або clip_s: [5, …] (фіксовані довжини), або clip_min_s + clip_max_s")
        elif fixed:
            cs = p["clip_s"]
            if not isinstance(cs, list) or not cs or not all(_int(x) and x >= 1 for x in cs):
                errs.append(f"{where}: clip_s — непорожній список цілих секунд ≥ 1, а не {cs!r}")
        elif not (_int(lo := p.get("clip_min_s")) and _int(hi := p.get("clip_max_s")) and 1 <= lo <= hi):
            errs.append(f"{where}: clip_min_s ≤ clip_max_s — цілі секунди ≥ 1")
        res = [p["resolution"]] if "resolution" in p else []
        if "resolution_by_tier" in p:
            tiers = p["resolution_by_tier"]
            if not isinstance(tiers, dict) or not tiers or not all(isinstance(k, str) for k in tiers):
                errs.append(f"{where}: resolution_by_tier — словник «тир → роздільність»")
            else:
                res += list(tiers.values())
        if not res:
            errs.append(f"{where}: потрібні resolution або resolution_by_tier")
        for x in res:
            if not isinstance(x, str):
                errs.append(f"{where}: роздільність {x!r} — рядок у лапках («720p»)")
            elif resolutions and x not in resolutions:
                errs.append(f"{where}: роздільність «{x}» не знає жоден відео-маршрут ({', '.join(sorted(resolutions))})")
        for k in ("surface", "url", "note"):
            if k in p and (not isinstance(p[k], str) or not p[k].strip()):
                errs.append(f"{where}: {k} — непорожній рядок")


_CACHE: dict[Path, tuple[int, tuple[dict[str, Route], dict[str, str], dict | None]]] = {}


def _catalog(path: Path | None) -> tuple[dict[str, Route], dict[str, str], dict | None]:
    """(маршрути, підказки, generation) — спільний кеш; назовні віддаємо лише копії."""
    path = Path(path or CATALOG)
    try:
        mtime = path.stat().st_mtime_ns
    except FileNotFoundError:
        raise ProviderError(f"немає каталогу маршрутів {path}") from None
    if (hit := _CACHE.get(path)) and hit[0] == mtime:
        return hit[1]
    try:
        data = yaml.safe_load(path.read_bytes().decode("utf-8-sig")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise ProviderError(f"{path.name}: YAML не читається — {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("routes"), dict) or not data["routes"]:
        raise ProviderError(f"{path.name}: потрібен ключ routes із маршрутами «<provider>:<model>»")
    hints = data.get("hints") or {}
    if not isinstance(hints, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in hints.items()):
        raise ProviderError(f"{path.name}: hints — словник «поле → підказка» (вкладене — «voice_settings.style»)")
    errs = []
    for key, raw in data["routes"].items():
        mine: list[str] = []
        _route_errors(str(key), raw, mine)
        errs += [f"{key}: {m}" for m in mine]
    if not errs:
        resolutions = {x for raw in data["routes"].values() if raw["kind"] == "video"
                       for x in raw["fields"].get("resolution", {}).get("values", ())}
        if (gen := data.get("generation")) is not None:
            _generation_errors(gen, resolutions, errs)
    if errs:
        raise ProviderError(f"{path.name}: каталог зламаний —\n  " + "\n  ".join(errs))
    routes = {key: Route(key, raw["provider"], raw["model"], raw["kind"], raw["fields"], tuple(raw.get("rules") or ()),
                         raw.get("prompt_field"), raw.get("prompt_max_chars"), raw.get("price"), raw["manual"],
                         " ".join(raw["verified"].split()))
              for key, raw in data["routes"].items()}
    _CACHE[path] = (mtime, (routes, hints, data.get("generation")))
    return routes, hints, data.get("generation")


def _route(key: str, path: Path | None) -> Route:
    routes = _catalog(path)[0]
    try:
        return routes[key]
    except KeyError:
        raise ProviderError(f"немає маршруту «{key}» у {Path(path or CATALOG).name} (є: {', '.join(routes)})") from None


def load(path: Path | None = None) -> dict[str, Route]:
    """Маршрути з YAML (копія); перевіряє форму каталогу. Кеш — за шляхом і часом зміни файлу."""
    return copy.deepcopy(_catalog(path)[0])


def route(key: str, *, path: Path | None = None) -> Route:
    """Маршрут за ключем (копія — fields / manual можна правити, кеш не зміниться)."""
    return copy.deepcopy(_route(key, path))


def generation(*, path: Path | None = None) -> dict:
    """Активний профіль генерації кліпів: {"name", clip_s | clip_min_s + clip_max_s, resolution | resolution_by_tier,
    surface?, url?, note?}. GENERATION_PROFILE (оточення / .env) перемикає профіль із каталогу."""
    gen = _catalog(path)[2]
    if gen is None:
        raise ProviderError(f"{Path(path or CATALOG).name}: немає блоку generation (profile + profiles)")
    name = config.get("GENERATION_PROFILE") or gen["profile"]
    if name not in gen["profiles"]:
        raise ProviderError(f"профіль генерації «{name}» невідомий (є: {', '.join(gen['profiles'])}) — "
                            "перевір GENERATION_PROFILE в оточенні / .env")
    return {"name": name, **copy.deepcopy(gen["profiles"][name])}


def validate(key: str, payload: dict, *, path: Path | None = None) -> list[str]:
    """Payload проти схеми маршруту: "API: …" повідомлення українською; [] — можна відправляти.
    Поле, яке не надсилаємо, — відсутнє; None (= null у JSON) можна лише в nullable-полях."""
    r, hints = _route(key, path), _catalog(path)[1]
    if not isinstance(payload, dict):
        return [f"{PREFIX}payload має бути словником, а не {type(payload).__name__}"]
    out: list[str] = []
    _check_fields(r.fields, payload, out, hints, where=f" (маршрут {key} його не приймає)")
    text = payload.get(r.prompt_field) if r.prompt_field else None
    if r.prompt_max_chars and isinstance(text, str) and len(text) > r.prompt_max_chars:
        out.append(f"«{r.prompt_field}»: {len(text)} символів, максимум {r.prompt_max_chars}")
    for rule in r.rules:
        if msg := RULES[rule][1](r, payload):
            out.append(msg)
    return [PREFIX + m for m in dict.fromkeys(out)]


def split(key: str, payload: dict, *, path: Path | None = None) -> dict[str, dict]:
    """Payload → {"path": …, "query": …, "body": …} за полем `in` (ElevenLabs: voice_id — у шляху, формат — у query).
    Порожнє поле шляху — ProviderError: інакше запит піде на …/text-to-speech/None."""
    r = _route(key, path)
    for k, spec in r.fields.items():
        if spec.get("in") == "path" and (payload.get(k) is None or not str(payload[k]).strip()):
            where = " (впиши voice.voice_id у bible.yaml)" if k == "voice_id" else ""
            raise ProviderError(f"бракує «{k}» для шляху запиту {key}{where}")
    out: dict[str, dict] = {"path": {}, "query": {}, "body": {}}
    for k, v in payload.items():
        out[r.fields.get(k, {}).get("in", "body")][k] = v
    return out


def price(key: str, payload: dict, *, path: Path | None = None) -> float | None:
    """USD за один виклик: секундні — ставка × duration (-1 → максимум маршруту); зображення — за кадр;
    голос — за 1K символів. None — ціни в каталозі немає або з payload її не порахувати."""
    r = _route(key, path)
    p = r.price
    if not p:
        return None
    if "by" in p:
        table = p["video_input"] if p.get("video_input") and _set(payload.get("reference_videos")) else p["values"]
        rate = table.get(str(_value(r, payload, p["by"])))
    else:
        rate = p.get("rate")
    if rate is None:
        return None
    if p["unit"] == "image":
        return round(rate, 6)
    if p["unit"] == "1k_chars":
        text = payload.get(r.prompt_field) if r.prompt_field else None
        return round(rate * len(text) / 1000, 6) if isinstance(text, str) else None
    dur = _value(r, payload, "duration")
    if dur is not None and dur in r.fields.get("duration", {}).get("also", ()):
        dur = r.fields["duration"].get("max")
    return round(rate * dur, 6) if _num(dur) and dur > 0 else None


def video_rates(key: str, *, path: Path | None = None) -> dict[str, float]:
    """{"480p": …, "720p": …} — USD за секунду без відео-референсів (кошторис, fabrica/costs.py)."""
    r = _route(key, path)
    p = r.price or {}
    if p.get("unit") != "second" or p.get("by") != "resolution":
        raise ProviderError(f"маршрут «{key}» не має посекундних ставок за роздільністю (price.by: resolution)")
    return {str(k): float(v) for k, v in p["values"].items()}
