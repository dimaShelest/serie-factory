"""Компілятори промптів (DESIGN §7): prompt_en.yaml + шот-спека → Item із промптом, payload і маршрутом.

Кожен компілятор: ctx → render(шаблон) → промпт; payload = payload шаблону (+ route_payload маршруту) + обчислені
поля (промпт, «ref:<id>» у слотах, тривалість, роздільність, сід …); маршрут (кліп зі стартовим кадром, де є
обличчя, → Cloudflare з use_virtual_avatar, інакше й t2v — Replicate; якорі облич — nano-banana-pro, решта зображень
— nano-banana-2.1; репліки — eleven_v4; голоси — eleven_ttv_v3); providers.validate → «API: …»; lint → «lint: …»;
уроки лабораторії (слот LESSONS); крок, needs, params, extra (ручні інструкції по поверхнях: спершу поверхня
активного профілю генерації — dropshot AI Studio, — потім AI Studio / ElevenLabs JSON, наприкінці — поверхня маршруту
з providers.yaml).

Жорсткі правила (тести — tests/test_compile.py):
1. negative = "" (жоден API його не бере); заперечення у відео — лише whitelist (лінт).
2. Відео не переописує зовнішність: люди — лише tag (роль + одяг), стани — їх video-фраза.
3. Ракурс → референс: face / three_quarter / profile — свій ракурс героя; back / silhouette / distant — повний зріст
   (сімка — якір 1994 або мокрий); blurred / hidden — без референсу (лише текст). Не більше 4 людей-референсів.
4. Image 1 — локація (кінцевий кадр — стартовий кадр шоту), далі люди зліва направо (left → center → right → решта).
5. Промпт ≤ prompt_max_chars маршруту (validate); відео — ціль ≤ 1600 символів, інакше попередження.
6. Репліка в кадрі → камера static або push_in very slow (інакше попередження), решта тримає рот закритим;
   мовець у кадрі без lip-sync — говорить він (і попередження, якщо його рот видно); репліка поза кадром (offscreen
   або мовця немає в кадрі) — голос за кадром, у кадрі роти закриті.
7. Відео не називає героїв на ім'я (поза репліками) — попередження; на маршруті з обличчям і в t2v кадр приблизний
   або його немає → розстановка й continuity словами.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from fabrica import lessons as lessons_mod
from fabrica import lint as lint_mod
from fabrica import providers
from fabrica import shotspec as S
from fabrica.prompts import STEP, Data, Item, PromptError, Template, render, seed_for

ANCHOR_ROUTE = "replicate:google/nano-banana-pro"       # якір обличчя лише текстом
FACE_ROUTE = "cloudflare:bytedance/seedance-2.5"        # відео з обличчям (use_virtual_avatar)
MAX_PEOPLE_REFS = 4                                     # nano-banana-2.1: ≤ 4 персонажі (UNVERIFIED, §4.5)
VIDEO_TARGET = 1600                                     # ціль довжини відео-промпту (ліміт маршруту 2000)
REF_FIELDS = ("image", "last_frame_image", "image_input", "reference_images", "reference_videos", "reference_audios")
CHAR_VIEWS = (("front", "front"), ("three_quarter", "34"), ("profile", "profile"), ("full_body", "full"))
VIEW_UA = {"front": "анфас (якір)", "three_quarter": "3/4", "profile": "профіль", "full_body": "повний зріст"}
VIEW_REF = {"face": "front", "three_quarter": "three_quarter", "profile": "profile", "back": "full_body",
            "silhouette": "full_body", "distant": "full_body"}          # blurred / hidden — без референсу
VIEW_IMAGE = {"face": "facing the camera", "three_quarter": "in a three-quarter view", "profile": "in profile",
              "back": "seen from behind", "silhouette": "as a dark silhouette", "blurred": "out of focus, the face "
              "unreadable", "distant": "small in the distance", "hidden": "with the face hidden from view"}
VIEW_VIDEO = {"face": "facing the camera", "three_quarter": "in three-quarter view", "profile": "in profile",
              "back": "with the back to the camera", "silhouette": "as a dark silhouette", "blurred": "out of focus",
              "distant": "far in the background", "hidden": "with the face out of view"}
SCREEN = {"left": "on the left of the frame", "center": "in the center of the frame",
          "right": "on the right of the frame"}
SCREEN_ORDER = {"left": 0, "center": 1, "right": 2, None: 3}
DELIVERY_VIDEO = {"normal": "in a natural voice", "quiet_fear": "quietly, with controlled fear",
                  "whisper": "in a trembling whisper", "shout": "shouting", "scream": "screaming in terror",
                  "crying": "sobbing, voice breaking"}
ACCENT = "in Mexican Spanish with a Mexico City accent"
STATIC = "Static locked-off camera on a tripod; the frame does not move."
# рух → (з ціллю, без цілі); {t} — ціль камери
MOVES = {"push_in": ("push in toward {t}", "push in"), "pull_out": ("pull out from {t}", "pull out"),
         "pan_left": ("pan left across {t}", "pan left"), "pan_right": ("pan right across {t}", "pan right"),
         "tilt_up": ("tilt up to {t}", "tilt up"), "tilt_down": ("tilt down to {t}", "tilt down"),
         "follow": ("follow shot behind {t}, matching the pace", "follow shot"),
         "track_left": ("track left alongside {t}, matching the pace", "track left"),
         "track_right": ("track right alongside {t}, matching the pace", "track right"),
         "orbit": ("orbit around {t}", "orbit"), "crane_up": ("crane up over {t}", "crane up"),
         "crane_down": ("crane down toward {t}", "crane down"),
         "handheld": ("handheld camera following {t}", "handheld camera"),
         "dolly_zoom": ("dolly zoom on {t}: {t} keeps the same size while the background stretches away", "dolly zoom")}
SHAKE = {"light": "with a light natural shake", "moderate": "with a moderate shake", "strong": "with a strong shake"}
SIZE_TERM = re.compile(r"(extreme wide|medium wide|wide|medium)(?![\w-])(?!\s*close)", re.I)   # словник розмірів §2.4
STATIC_TEXT = re.compile(r"\b(static|locked[- ]off|tripod|very slow(ly)? push(es|ing)? in)\b", re.I)
HONORIFICS = {"Don", "Doña", "Los", "Las", "El", "La"}
# сталі речення компілятора — лінт їх не чіпає (allow)
NO_BGM = "No BGM; only ambience and action sounds."          # §2.6: окремий рядок звуку, «No BGM» сам інколи програє
CONSTANTS = ("Single continuous shot, no cuts.", "The clip begins exactly at this moment.", STATIC, "No BGM.", NO_BGM,
             "there is no narration")
MODEL_UA = {"replicate:google/nano-banana-pro": "Nano Banana Pro",
            "replicate:google/nano-banana-2.1": "Nano Banana 2.1"}
_DARK = re.compile(r"\b(night|dark|darkness|flashlight|flashlights|moonlight|candle\w*|dim)\b", re.I)


# ---------------------------------------------------------------- дрібниці


def _strip(s: str | None) -> str:
    """Без крапки в кінці — для «Light: …», «End state: …»."""
    return (s or "").strip().rstrip(".").strip()


def _sent(s: str | None) -> str:
    """Речення з крапкою в кінці (якщо немає . ! ? « " … »)."""
    s = (s or "").strip()
    return s if not s or s[-1] in '.!?"”…' else f"{s}."


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _en(data: Data, key: str):
    try:
        return data.en[key]
    except KeyError:
        raise PromptError(f"prompt_en.yaml: немає ключа «{key}» (англійський шар v2, DESIGN §6)") from None


def _gender(who: str) -> tuple[str, str, str]:
    w = (who or "").lower()
    if re.search(r"\bwoman\b", w):
        return "woman", "She", "her"
    if re.search(r"\bman\b", w):
        return "man", "He", "his"
    return "person", "They", "their"


def _dark(time: str | None, light: str | None) -> bool:
    """Нічна / темна сцена → «чиста темрява» (style.low_light)."""
    return time == "night" or bool(_DARK.search(light or ""))


def producer_id(data: Data, ref: str) -> str:
    """Референс кастингу → id елемента, що його робить: mateo.three_quarter → cast-mateo-34, mina.tunnel →
    loc-mina-tunnel."""
    owner, _, what = ref.partition(".")
    if owner in data.locations:
        return f"loc-{owner}" if what == "plate" else f"loc-{owner}-{what}"
    suffix = {"front": "front", "three_quarter": "34", "profile": "profile", "full_body": "full"}.get(what)
    return f"cast-{owner}-{suffix or re.sub(r'^emotion(\d+)$', r'emo\1', what)}"


# ---------------------------------------------------------------- ручні поверхні


def _route_manual(route: str) -> dict:
    m = providers.route(route).manual
    return {k: m[k] for k in ("surface", "url", "how", "endpoint") if m.get(k)}


def _image_manual(route: str, body: dict, refs: list[str], who: dict[str, str]) -> dict:
    """AI Studio тією самою моделлю, що в маршруті; dropshot Image — це Nano Banana Pro: еталон лише для якорів (Pro),
    для решти — чернетка, бо в журнал має йти та модель, яку потім шле автоматика (§1.9)."""
    pro = route == ANCHOR_ROUTE
    slots = "; ".join(f"Image {n} = {ref} (результат «{who[ref]}»)" for n, ref in enumerate(refs, 1))
    how = (f"Google AI Studio — модель {MODEL_UA.get(route, route)} "
           + ("(або dropshot AI Studio → Image → Nano Banana Pro). " if pro else
              "(dropshot Image — це Nano Banana Pro, інша модель: лише чернетка, у журнал не як еталон). ")
           + (f"Прикріпи файли строго в цьому порядку: {slots}. " if refs else "Без референсів — лише текст. ")
           + f"Встав промпт без змін; співвідношення {body.get('aspect_ratio')}, роздільність "
           f"{body.get('resolution')}. "
           "Сіда немає — 2–3 спроби, найкращу запиши в журнал (`uv run fabrica lab log <id> --file …`).")
    return {"surface": "AI Studio / Gemini" + (" · dropshot Image" if pro else ""), "url": "https://aistudio.google.com",
            "how": how}


def _dropshot_manual(profile: dict, body: dict, start: tuple[str, str] | None, end: tuple[str, str] | None) -> dict:
    def file(x: tuple[str, str]) -> str:
        last = " — його останній кадр" if x[0].endswith(".last") else ""
        return f"результат «{x[1]}»{last} (референс {x[0]})"

    mode = (f"Video → Seedance 2.5 → Frame to Video. Start frame: завантаж {file(start)}"
            + (f"; End frame: {file(end)}" if end else "") + "." if start
            else "Video → Seedance 2.5, без стартового кадру (лише текст).")
    how = (f"{mode} Встав промпт у єдине текстове поле (окремого негативу немає — потрібні заперечення вже в промпті). "
           f"Налаштування: 16:9 · {body.get('duration')}s · {body.get('resolution')} · With Audio "
           f"{'ON' if body.get('generate_audio', True) else 'OFF'} · Draft OFF (Draft ON — дешевший перегляд 480p). "
           "Generate Video; скачай результат і запиши в журнал (`uv run fabrica lab log <id> --file …`).")
    out = {"surface": profile["surface"], "url": profile.get("url", ""), "how": how}
    if body.get("use_virtual_avatar"):
        out["note"] = ("Обличчя в кадрі: dropshot може відхилити (фільтр облич Seedance) — якщо так, маршрут Cloudflare "
                       "нижче (use_virtual_avatar).")
    return out


def _voice_manual(route: str, body: dict) -> dict:
    r = providers.route(route)
    has_path = any(s.get("in") == "path" for s in r.fields.values())
    parts = providers.split(route, {**body, "voice_id": body.get("voice_id") or "{voice_id}"} if has_path else body)
    endpoint = r.manual.get("endpoint", "")
    for k, v in {**parts["path"], **parts["query"]}.items():
        endpoint = endpoint.replace("{" + k + "}", str(v))
    how = "Тіло запиту — рівно цей JSON; ключ — з оточення ELEVENLABS_API_KEY (заголовок xi-api-key)."
    if has_path and not body.get("voice_id"):
        how += (" voice_id ще немає: спершу голос (крок 4), потім впиши його в bible.yaml → voice.voice_id і "
                "перезбери пакет.")
    return {"surface": "ElevenLabs API (JSON)", "url": r.manual["url"], "endpoint": endpoint, "how": how,
            "body": json.dumps(parts["body"], ensure_ascii=False, indent=2)}


# ---------------------------------------------------------------- збірка елемента


def _allow(data: Data, kind: str) -> list[str]:
    if kind == "image":
        return list(data.en.get("image_rules") or [])
    if kind == "video":
        return list(data.en.get("video_constants") or []) + list(CONSTANTS)
    return []


def _make(data: Data, t: Template, ctx: dict, *, item_id: str, set_name: str, title: str, route: str, step: int,
          payload: dict | None = None, refs: list[str] | tuple = (), produces: str | None = None,
          needs: list[str] | None = None, extra: dict | None = None, warnings: list[str] | tuple = (),
          tags: set[str] | frozenset = frozenset(), footage: str | None = None,
          surfaces: Callable[[dict], list[dict]] | None = None) -> Item:
    """ctx → промпт (+ уроки, поки вміщаються) → payload → validate + lint → Item."""
    r = providers.route(route)
    found = lessons_mod.match(data.slug, t.kind, route, t.id, set(tags)) if t.kind in ("image", "video") else []
    warn = list(warnings)
    while True:
        prompt, _ = render(t, {**ctx, "lessons": [_sent(x["rule"]) for x in found]})
        if not (found and r.prompt_max_chars and len(prompt) > r.prompt_max_chars):
            break
        dropped = found.pop()
        warn.append(f"урок {dropped['id']} не вмістився: промпт > {r.prompt_max_chars} символів")
    body = ({r.prompt_field: prompt} if r.prompt_field else {}) | dict(payload or {})
    body |= {k: v for k, v in {**t.payload, **t.route_payload.get(route, {})}.items() if k not in body}
    warn += providers.validate(route, body)
    warn += lint_mod.lint(t.kind, prompt, allow=_allow(data, t.kind), footage=footage)
    manual = (surfaces(body) if surfaces else []) + [_route_manual(route)]
    params = {"tool": manual[0]["surface"], "route": route, "model": r.model,
              **{k: v for k, v in body.items() if k != r.prompt_field and k not in REF_FIELDS}}
    ex = dict(extra or {}) | {"manual": manual}
    if found:
        ex["lessons"] = [x["id"] for x in found]
    return Item(item_id, set_name, t.kind, title, t, prompt, "", params, list(refs), produces, ex,
                list(dict.fromkeys(warn)), step, route, body, list(refs) if needs is None else needs)


def _image(data: Data, t: Template, ctx: dict, *, refs: list[str], route: str, payload: dict | None = None,
           who: dict[str, str] | None = None, **kw) -> Item:
    """Зображення: image_input = «ref:<id>» у порядку слотів; інструкція AI Studio / dropshot Image."""
    who = {ref: (who or {}).get(ref) or producer_id(data, ref) for ref in refs}
    body = ({"image_input": [f"ref:{x}" for x in refs]} if refs else {}) | dict(payload or {})
    return _make(data, t, {"style": _en(data, "style"), "rules": _en(data, "image_rules"), **ctx}, refs=refs,
                 route=route, payload=body, surfaces=lambda b: [_image_manual(route, b, refs, who)], **kw)


# ---------------------------------------------------------------- кастинг


def character_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    """Герої: якір анфас лише текстом (крок 1, Pro); 3/4, профіль, повний зріст, емоції — якір як Image 1 (крок 2)."""
    t = templates["image.character"]
    items: list[Item] = []
    for cid, ch in data.characters.items():
        c = (data.en.get("characters") or {}).get(cid)
        if c is None:
            raise PromptError(f"prompt_en.yaml: немає персонажа «{cid}»")
        noun, pron, poss = _gender(c["who"])
        base = {"c": c, "name": ch["name"], "noun": noun, "pron": pron, "poss": poss, "emotion": ""}
        tags = {f"character:{cid}"}
        for view, suffix in CHAR_VIEWS:
            anchor = view == "front"
            items.append(_image(
                data, t, {**base, "view": view}, item_id=f"cast-{cid}-{suffix}", set_name="casting",
                title=f"{ch['name']} — {VIEW_UA[view]}", refs=[] if anchor else [f"{cid}.front"],
                produces=f"{cid}.{view}", step=STEP["identity" if anchor else "views"],
                route=ANCHOR_ROUTE if anchor else t.route,
                payload={"aspect_ratio": "2:3"} if view == "full_body" else None, tags=tags))
        for i, emotion in enumerate(c.get("emotions") or [], 1):
            items.append(_image(
                data, t, {**base, "view": "emotion", "emotion": emotion}, item_id=f"cast-{cid}-emo{i}",
                set_name="casting", title=f"{ch['name']} — емоція {i}", refs=[f"{cid}.front"],
                produces=f"{cid}.emotion{i}", step=STEP["views"], route=t.route, tags=tags))
    return items


def _face_of(data: Data, mid: str) -> str | None:
    """Чиє обличчя в учасника сімки: members.<id>.face_of або «= <Ім'я>» на початку dna в bible.yaml (Tomás = Mateo)."""
    own = ((data.en.get("members") or {}).get(mid) or {}).get("face_of")
    if own:
        return own
    m = re.match(r"\s*=\s*([^\s(,]+)", str(data.members.get(mid, {}).get("dna") or ""))
    if not m:
        return None
    return next((cid for cid, ch in data.characters.items() if ch["name"].split()[0] == m.group(1)), None)


def member_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    """Сімка 1994: якір (лише текстом, крок 1; з чужим обличчям — крок 2) і мокрий від якоря (крок 2)."""
    t = templates["image.member_1994"]
    states = data.en.get("states") or {}
    items: list[Item] = []
    for mid, member in data.members.items():
        m = (data.en.get("members") or {}).get(mid)
        if m is None:
            raise PromptError(f"prompt_en.yaml: немає учасника сімки «{mid}»")
        noun, pron, poss = _gender(m["who"])
        face = _face_of(data, mid)
        if face and face not in data.characters:
            raise PromptError(f"prompt_en.yaml: members.{mid}.face_of «{face}» — немає такого героя")
        ctx = {"m": m, "name": member["name"], "noun": noun, "pron": pron, "poss": poss, "wet": "",
               "face_of": data.characters[face]["name"] if face else ""}
        tags = {f"character:{mid}"} | ({f"character:{face}"} if face else set())
        refs = [f"{face}.front"] if face else []
        items.append(_image(
            data, t, {**ctx, "variant": "base"}, item_id=f"cast-{mid}-1994", set_name="casting",
            title=f"{member['name']} — 1994" + (f" (обличчя {data.characters[face]['name']})" if face else ""),
            refs=refs, produces=f"{mid}.1994", step=STEP["views" if face else "identity"],
            route=t.route if face else ANCHOR_ROUTE, tags=tags))
        wet, warn = m.get("wet"), []
        if not wet:
            wet = f"the same adult {noun}, {(states.get('wet') or {}).get('image') or 'soaked from head to toe'}"
            warn.append(f"prompt_en.yaml: у members.{mid} немає wet — взято states.wet")
        items.append(_image(
            data, t, {**ctx, "variant": "wet", "wet": _strip(wet)}, item_id=f"cast-{mid}-wet", set_name="casting",
            title=f"{member['name']} — мокрий", refs=[f"{mid}.1994"], produces=f"{mid}.wet", step=STEP["views"],
            route=t.route, tags=tags, warnings=warn))
    return items


def location_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    """Плити (лише текстом) і стани: того самого місця — Image 1 = плита; окремий кадр — з ref або без (крок 3)."""
    t = templates["image.location"]
    known = {f"{lid}.{v}" for lid in data.locations for v in ["plate", *(data.loc(lid).get("variants") or {})]}
    items: list[Item] = []
    for lid, loc in data.locations.items():
        for variant in [None, *(data.loc(lid).get("variants") or {})]:
            p = data.place(lid, variant)
            warn = []
            if p["ref"] and p["ref"] not in known:
                warn.append(f"prompt_en.yaml: {lid}.{variant} ref «{p['ref']}» — такого референсу немає; без нього")
                p["ref"] = None if p["replace"] else f"{lid}.plate"
            mode = ("plate" if variant is None else "variant" if not p["replace"] else
                    "related" if p["ref"] else "standalone")
            refs = [p["ref"]] if mode in ("variant", "related") else []
            ctx = {"mode": mode, "base": _strip(p["base"]), "change": _strip(p["change"]), "desc": _strip(p["desc"]),
                   "framing": _strip(p["framing"]), "same_view": p["framing"] == p["plate_framing"],
                   "light": _strip(p["light"]), "mood": _strip(p["mood"]), "rules": _empty_rules(data)}
            items.append(_image(
                data, t, ctx, item_id=f"loc-{lid}" + (f"-{variant}" if variant else ""), set_name="casting",
                title=f"{loc['name']} — {variant or 'плита'}", refs=refs, produces=f"{lid}.{variant or 'plate'}",
                step=STEP["locations"], route=t.route, warnings=warn,
                tags={f"location:{lid}"} | ({f"variant:{variant}"} if variant else set())))
    return items


def _voiced(data: Data) -> list[tuple[str, dict, str]]:
    """Хто має голос: усі герої + сімка й другорядні з voice_design (id, англійський опис, ім'я)."""
    out = [(cid, (data.en.get("characters") or {}).get(cid) or {}, ch["name"]) for cid, ch in data.characters.items()]
    for block, names in (("members", data.members), ("supporting", data.supporting)):
        out += [(pid, en, names.get(pid, {}).get("name", pid)) for pid, en in (data.en.get(block) or {}).items()
                if isinstance(en, dict) and en.get("voice_design")]
    return out


def voice_design_items(data: Data, templates: dict[str, Template]) -> list[Item]:
    """Голоси (ElevenLabs Voice Design, крок 4): опис в офіційному форматі + прев'ю героя іспанською."""
    t = templates["voice.design"]
    items: list[Item] = []
    for pid, en, name in _voiced(data):
        item_id, warn = f"cast-{pid}-voice", []
        desc = en.get("voice_design")
        if not desc:
            desc = en.get("voice") or f"Native Spanish (Mexico City). {name}."
            warn.append("prompt_en.yaml: немає voice_design (офіційний формат ElevenLabs) — взято voice")
        preview = (en.get("preview_es") or "").strip()
        body = ({"text": preview} if preview else {"auto_generate_text": True}) | {"seed": seed_for(item_id)}
        items.append(_make(data, t, {"description": _strip(desc) + "."}, item_id=item_id, set_name="casting",
                           title=f"{name} — голос (Voice Design)", route=t.route, step=STEP["voices"], payload=body,
                           produces=f"{pid}.voice", extra={"preview_es": preview}, warnings=warn,
                           tags={f"character:{pid}"}, surfaces=lambda b, r=t.route: [_voice_manual(r, b)]))
    return items


# ---------------------------------------------------------------- люди в кадрі


def _person(data: Data, pid: str) -> dict:
    """id → kind, ім'я (None для другорядних — лише текстом), tag (відео), desc (зовнішність для кадру без
    референсу)."""
    en = data.en
    for kind, block, names in (("character", "characters", data.characters), ("member", "members", data.members),
                               ("supporting", "supporting", data.supporting)):
        e = (en.get(block) or {}).get(pid)
        if isinstance(e, dict):
            look = "; ".join(e.get("dna") or []) or e.get("look") or ""
            body = "; ".join(x for x in (look, f"wearing {e['wardrobe']}" if e.get("wardrobe") else "") if x)
            desc = f"{e['who']}: {body}" if e.get("who") and body else e.get("who") or body
            return {"id": pid, "kind": kind, "name": names.get(pid, {}).get("name") if kind != "supporting" else None,
                    "tag": e.get("tag"), "desc": _strip(desc), "en": e}
    raise PromptError(f"prompt_en.yaml: немає персонажа «{pid}» (characters / members / supporting)")


def _ref_for(x: dict, p: S.Person) -> str | None:
    if p.view in ("blurred", "hidden") or x["kind"] == "supporting":
        return None
    if x["kind"] == "character":
        return f"{x['id']}.{VIEW_REF[p.view]}"
    return f"{x['id']}.{'wet' if 'wet' in p.state else '1994'}"


def _cast(data: Data, people: list[S.Person]) -> tuple[list[dict], list[str]]:
    """Люди в порядку слотів (зліва направо, далі без місця) з референсом за ракурсом; > 4 референсів — текстом."""
    out, over, n = [], [], 0
    for p in sorted(people, key=lambda p: SCREEN_ORDER[p.screen]):
        x = {**_person(data, p.id), "p": p}
        x["ref"] = _ref_for(x, p)
        if x["ref"] and n >= MAX_PEOPLE_REFS:
            x["ref"], x["over"] = None, True
            over.append(x["name"] or p.id)
        elif x["ref"]:
            n += 1
        out.append(x)
    warn = [f"людей з референсом більше {MAX_PEOPLE_REFS} (nano-banana-2.1): {', '.join(over)} — описано текстом; "
            "краще ≤ 4 людей у кадрі або проміжний кадр"] if over else []
    warn += [f"prompt_en.yaml: немає tag у «{x['id']}» — у відео «the person»" for x in out if not x["tag"]]
    return out, warn


def _tag(x: dict) -> str:
    return _strip(x["tag"]) or "the person"


def _state_image(data: Data, x: dict) -> list[str]:
    states = data.en.get("states") or {}
    wet_ref = (x.get("ref") or "").endswith(".wet")                      # мокрий референс уже показує стан
    return [_strip(states[s]["image"]) for s in x["p"].state if s in states and not (s == "wet" and wet_ref)]


def _image_blocking(data: Data, x: dict) -> str | None:
    """Речення про людину в кадрі: де, як повернута, куди дивиться, стан; без референсу — ще й як виглядає."""
    p = x["p"]
    parts = [SCREEN[p.screen]] if p.screen else []
    if p.view != "face" or p.screen:
        parts.append(VIEW_IMAGE[p.view])
    if p.facing:
        parts.append(p.facing if re.match(r"(facing|looking|turned)\b", p.facing) else f"facing {p.facing}")
    states = _state_image(data, x)
    if x["ref"]:
        who = x["name"]
    elif x.get("over"):
        who = f"{x['name'] or _tag(x)} ({x['desc']})"
    else:
        who = _tag(x) if p.view in ("blurred", "hidden") else x["desc"] or _tag(x)
    if x["ref"] and not parts and not states:
        return None
    body = f"{_cap(who)} is {', '.join(parts or ['in the frame'])}"
    return _sent(body + (f"; {'; '.join(states)}" if states else ""))


def _shot_size(size: str | None) -> str:
    """«medium» → «medium shot», «wide, seen from the doorway» → «wide shot, seen from the doorway»; «shot» уже є,
    «close-up» чи вільний текст без розміру на початку («handheld point of view») — як є."""
    s = (size or "").strip()
    m = None if re.search(r"\bshot\b", s, re.I) else SIZE_TERM.match(s)
    return f"{s[:m.end()]} shot{s[m.end():]}" if m else s


def _still_camera(cam: S.Camera) -> str:
    """Камера кадру — лише статика: розмір, кут, об'єктив."""
    return ", ".join(x for x in (_shot_size(cam.size), cam.angle, f"{cam.lens_mm}mm lens" if cam.lens_mm else "") if x)


def _tags(spec: S.ShotSpec) -> set[str]:
    out = {f"location:{spec.location}", f"set:{spec.set}", f"tier:{spec.tier}", f"mode:{spec.mode}"}
    out |= {f"character:{p.id}" for p in spec.people}
    out |= {f"{k}:{v}" for k, v in (("footage", spec.footage), ("beat", spec.beat), ("variant", spec.variant)) if v}
    return out


# ---------------------------------------------------------------- кадри


def _empty_rules(data: Data) -> list[str]:
    """Правила кадру без людей: image_rules_empty з prompt_en, інакше image_rules без речень про людей і руки
    (у порожньому кадрі «руки» й «кожна людина доросла» підказують моделі домалювати людину)."""
    own = data.en.get("image_rules_empty")
    if own:
        return list(own)
    return [r for r in _en(data, "image_rules") if not re.search(r"\b(people|person|hands?|adult)\b", r, re.I)]


def _frame(spec: S.ShotSpec, data: Data, t: Template, which: str) -> Item:
    place = data.place(spec.location, spec.variant, spec.light)
    loc_ref = f"{spec.location}.{spec.variant}" if spec.variant else f"{spec.location}.plate"
    from_frame = which == "last" and spec.handoff != "continue"
    first = spec.frame_ref if from_frame else loc_ref
    cast, warn = _cast(data, spec.people)
    people = [x for x in cast if x["ref"]]
    refs = [first] + [x["ref"] for x in people]
    slots = ["Image 1 is the first frame of this shot: keep the place, the camera position, the framing and the light "
             "exactly; only what this description changes is different." if from_frame else
             f"Image 1 is the location: {_strip(place['desc'])}. Keep its architecture, materials, colours and objects as "
             "in Image 1; the camera position, framing and light come from this description."]
    if people:
        slots.append(_sent("; ".join(f"Image {n} is {x['name']}, {_tag(x)}" for n, x in enumerate(people, 2))))
    style = data.en["style"]
    ctx = {"which": which, "footage": spec.footage, "slots": slots, "bind": bool(people),
           "rules": _en(data, "image_rules") if cast else _empty_rules(data),
           "scene": _sent(spec.frame if which == "first" else spec.end_frame),
           "blocking": [b for x in cast if (b := _image_blocking(data, x))],
           "continuity": [_strip(c) for c in spec.continuity], "light": _strip(place["light"]),
           "low_light": style["low_light"]["image"] if _dark(spec.time, place["light"]) else "",
           "camera": _still_camera(spec.camera),
           "style": (style.get("image_footage") or {}).get(spec.footage, "") if spec.footage else style["image"]}
    who = {spec.frame_ref: f"{spec.prefix}-frame"} if from_frame else {}
    return _image(data, t, ctx, item_id=f"{spec.prefix}-{'frame' if which == 'first' else 'end'}", set_name=spec.set,
                  title=f"{spec.title} — {'стартовий' if which == 'first' else 'кінцевий'} кадр", refs=refs,
                  produces=spec.frame_ref if which == "first" else spec.end_ref, step=STEP["frames"], route=t.route,
                  who=who, warnings=spec.warnings + warn, tags=_tags(spec),
                  extra={"shot": spec.id, "tier": spec.tier, "face": spec.face, "which": which,
                         "success": spec.success})


def frame_items(spec: S.ShotSpec, data: Data, templates: dict[str, Template]) -> list[Item]:
    """Стартовий кадр (не для handoff continue) + кінцевий кадр для first_last (крок 5); mode none — []."""
    if spec.mode == "none":
        return []
    t = templates["image.start_frame"]
    out = [_frame(spec, data, t, "first")] if spec.handoff != "continue" else []
    return out + ([_frame(spec, data, t, "last")] if spec.mode == "first_last" else [])


# ---------------------------------------------------------------- відео


def camera_sentence(cam: S.Camera) -> str:
    """Один рух: ціль, швидкість, кінцева точка (+ одна текстура трясіння); static — замок штатива (§2.4)."""
    if cam.text:
        text = _strip(cam.text)
        return _sent(text if text.lower().startswith("camera") else f"Camera: {text}")
    if cam.move == "static":
        return STATIC if cam.shake == "none" else f"Camera: handheld, holding the framing in place, {SHAKE[cam.shake]}."
    if cam.move == "rack_focus":
        t = cam.target or "the background"
        return (f"Rack focus: the focus shifts smoothly from the foreground to {t}; the foreground becomes blurred "
                f"while {t} gradually becomes clear.")
    with_t, bare = MOVES[cam.move]
    speed = cam.speed or ("" if cam.move in ("handheld", "dolly_zoom") else "slow")
    s = f"Camera: {speed + ' ' if speed else ''}{with_t.format(t=cam.target) if cam.target else bare}"
    if cam.endpoint:
        s += f", ending on {_strip(cam.endpoint)}"
    if cam.shake != "none":
        s += f", {SHAKE[cam.shake]}"
    return f"{s}."


def _people_line(cast: list[dict], size: str | None) -> str:
    """Розстановка тегами (без зовнішності): «Blocking: medium shot; the woman in … on the left, facing the camera»."""
    who = [f"{_tag(x)} {SCREEN[x['p'].screen] + ', ' if x['p'].screen else ''}{VIEW_VIDEO[x['p'].view]}" for x in cast]
    head = _shot_size(size)
    return _sent("Blocking: " + "; ".join(x for x in [head, *who] if x)) if who or head else ""


# Дія, де рот відкритий (крик, сміх, плач …): «рот закритий» тоді суперечив би дії — не пишемо його.
_OPEN_MOUTH = re.compile(r"\b(scream\w*|shout\w*|yell\w*|laugh\w*|giggl\w*|gasp\w*|sob\w*|cr(?:y|ies|ying)|"
                         r"whisper\w*|talk\w*|speak\w*|mouth (?:opens?|open|falls open|wide)|open mouth|jaw drops)\b", re.I)


def _sound(spec: S.ShotSpec, cast: list[dict], first: bool, action: str = "") -> list[str]:
    """Репліки (§2.6: мова й акцент перед кожною), роти, звуки; «No BGM» дописує шаблон.

    on_screen — lip-sync «says only this line, once»; за кадром (offscreen або мовця немає в кадрі) — голос за
    кадром; мовець у кадрі без lip-sync (спиною, has_dialogue_visible ні) — говорить він, а не «голос за кадром»."""
    tags = {x["id"]: _tag(x) for x in cast}
    lines = spec.lines if first else []
    out, speaks = [], False
    for ln in lines:
        how = DELIVERY_VIDEO.get(ln.delivery, DELIVERY_VIDEO["normal"])
        if ln.on_screen:
            out.append(f'{_cap(ACCENT)}, {how}, {tags.get(ln.speaker, "the speaker")} says only this line, once: '
                       f'"{ln.text_es}"')
        elif ln.offscreen or ln.speaker not in tags:
            out.append(f'An off-screen voice, {ACCENT}, {how}, says: "{ln.text_es}"')
            continue
        else:
            out.append(f'{_cap(ACCENT)}, {how}, {tags[ln.speaker]} says: "{ln.text_es}"')
        speaks = True
    if speaks:
        others = "; everyone else keeps their mouth closed." if len(cast) > 1 else "."
        out.append(f"Then the speaker's lips close{others}")
    elif cast and not _OPEN_MOUTH.search(action):
        out.append("Everyone in the frame keeps their mouth naturally closed" + ("." if lines else
                                                                                   "; there is no narration."))
    elif cast:
        out.append("" if lines else "There is no narration.")
    else:
        out.append("There is no narration." if not lines else "")
    noise = (spec.sound.sfx if first else []) + spec.sound.ambience
    if noise:
        out.append(f"Sound: {'; '.join(_strip(x) for x in noise)}.")
    return [x for x in out if x]


def _lock(data: Data, cast: list[dict], placed: bool = False) -> str:
    """Замок (§2.2 A, рядок 8): місце на екрані, обличчя / волосся / одяг, стани (video-фраза), місце.
    placed — місця вже названо в Blocking (маршрут з обличчям): для 2+ людей одна фраза замість переліку (ліміт 2000)."""
    states = data.en.get("states") or {}
    on_screen = [x for x in cast if x["p"].screen]
    if placed and len(on_screen) > 1:
        parts = ["everyone keeps their place in the frame"]
    else:
        parts = [f"{_tag(x)} stays {SCREEN[x['p'].screen]}" for x in on_screen]
    if cast:
        parts.append("faces, hair and clothing stay exactly as in the image")
    by_state: dict[str, list[str]] = {}            # той самий стан у кількох людей — одна фраза (ліміт 2000 знаків)
    for x in cast:
        for st in x["p"].state:
            if st in states:
                by_state.setdefault(st, []).append(_tag(x))
    for st, tags in by_state.items():
        phrase = _strip(states[st]["video"])
        if len(cast) == 1:
            parts.append(phrase)
        else:
            who = tags[0] if len(tags) == 1 else ", ".join(tags[:-1]) + " and " + tags[-1]
            parts.append(f"for {who}: {phrase}")
    parts.append("the place and its layout stay exactly as in the image")
    return _sent(_cap("; ".join(parts)))


def _preserve(cast: list[dict]) -> str:
    tags = ", ".join(_tag(x) for x in cast)
    return (f"the faces, hair and clothing of {tags}, " if cast else "") + "the light and the layout of the place"


def _line_warnings(spec: S.ShotSpec, cast: list[dict], cam: S.Camera) -> list[str]:
    """Репліки — лише в кліпі 1, тож і камера — кліпу 1; мовець анфас / 3/4 / профіль без on_screen."""
    warn = []
    if any(ln.on_screen for ln in spec.lines):
        slow_push = cam.move == "push_in" and (cam.speed or "").startswith("very slow")
        if (cam.text and not STATIC_TEXT.search(cam.text)) or (not cam.text and not (cam.move == "static" or slow_push)):
            warn.append("репліка в кадрі → камера static або push_in very slow (§6.2 п.4), а тут "
                        f"«{cam.text or cam.move}»")
    views = {x["id"]: x["p"].view for x in cast}
    for ln in spec.lines:
        if not ln.on_screen and not ln.offscreen and views.get(ln.speaker) in S.LIPS:
            warn.append(f"мовець «{ln.speaker}» у кадрі (view {views[ln.speaker]}), а репліка не on_screen — "
                        f"lines.{ln.n}.on_screen або поверни спиною")
    return warn


def _appearance(prompt: str, cast: list[dict]) -> list[str]:
    """Правило 2: відео не повторює зовнішність (ДНК / look / who) — лише tag."""
    low = prompt.lower()
    found = []
    for x in cast:
        e = x["en"]
        for s in [*(e.get("dna") or []), *re.split(r",\s*", e.get("look") or ""), e.get("who") or ""]:
            s = _strip(s).lower()
            if len(s) >= 15 and s in low and s not in _tag(x).lower():
                found.append(s)
    return [f"відео переописує зовнішність «{s}» — у відео лише tag (обличчя й одяг тримає кадр)"
            for s in dict.fromkeys(found)]


def _names(data: Data, prompt: str) -> list[str]:
    """Правило 2 / §6: Seedance не знає імен — ім'я героя чи учасника сімки поза репліками в лапках → попередження."""
    text = re.sub(r'"[^"]*"|“[^”]*”', " ", prompt)
    words = dict.fromkeys(w for who in (*data.characters.values(), *data.members.values())
                          for w in re.findall(r"[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñü]+", str(who.get("name") or ""))
                          if w not in HONORIFICS)
    found = [w for w in words if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)]
    return [f"відео називає «{w}» — Seedance не знає імен, пиши tag" for w in found]


def _state_out(data: Data, cast: list[dict], spec: S.ShotSpec, end_state: str | None) -> list[str]:
    """§12: стан на кінці шоту — кінцевий стан кліпу, стани людей (video-фраза: кров з носа …), continuity."""
    states = data.en.get("states") or {}
    people = [f"{_tag(x)}: {_strip(states[s]['video'])}" for x in cast for s in x["p"].state if s in states]
    return list(dict.fromkeys(x for x in [_strip(end_state), *people, *map(_strip, spec.continuity)] if x))


def video_items(spec: S.ShotSpec, data: Data, templates: dict[str, Template], *, profile: dict | None = None,
                prev: tuple[str, ...] | None = None) -> list[Item]:
    """Відео шоту — по елементу на кліп (§12, крок 6). prev = (референс «….last», id елемента[, маршрут]) останнього
    кліпу попереднього шоту — для handoff continue.

    Маршрут — на кліп: є стартовий кадр і (face clear або старт — кадр кліпу з маршруту з обличчям: на ньому може бути
    обличчя, Replicate дасть E005) → Cloudflare з use_virtual_avatar; t2v (без кадру) обличчя не фільтрує → Replicate.
    """
    if spec.mode not in S.VIDEO_MODES:
        return []
    profile = profile or providers.generation()
    i2v = templates["video.i2v"]
    res = profile.get("resolution") or (profile.get("resolution_by_tier") or {}).get(spec.tier, "480p")
    place = data.place(spec.location, spec.variant, spec.light)
    light = _strip(place["light"])
    cast, cast_warn = _cast(data, spec.people)
    style = data.en["style"]
    dot, base_id = spec.prefix.replace("-", "."), f"{spec.prefix}-{spec.video_id}"
    plan = S.clips(spec, profile)
    shot_warn = spec.warnings + cast_warn + (
        ["face clear без людей у people — маршрут з обличчям без потреби"] if spec.face == "clear" and not spec.people
        else [])
    items: list[Item] = []
    for c in plan:
        item_id = base_id if c.index == 1 else f"{base_id}-{c.index}"
        warn = list(c.warnings) + (_line_warnings(spec, cast, c.camera) if c.index == 1 else [])
        start: tuple[str, str] | None = None
        start_route = ""
        if c.start == "frame":
            start = (spec.frame_ref, f"{spec.prefix}-frame")
        elif c.start == "prev_last":
            if c.index > 1:
                start, start_route = (f"{dot}.c{c.index - 1}.last", items[-1].id), items[-1].route
            elif prev:
                start, start_route = (prev[0], prev[1]), prev[2] if len(prev) > 2 else ""
            else:
                start = (spec.frame_ref, f"{spec.prefix}-frame")
                warn.append("handoff continue без попереднього кліпу — старт зі стартового кадру шоту")
        end = (spec.end_ref, f"{spec.prefix}-end") if spec.mode == "first_last" and c.index == c.of else None
        t = templates["video.t2v"] if start is None else templates["video.first_last"] if end else i2v
        route = FACE_ROUTE if start and (spec.face == "clear" or start_route == FACE_ROUTE) else i2v.route
        # промпт не залежить від профілю (рішення 07.10: golden = те саме, що надішле автомат): маршрут з обличчям
        # (Cloudflare use_virtual_avatar — кадр задає обличчя, а не композицію) або без кадру — склад словами
        loose = start is None or route == FACE_ROUTE
        size = c.camera.size or spec.camera.size
        blocking = _people_line(cast, size) if loose else ""
        ctx = {"clean_head": style["low_light"]["video"] if _dark(spec.time, light) else "",
               "footage": (style.get("video_footage") or {}).get(spec.footage, "") if spec.footage else "",
               "blocking": blocking,
               "continuity": [_strip(x) for x in spec.continuity if _strip(x)] if loose else [],
               "action": _sent(c.action), "end_state": _strip(c.end_state), "camera": camera_sentence(c.camera),
               "light": light, "sound": _sound(spec, cast, c.index == 1, c.action or ""),
               "lock": _lock(data, cast, placed=bool(blocking)),
               "preserve": _preserve(cast), "constants": [_sent(x) for x in _en(data, "video_constants")],
               "size": _shot_size(size) or _strip(place["framing"]),
               "place": _strip(place["desc"]), "style": "" if spec.footage else _sent(style.get("video"))}
        body = {"image": f"ref:{start[0]}"} if start else {}
        body |= ({"last_frame_image": f"ref:{end[0]}"} if end else {}) | {
            "duration": c.gen_s, "resolution": res, "seed": seed_for(item_id)}
        refs = [x[0] for x in (start, end) if x]
        keep = c.window[1] - c.window[0]
        extra = {"shot": spec.id, "tier": spec.tier, "face": spec.face, "mode": spec.mode,
                 "edit_window": f"кліп {c.gen_s} с → у монтаж {keep:g} с ({c.window[0]:g}–{c.window[1]:g} с)",
                 "clip": {"index": c.index, "of": c.of, "gen_s": c.gen_s, "window": list(c.window), "start": c.start,
                          "start_ref": start[0] if start else None, "start_item": start[1] if start else None},
                 "success": spec.success}
        if c.index == c.of:
            extra["state_out"] = _state_out(data, cast, spec, c.end_state)
        title = f"{spec.title} — відео" + (f" ({spec.video_id})" if spec.video_id != "video" else "") + (
            f" · кліп {c.index}/{c.of}" if c.of > 1 else "")
        item = _make(data, t, ctx, item_id=item_id, set_name=spec.set, title=title, route=route, step=STEP["video"],
                     payload=body, refs=refs, produces=f"{dot}.c{c.index}", extra=extra, warnings=shot_warn + warn,
                     tags=_tags(spec), footage=spec.footage,
                     surfaces=lambda b, s=start, e=end: [_dropshot_manual(profile, b, s, e)] if profile.get("surface")
                     else [])
        if len(item.prompt) > VIDEO_TARGET:
            item.warnings.append(f"промпт {len(item.prompt)} символів — ціль ≤ {VIDEO_TARGET} (ліміт маршруту 2000)")
        item.warnings += _appearance(item.prompt, cast) + _names(data, item.prompt)
        items.append(item)
    return items


# ---------------------------------------------------------------- репліки


def _voice_id(data: Data, pid: str | None) -> str | None:
    """voice_id із bible.yaml; ще немає — None (поле не кладемо: голос — needs «<id>.voice», крок 4)."""
    for names in (data.characters, data.members, data.supporting):
        if pid in names and (names[pid].get("voice") or {}).get("voice_id"):
            return names[pid]["voice"]["voice_id"]
    return None


def line_items(spec: S.ShotSpec, data: Data, templates: dict[str, Template]) -> list[Item]:
    """Репліки шоту (ElevenLabs eleven_v4, крок 7): «[тег манери] текст», лише stability + similarity_boost, es, сід."""
    t = templates["voice.line"]
    dot = spec.prefix.replace("-", ".")
    items: list[Item] = []
    for ln in spec.lines:
        if ln.voice == "native":           # голос — рідний звук Seedance у кліпі (одноразова репліка VHS)
            continue
        item_id = f"{spec.prefix}-voice{ln.n}"
        s = t.settings.get(ln.delivery) or t.settings["normal"]
        vid = _voice_id(data, ln.speaker)
        body = ({"voice_id": vid} if vid else {}) | {
            "voice_settings": {"stability": s["stability"], "similarity_boost": s["similarity_boost"]},
            "seed": seed_for(item_id)}
        warn = [] if ln.speaker else ["репліка без мовця (character_id) — голос невідомий"]
        items.append(_make(
            data, t, {"tag": s.get("tag") or "", "text": ln.text_es}, item_id=item_id, set_name=spec.set,
            title=f"{spec.title} — репліка {ln.n}", route=t.route, step=STEP["lines"], payload=body,
            produces=f"{dot}.voice{ln.n}", needs=[f"{ln.speaker}.voice"] if ln.speaker else [], warnings=warn,
            extra={"shot": spec.id, "character": ln.speaker, "line_id": ln.line_id, "delivery": ln.delivery,
                   "delivery_source": ln.delivery_source, "on_screen": ln.on_screen, "offscreen": ln.offscreen},
            surfaces=lambda b, r=t.route: [_voice_manual(r, b)]))
    return items


# ---------------------------------------------------------------- набір шотів


def spec_items(specs: list[S.ShotSpec], data: Data, templates: dict[str, Template],
               profile: dict | None = None) -> list[Item]:
    """Шоти по порядку → кадри, кліпи, репліки. handoff continue бере останній кліп попереднього шоту; якщо його
    немає (попередній шот без відео) — новий стартовий кадр і попередження. state_out останнього шоту з відео тієї ж
    сцени → extra.state_in стартового кадру й кліпу 1 (§12: показати на картці; у prompt_sha не входить)."""
    profile = profile or providers.generation()
    items: list[Item] = []
    prev: tuple[str, str, str] | None = None
    carry: tuple[str | None, list[str]] = (None, [])
    for spec in specs:
        if spec.handoff == "continue" and prev is None:
            spec = spec.model_copy(update={"handoff": "cut", "warnings": spec.warnings + [
                "handoff continue, але попередній шот без відео — новий стартовий кадр (cut)"]})
        frames, videos = frame_items(spec, data, templates), video_items(spec, data, templates, profile=profile,
                                                                         prev=prev)
        if spec.scene_id and carry[0] == spec.scene_id and carry[1]:
            for it in frames[:1] if frames and frames[0].extra.get("which") == "first" else []:
                it.extra["state_in"] = list(carry[1])
            for it in videos[:1]:
                it.extra["state_in"] = list(carry[1])
        items += frames + videos + line_items(spec, data, templates)
        prev = (f"{videos[-1].produces}.last", videos[-1].id, videos[-1].route) if videos else None
        if videos:
            carry = (spec.scene_id, videos[-1].extra.get("state_out") or [])
    return items
