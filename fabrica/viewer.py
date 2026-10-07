"""Пакет лабораторії промптів: prompts/out/<slug>/<набір>/ → <елемент>.md, index.html (переглядач), manifest.json.

HTML — один самодостатній файл для телевізора (і телефона): темна тема, великий шрифт. Картки згруповано за
кроками виробництва (prompts.STEPS: що робити, чим, коли готово). На картці: маршрут (+ «обличчя → Cloudflare»),
payload — рівно те тіло, яке отримає API (кнопка «копіювати»), референси в порядку слотів (стартовий кадр,
Image 1…n) зі станом «є ≥ 4 / golden / ще немає — спершу крок N» і файлом, який вантажити (той самий, що бере
lab.ref_file), ручні інструкції для кожної поверхні (endpoint, тіло, команди), кліп і вікно монтажу, стан із
попереднього шоту (§12), попередження окремо API / lint / дані, нотатки (у браузері) і команда `fabrica lab log …`.
"""

from __future__ import annotations

import dataclasses
import html
import json
import os
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from urllib.parse import quote

from fabrica import config
from fabrica import lab as lab_mod
from fabrica import lessons as lessons_mod
from fabrica import prompts as prompts_mod
from fabrica import providers as providers_mod

IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO = {".mp4", ".mov", ".webm"}
AUDIO = {".mp3", ".wav", ".m4a", ".ogg"}
KIND_UA = {"image": "фото", "video": "відео", "voice": "голос"}
TOOLS = ["dropshot", "gemini", "ai-studio", "nano-banana", "replicate", "cloudflare", "elevenlabs", "dreamina",
         "syntx", "other"]
# підрядок у назві поверхні → інструмент журналу (береться той, що стоїть у назві найраніше)
TOOL_NEEDLES = (("dropshot", "dropshot"), ("ai studio", "ai-studio"), ("gemini", "gemini"), ("dreamina", "dreamina"),
                ("replicate", "replicate"), ("cloudflare", "cloudflare"), ("elevenlabs", "elevenlabs"))
WARN_GROUPS = (("API", "API: "), ("lint", "lint: "), ("дані", ""))
# слоти payload у порядку, в якому людина прикріплює файли: (поле, підпис; список → «Image 1…n»)
SLOT_FIELDS = {"image": "стартовий кадр", "last_frame_image": "кінцевий кадр", "image_input": "Image",
               "reference_images": "Image", "reference_videos": "Video", "reference_audios": "Audio",
               "video": "відео", "audio": "аудіо"}
STATE_CLASS = {"golden": "golden", "ok": "ok", "nofile": "weak", "weak": "weak", "clip": "missing", "missing": "missing"}
CLIP_START = {"frame": "старт: стартовий кадр", "prev_last": "старт: останній кадр попереднього кліпу",
              "prev_shot": "старт: останній кадр попереднього шоту", "none": "старт: без кадру (лише текст)"}
CLIP_SKIP = {"index", "of", "total", "count", "gen_s", "window", "start", "start_ref", "start_item", "action",
             "end_state", "camera"}
NO_LOCAL = "файлу немає на цьому комп'ютері"

# Запасна таблиця кроків (DESIGN §1), якщо prompts.STEPS немає; done — «готово, коли», якщо todo цього не каже.
STEPS_DEFAULT = [
    {"step": 1, "key": "identity", "title": "Ідентичність — якорі",
     "todo": "анфас кожного героя й портрет кожного з сімки 1994 — лише текст, без референсів",
     "tool": "Nano Banana Pro (Replicate / AI Studio)",
     "done": "у кожного якоря є результат ≥ 4, найкращий затверджено (`fabrica lab approve`)"},
    {"step": 2, "key": "views", "title": "Ракурси, емоції, мокрі",
     "todo": "3/4, профіль, повний зріст, емоції, мокрий стан — Image 1 = якір із кроку 1",
     "tool": "Nano Banana 2.1 (Replicate / AI Studio)", "done": "те саме обличчя в усіх ракурсах, оцінка ≥ 4"},
    {"step": 3, "key": "locations", "title": "Локації",
     "todo": "плита кожної локації, потім її стани (стан того ж місця — Image 1 = плита)",
     "tool": "Nano Banana 2.1 (Replicate / AI Studio)", "done": "плита й стани з оцінкою ≥ 4, без людей і написів"},
    {"step": 4, "key": "voices", "title": "Голоси",
     "todo": "Voice Design: опис голосу + текст прев'ю, обрати найкраще прев'ю",
     "tool": "ElevenLabs Voice Design", "done": "голос збережено в ElevenLabs, voice_id вписано в bible.yaml"},
    {"step": 5, "key": "frames", "title": "Стартові кадри",
     "todo": "кадр першої миті шоту: Image 1 = локація, далі люди зліва направо",
     "tool": "Nano Banana 2.1 (Replicate / AI Studio)", "done": "композиція, ракурси й стани як в описі, оцінка ≥ 4"},
    {"step": 6, "key": "video", "title": "Відео — кліпи",
     "todo": "кліп зі стартового кадру (кліп 2+ — з останнього кадру попереднього); у монтаж іде лише вікно",
     "tool": "dropshot AI Studio → Seedance 2.5 · Frame to Video (обличчя → Cloudflare)",
     "done": "рух і звук як в описі, без склейок і написів, оцінка ≥ 4; останній кадр витягнуто"},
    {"step": 7, "key": "lines", "title": "Репліки",
     "todo": "кожна репліка голосом персонажа в потрібній манері",
     "tool": "ElevenLabs (eleven_v4)", "done": "текст слово в слово, манера як треба, оцінка ≥ 4"},
]
NO_STEP = {"step": 0, "key": "other", "title": "Без кроку", "todo": "елементи без кроку виробництва (старий формат)",
           "tool": "", "done": ""}


# ---------------------------------------------------------------- кроки, слоти, попередження


def _as_dict(s) -> dict:
    if isinstance(s, dict):
        return dict(s)
    if hasattr(s, "_asdict"):
        return s._asdict()
    if dataclasses.is_dataclass(s):
        return dataclasses.asdict(s)
    if isinstance(s, (tuple, list)):
        return dict(zip(("step", "key", "title", "todo"), s))
    return {}


def steps() -> dict[int, dict]:
    """Кроки виробництва: prompts.STEPS (Step(n, key, title, todo, tool), словники чи кортежі) поверх запасної таблиці.
    → {крок: {step, key, title, todo, tool, done}} за зростанням кроку. Номер — n / step, далі key, далі позиція.
    «Готово, коли» із запасної таблиці — лише якщо todo з prompts.STEPS цього ще не каже (одне джерело правди)."""
    out = {s["step"]: dict(s) for s in STEPS_DEFAULT}
    by_key = {s["key"]: s["step"] for s in STEPS_DEFAULT}
    raw = getattr(prompts_mod, "STEPS", None) or []
    for k, s in (list(raw.items()) if isinstance(raw, dict) else list(enumerate(raw, 1))):
        s = _as_dict(s)
        if isinstance(k, str):
            s.setdefault("key", k)
        n = next((s[f] for f in ("step", "n") if isinstance(s.get(f), int) and not isinstance(s[f], bool)), None)
        if n is None:
            n = by_key.get(s.get("key")) or (k if isinstance(k, int) else None)
        if n is None:
            continue
        s["todo"] = s.get("todo") or s.get("what") or s.get("human")
        s["tool"] = s.get("tool") or s.get("tools")
        base = out.get(n) or {"key": s.get("key") or f"step{n}", "title": f"Крок {n}", "todo": "", "tool": "", "done": ""}
        if s["todo"] and "готов" in str(s["todo"]).lower() and not s.get("done"):
            base = {**base, "done": ""}
        out[n] = {**base, **{f: v for f, v in s.items() if v not in (None, "") and f != "n"}, "step": n}
    return dict(sorted(out.items()))


def slots(item: prompts_mod.Item) -> list[tuple[str, str]]:
    """(підпис слоту, id референсу) у порядку payload: стартовий / кінцевий кадр, Image 1…n, Video …, Audio …;
    далі refs / needs, яких у payload немає (голос, елементи старого формату без payload → Image k)."""
    out: list[tuple[str, str]] = []
    payload = item.payload or {}
    fields = [f for f in SLOT_FIELDS if f in payload] + [f for f in payload if f not in SLOT_FIELDS]
    for f in fields:
        v = payload[f]
        refs = [x[4:] for x in (v if isinstance(v, list) else [v]) if isinstance(x, str) and x.startswith("ref:")]
        label = SLOT_FIELDS.get(f, f)
        out += [(f"{label} {i}" if isinstance(v, list) else label, r) for i, r in enumerate(refs, 1)]
    seen, legacy = {r for _, r in out}, not out
    for r in [*item.refs, *item.needs]:
        if r not in seen:
            seen.add(r)
            out.append((f"Image {len(out) + 1}" if legacy and r in item.refs else "потрібно", r))
    return out


def split_warnings(warnings: list[str]) -> dict[str, list[str]]:
    """Попередження → {"API": […], "lint": […], "дані": […]} без префіксів «API: » / «lint: »."""
    out: dict[str, list[str]] = {name: [] for name, _ in WARN_GROUPS}
    for w in warnings:
        name, prefix = next((n, p) for n, p in WARN_GROUPS if w.startswith(p))
        out[name].append(w[len(prefix):])
    return out


def manual(item: prompts_mod.Item) -> list[dict]:
    """Ручні інструкції для поверхонь (extra.manual: surface, url, endpoint, how, body …); немає — з каталогу
    маршрутів (surface, url, endpoint, how + payload)."""
    if item.extra.get("manual"):
        return [m if isinstance(m, dict) else {"surface": "", "text": str(m)} for m in item.extra["manual"]]
    if not item.route:
        return []
    try:
        m = providers_mod.route(item.route).manual or {}
    except providers_mod.ProviderError:
        return []
    return [{"surface": m.get("surface") or item.route, "title": "", "url": m.get("url"), "endpoint": m.get("endpoint"),
             "how": m.get("how"), "json": item.payload}] if m else []


def how_parts(text) -> list[tuple[bool, str]]:
    """how → [(команда?, текст)]: абзаци через порожній рядок; абзац із відступом (curl у providers.yaml) — команда,
    її копіюють окремо, а не з прозою."""
    return [(c.startswith("  "), c.strip()) for c in str(text or "").replace("\r\n", "\n").split("\n\n") if c.strip()]


def _s(x) -> str:
    return f"{x:g}" if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def _clip_parts(clip, *, window: bool = True) -> list[str]:
    """extra.clip (компілятор: index, of, gen_s, window, start ∈ frame|prev_last|none, start_ref, start_item) →
    короткі підписи для картки й .md. window=False — вікно вже в edit_window."""
    if not isinstance(clip, dict):
        return [str(clip)] if clip not in (None, "") else []
    n = clip.get("of") or clip.get("total") or clip.get("count")
    out = []
    if clip.get("index") is not None:
        out.append(f"кліп {clip['index']}" + (f" з {n}" if n else ""))
    if clip.get("gen_s") is not None:
        out.append(f"генерувати {_s(clip['gen_s'])} с")
    w = clip.get("window")
    if window and isinstance(w, (list, tuple)) and len(w) == 2:
        out.append(f"у монтаж: {_s(w[0])}–{_s(w[1])} с кліпу")
    start = clip.get("start")
    if start == "prev_last" and clip.get("index") == 1:              # handoff continue — кадр попереднього шоту
        start = "prev_shot"
    if start:
        out.append(CLIP_START.get(start, f"старт: {start}"))
    if clip.get("start_item"):
        last = " — його останній кадр" if str(clip.get("start_ref") or "").endswith(".last") else ""
        out.append(f"файл старту: результат «{clip['start_item']}»{last}")
    out += [f"{k}: {v}" for k, v in clip.items() if k not in CLIP_SKIP and v not in (None, "", [])]
    return out


def _lessons(item: prompts_mod.Item, slug: str) -> list[str]:
    """extra.lessons (id уроків; старий формат — словники) → «L3: правило» з lessons.yaml."""
    raw = item.extra.get("lessons") or []
    if not raw:
        return []
    try:
        rules = {x.get("id"): x.get("rule") for x in lessons_mod.load(slug)}
    except lessons_mod.LessonError:
        rules = {}
    out = []
    for x in raw:
        if isinstance(x, dict):
            lid, rule = x.get("id"), x.get("rule")
        else:
            lid, rule = x, rules.get(x)
        out.append(f"{lid}: {rule}" if lid and rule else str(rule or lid or json.dumps(x, ensure_ascii=False)))
    return out


def carry_over(items: list[prompts_mod.Item]) -> dict[str, list[str]]:
    """§12: стан на кінці шоту (state_out останнього кліпу) → наступний шот частини: {шот: [стан]}. Порядок шотів —
    за відео (у handoff continue кадру немає); test-pack — незалежні тести, нічого не переносимо."""
    vids = [i for i in items if i.kind == "video" and i.extra.get("shot") and str(i.set).isdigit()]
    shots = list(dict.fromkeys(i.extra["shot"] for i in vids))
    outs = {i.extra["shot"]: i.extra["state_out"] for i in vids if i.extra.get("state_out")}
    return {b: outs[a] for a, b in pairwise(shots) if outs.get(a)}


def state_in(item: prompts_mod.Item, carry: dict[str, list[str]]) -> list[str]:
    """Стан із попереднього шоту для стартового кадру й кліпу 1 (extra.state_in має перевагу)."""
    st = item.extra.get("state_in")
    if not st:
        clip = item.extra.get("clip")
        first = ((item.kind == "image" and item.extra.get("which", "first") == "first")
                 or (isinstance(clip, dict) and clip.get("index") == 1))
        st = carry.get(item.extra.get("shot")) if first else None
    return [str(x) for x in (st if isinstance(st, list) else [st])] if st else []


# ---------------------------------------------------------------- стан референсів


def _path(f: str) -> Path:
    return lab_mod.stored_path(f)                         # як у журналі: відносно кореня репо або абсолютний


def _local(f) -> bool:
    """Файл є на цьому комп'ютері (media/ не в Git: у партнера рядок журналу є, а файлу немає)."""
    return bool(f) and _path(str(f)).is_file()


@dataclass
class RefState:
    ref: str                                   # mina.tunnel · p1.1.02.frame · p1.1.02.c1.last
    producer: prompts_mod.Item | None          # хто його створює (для «.last» — кліп)
    row: dict | None = None                    # результат, чий файл вантажити; файлу тут немає — найкращий у журналі
    file: str | None = None                    # файл (як у журналі), є на диску; для «.last» — останній кадр
    golden: bool = False
    clip: dict | None = None                   # «.last»: кліп у журналі є, кадру ще немає
    last: bool = False                         # «<produces>.last» — останній кадр кліпу producer

    @property
    def state(self) -> str:
        """golden | ok (≥ 4 з файлом) | nofile (≥ 4, файлу тут немає) | weak (< 4) | clip | missing."""
        if self.golden:
            return "golden"
        if self.row:
            if self.row["score"] < lab_mod.PASS_SCORE:
                return "weak"
            return "ok" if self.file else "nofile"
        return "clip" if self.clip else "missing"

    @property
    def ready(self) -> bool:
        return self.state in ("golden", "ok")

    def label(self, slug: str) -> str:
        p = self.producer
        if p is None:
            return "ще немає — джерела в пакеті немає (збери пакет разом із кастингом)"
        where = f"крок {p.step} · {p.id}" if p.step else p.id
        score, state = (self.row or {}).get("score"), self.state
        if state == "clip":
            s = self.clip.get("score")
            return (f"кліп є ({s}/5), останнього кадру ще немає — uv run fabrica lab log {p.id}{lab_mod.LAST} "
                    f'--story {slug} --tool other --score {s} --file "<кадр.png>"')
        away = bool((self.row or {}).get("file")) and not self.file          # у журналі файл є, на диску — ні
        return {"golden": "★ golden" + (f" ({score}/5)" if score else "") + (f" · {NO_LOCAL}" if away else ""),
                "ok": f"✓ є ({score}/5)",
                "nofile": f"✓ {score}/5, але {NO_LOCAL}" if away else
                f"оцінка {score}/5 без файлу — запиши результат з --file",
                "weak": f"лише {score}/5 — переробити: {where}",
                "missing": f"ще немає — спершу {where}"}[state]


def _top(rows: list[dict], item: prompts_mod.Item) -> dict | None:
    """Найкращий рядок, як у lab.ref_file: файл є на диску → оцінка ≥ 4 → поточна версія промпту → оцінка → новіший."""
    return max(rows, key=lambda r: (_local(r.get("file")), r.get("score", 0) >= lab_mod.PASS_SCORE,
                                    r.get("prompt_sha") == item.prompt_sha, r.get("score", 0),
                                    r.get("id", 0))) if rows else None


class Pack:
    """Журнал і golden одного пакета: результати за елементом, хто створює який референс, що вже готово."""

    def __init__(self, slug: str, items: list[prompts_mod.Item], producers: list[prompts_mod.Item] | None = None,
                 rows: list[dict] | None = None, g: dict | None = None) -> None:
        self.slug = slug
        self.g = g if g is not None else lab_mod.golden()
        self.all_rows = list(rows if rows is not None else lab_mod.results(slug))
        self.rows: dict[str, list[dict]] = {}
        for r in self.all_rows:
            self.rows.setdefault(r["item"], []).append(r)
        self.pool = [*items, *(producers or [])]          # елементи пакета важать більше за producers
        self.producers: dict[str, prompts_mod.Item] = {}
        for it in self.pool:
            if it.produces:
                self.producers.setdefault(it.produces, it)
        self._refs: dict[str, RefState] = {}

    def golden(self, item: prompts_mod.Item) -> bool:
        return lab_mod.is_golden_item(self.slug, item, self.g)

    def current(self, item: prompts_mod.Item) -> list[dict]:
        return [r for r in self.rows.get(item.id, []) if r["prompt_sha"] == item.prompt_sha]

    def done(self, item: prompts_mod.Item) -> bool:
        return self.golden(item) or any(r["score"] >= lab_mod.PASS_SCORE for r in self.current(item))

    def ref(self, ref: str) -> RefState:
        """Стан референсу. Файл — рівно той, що дає lab.ref_file (той самий бере студія): golden поточного промпту →
        ≥ 4 (поточна версія першою) → решта, лише наявні на диску. «<produces>.last» — last_frame рядка кліпу або кадр
        «<кліп>-last», записаний руками (окремий елемент, що дає «….last», — важливіший)."""
        if ref in self._refs:
            return self._refs[ref]
        last = ref not in self.producers and ref.endswith(".last")
        p = self.producers.get(ref.removesuffix(".last") if last else ref)
        if p is None:
            return RefState(ref, None, last=last)
        rows = self.rows.get(p.id, [])
        cands = ([{**r, "file": r["last_frame"]} for r in rows if r.get("last_frame")]
                 + [r for r in self.rows.get(p.id + lab_mod.LAST, []) if r.get("file")]) if last else rows
        f = lab_mod.ref_file(self.slug, ref, self.pool, rows=self.all_rows, g=self.g)
        golden = self.golden(p) and (bool(cands) or not last)
        rid = (lab_mod.golden_result(self.slug, p, g=self.g, rows=self.all_rows) or {}).get("id") if golden else None
        hit = [r for r in cands if f and r.get("file") and _path(r["file"]) == f]
        best = max(hit, key=lambda r: r.get("id") == rid) if hit else _top(cands, p)
        st = RefState(ref, p, best, best["file"] if hit else None, golden,
                      None if cands or not last else _top(rows, p), last)
        self._refs[ref] = st
        return st

    def next_item(self, items: list[prompts_mod.Item]) -> prompts_mod.Item | None:
        """Далі: перший не готовий елемент, усі референси якого готові (≥ 4 / golden); інакше — перший не готовий."""
        todo = [i for i in items if not self.done(i)]
        return next((i for i in todo if all(self.ref(r).ready for _, r in slots(i))), todo[0] if todo else None)


# ---------------------------------------------------------------- HTML


def _rel(path: str, base: Path) -> str:
    """Посилання на файл відносно index.html, з відсотковим кодуванням («#», «?», пробіли в назві файлу)."""
    target = _path(path)
    try:
        return quote(Path(os.path.relpath(target, base)).as_posix(), safe="/")
    except ValueError:                                    # Windows: інший диск — абсолютне посилання
        return target.resolve().as_uri()


def _media(src: str, label: str) -> str:
    ext = Path(src).suffix.lower()
    s, lb = html.escape(src), html.escape(label)
    if ext in IMAGE:
        return f'<figure><a href="{s}" target="_blank"><img src="{s}" alt="{lb}" loading="lazy"></a><figcaption>{lb}</figcaption></figure>'
    if ext in VIDEO:
        return f'<figure><video src="{s}" controls muted preload="metadata"></video><figcaption>{lb}</figcaption></figure>'
    if ext in AUDIO:
        return f'<figure class="audio"><audio src="{s}" controls preload="none"></audio><figcaption>{lb}</figcaption></figure>'
    return f'<figure><a href="{s}">{lb}</a></figure>'


def _file_html(f: str | None, base: Path, label: str) -> str:
    """Мініатюра файлу журналу; файлу на цьому комп'ютері немає — підпис замість зламаної картинки."""
    if f and _local(f):
        return _media(_rel(f, base), label)
    return f'<span class="chip">{html.escape(label + (f" · {NO_LOCAL}" if f else ""))}</span>'


def _copy_block(label: str, text: str, key: str) -> str:
    return (f'<div class="block"><div class="block-head"><span>{html.escape(label)}</span>'
            f'<button class="copy" data-target="{key}">Копіювати</button></div>'
            f'<pre id="{key}">{html.escape(text)}</pre></div>')


def _json(v) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2, default=str)


def _tool(item: prompts_mod.Item, man: list[dict]) -> str:
    """Інструмент за замовчуванням у формі журналу: той, що стоїть найраніше в назві першої поверхні (далі —
    провайдер маршруту): «AI Studio / Gemini · dropshot Image» → ai-studio, «dropshot AI Studio …» → dropshot."""
    text = f"{(man[0].get('surface') or '') if man else ''} {item.route.split(':')[0]}".lower()
    hits = [(text.find(needle), tool) for needle, tool in TOOL_NEEDLES if needle in text]
    return min(hits)[1] if hits else TOOLS[0]


def _face(item: prompts_mod.Item) -> tuple[bool, str]:
    """(Cloudflare через обличчя?, підпис): бейдж «обличчя → Cloudflare» лише на маршруті cloudflare:…"""
    face = item.extra.get("face")
    cf = face == "clear" and item.route.startswith("cloudflare:")
    return cf, "обличчя → Cloudflare" if cf else f"обличчя: {face}" if face else ""


def _warnings_html(item: prompts_mod.Item) -> str:
    groups = split_warnings(item.warnings)
    css = {"API": "w-api", "lint": "w-lint", "дані": "w-data"}
    return "".join(f'<div class="wgroup {css[name]}"><h4>⚠️ {name} ({len(ws)})</h4><ul>'
                   + "".join(f"<li>{html.escape(w)}</li>" for w in ws) + "</ul></div>"
                   for name, ws in groups.items() if ws)


def _slots_html(item: prompts_mod.Item, pack: Pack, base: Path) -> str:
    out = []
    for label, ref in slots(item):
        s = pack.ref(ref)
        thumb = _media(_rel(s.file, base), f"{ref} · {s.row['score']}/5") if s.file and s.row else ""
        src = ""
        if s.producer:
            pid = f"<code>{html.escape(s.producer.id)}</code>"
            src = f'<div class="slot-src">файл: {"останній кадр результату " if s.last else "результат "}{pid}'
            src += (f' · <code>{html.escape(s.file)}</code>' if s.file else "") + "</div>"
        out.append(f'<div class="slot s-{STATE_CLASS[s.state]}"><div class="slot-head"><b>{html.escape(label)}</b> = '
                   f'<code>{html.escape(ref)}</code></div>{thumb}'
                   f'<div class="slot-state">{html.escape(s.label(pack.slug))}</div>{src}</div>')
    return f'<div class="refs"><h4>Референси по порядку</h4><div class="slots">{"".join(out)}</div></div>' if out else ""


MANUAL_BLOCKS = (("text", "Текст"), ("body", "Тіло запиту (JSON)"), ("json", "JSON"), ("cmd", "Команда"))


def _manual_html(man: list[dict], kid: str) -> str:
    out = []
    for j, m in enumerate(man):
        head = " — ".join(str(x) for x in (m.get("surface"), m.get("title")) if x) or "інструкція"
        body = []
        if m.get("url"):
            u = html.escape(str(m["url"]))
            body.append(f'<p class="url"><a href="{u}" target="_blank" rel="noopener">{u}</a></p>')
        if m.get("endpoint"):
            body.append(_copy_block("Endpoint", str(m["endpoint"]), f"{kid}-m{j}-endpoint"))
        for key in ("how", "note"):
            for c, (cmd, chunk) in enumerate(how_parts(m.get(key))):
                body.append(_copy_block("Команда", chunk, f"{kid}-m{j}-{key}{c}") if cmd
                            else f'<p class="how">{html.escape(chunk)}</p>')
        for key, lb in MANUAL_BLOCKS:
            if m.get(key) not in (None, "", {}):
                body.append(_copy_block(lb, _json(m[key]), f"{kid}-m{j}-{key}"))
        out.append(f'<details class="manual"{" open" if j == 0 else ""}><summary>{html.escape(head)}</summary>'
                   f'{"".join(body)}</details>')
    return f'<div class="manuals"><h4>Як зробити руками</h4>{"".join(out)}</div>' if out else ""


def _list_html(css: str, title: str, rows: list) -> str:
    li = "".join(f"<li>{html.escape(str(s))}</li>" for s in rows)
    return f'<div class="{css}"><h4>{html.escape(title)}</h4><ul>{li}</ul></div>'


STATE_IN = "Стан із попереднього шоту — має бути в кадрі"
STATE_OUT = "Стан на кінці шоту → наступний шот"


def _card(item: prompts_mod.Item, n: int, pack: Pack, base: Path, carry: dict[str, list[str]] | None = None) -> str:
    slug, kid = pack.slug, f"i{n}"
    golden_item, state = pack.golden(item), lab_mod.golden_state(item.template, pack.g)
    mine, current = pack.rows.get(item.id, []), pack.current(item)
    best = max((r["score"] for r in current), default=None)
    man, (cf, face) = manual(item), _face(item)
    badges = [f'<span class="badge kind-{item.kind}">{KIND_UA.get(item.kind, item.kind)}</span>']
    if item.route:
        badges.append(f'<span class="badge route">{html.escape(item.route)}</span>')
    if face:
        badges.append(f'<span class="badge{" face" if cf else ""}">{html.escape(face)}</span>')
    badges += [f'<span class="badge tpl">{html.escape(item.template.ref)} · {html.escape(state)}</span>',
               f'<span class="badge sha">промпт {item.prompt_sha}</span>']
    if lessons := _lessons(item, slug):
        badges.append(f'<span class="badge lessons">враховано уроків: {len(lessons)}</span>')
    if golden_item:
        badges.append('<span class="badge golden">★ golden</span>')
    if best is not None:
        badges.append(f'<span class="badge score s{best}">найкраще: {best}/5</span>')
    search = " ".join([item.id, item.title, item.route, *item.needs]).lower()
    parts = [(f'<article class="card" data-kind="{html.escape(item.kind)}" data-step="{item.step}" '
              f'data-tested="{int(bool(current))}" data-golden="{int(golden_item)}" data-warn="{int(bool(item.warnings))}" '
              f'data-search="{html.escape(search)}">'),
             f'<header><h3><code>{html.escape(item.id)}</code> {html.escape(item.title)}</h3>{"".join(badges)}</header>',
             _warnings_html(item)]
    clip = _clip_parts(item.extra.get("clip"), window=not item.extra.get("edit_window"))
    if item.extra.get("edit_window"):
        clip.append(f"монтаж: {item.extra['edit_window']}")
    if clip:
        parts.append('<div class="clip">' + "".join(f'<span class="chip on">{html.escape(c)}</span>' for c in clip) + "</div>")
    if st := state_in(item, carry or {}):
        parts.append(_list_html("state-in", STATE_IN, st))
    label = "Текст репліки (іспанською)" if item.template.id == "voice.line" else "Промпт"
    parts.append(_copy_block(label, item.prompt, f"{kid}-p"))
    if item.payload:
        parts.append(_copy_block(f"Payload — тіло запиту ({item.route or 'маршрут не задано'})", _json(item.payload),
                                 f"{kid}-j"))
    parts.append(_slots_html(item, pack, base))
    parts.append(_manual_html(man, kid))
    if item.negative:
        parts.append(_copy_block("Negative prompt", item.negative, f"{kid}-n"))
    if item.extra.get("preview_es"):
        parts.append(_copy_block("Текст прев'ю голосу (іспанською)", item.extra["preview_es"], f"{kid}-v"))
    rows_html = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(_json(v) if isinstance(v, (dict, list)) else str(v))}</td></tr>"
                        for k, v in item.params.items() if v not in (None, ""))
    if rows_html:
        parts.append(f'<table class="params">{rows_html}</table>')
    if item.extra.get("success"):
        parts.append(_list_html("success", "Успіх, якщо", item.extra["success"]))
    if item.extra.get("state_out"):
        parts.append(_list_html("state-out", STATE_OUT, item.extra["state_out"]))
    if lessons:
        li = "".join(f"<li>{html.escape(s)}</li>" for s in lessons)
        parts.append(f'<details class="lessons"><summary>Уроки в промпті ({len(lessons)})</summary><ul>{li}</ul></details>')
    if mine:
        res = []
        for r in sorted(mine, key=lambda r: r["id"], reverse=True)[:6]:
            old = "" if r["prompt_sha"] == item.prompt_sha else " (стара версія)"
            notes = f" — {r['notes']}" if r.get("notes") else ""
            res.append(_file_html(r.get("file"), base, f"#{r['id']} {r['tool']} · {r['score']}/5{old}{notes}"))
            if r.get("last_frame"):
                res.append(_file_html(r["last_frame"], base, f"#{r['id']} останній кадр"))
        parts.append(f'<div class="results"><h4>Результати тестів</h4>{"".join(res)}</div>')
    tool = _tool(item, man)
    opts = "".join(f'<option{" selected" if t == tool else ""}>{t}</option>' for t in TOOLS)
    parts.append(
        f'<div class="lab" data-item="{html.escape(item.id)}" data-sha="{item.prompt_sha}" data-story="{html.escape(slug)}">'
        f'<h4>Нотатки й запис результату</h4>'
        f'<textarea placeholder="Що вийшло, що виправити в шаблоні…"></textarea>'
        f'<div class="row"><label>Інструмент <select class="tool">{opts}</select></label>'
        f'<label>Оцінка <select class="score"><option>5</option><option selected>4</option><option>3</option>'
        f'<option>2</option><option>1</option></select></label>'
        f'<label class="grow">Файл <input class="file" placeholder="~/Downloads/результат.png"></label></div>'
        f'<button class="copy-cmd">Копіювати команду журналу</button><pre class="cmd"></pre></div>')
    parts.append("</article>")
    return "".join(p for p in parts if p)


def _step_head(s: dict, items: list[prompts_mod.Item], pack: Pack) -> str:
    done = sum(1 for i in items if pack.done(i))
    rows = [("Що робити", s.get("todo")), ("Чим", s.get("tool")), ("Готово, коли", s.get("done"))]
    body = "".join(f"<p><b>{k}:</b> {html.escape(str(v))}</p>" for k, v in rows if v)
    num = f"Крок {s['step']} · " if s["step"] else ""
    return (f'<div class="step-head"><h2>{num}{html.escape(str(s.get("title") or ""))}</h2>{body}'
            f'<p class="progress">готово {done} з {len(items)}</p></div>')


def _profile_line() -> str:
    """Активний профіль кліпів (providers.generation) — для наборів з відео."""
    try:
        p = providers_mod.generation()
    except (providers_mod.ProviderError, config.ConfigError):
        return ""
    clip = ("/".join(f"{x:g}" for x in p["clip_s"]) if p.get("clip_s")
            else f"{p.get('clip_min_s', '?')}–{p.get('clip_max_s', '?')}") + " с"
    extra = [p.get("resolution"), p.get("surface"), p.get("note")]
    return f"профіль кліпів «{p['name']}»: {clip}" + "".join(f" · {x}" for x in extra if x)


CSS = """
:root{--bg:#0f1115;--card:#171a21;--panel:#12151b;--code:#0b0d11;--line:#2a2f3a;--text:#e8e8ea;--muted:#9aa0aa;--accent:#e8a33d;--ok:#3fb27f;--bad:#e5534b;--info:#6ea8e0;--face:#c678dd}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:20px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
code{overflow-wrap:anywhere}a{color:var(--info)}
.top{position:sticky;top:0;z-index:5;background:#0f1115ee;backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:14px 24px}
.top h1{margin:0 0 8px;font-size:26px}.top .sub{color:var(--muted);font-size:16px}.top .next{color:var(--text);font-size:18px;margin-top:4px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.filters button,.filters input{font:inherit;font-size:17px}
.filters button{background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:999px;padding:6px 14px;cursor:pointer}
.filters button.on{background:var(--accent);color:#111;border-color:var(--accent)}
.filters input{flex:1;min-width:200px;background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:6px 12px}
main{max-width:1200px;margin:0 auto;padding:20px 24px 80px}
.step{margin:0 0 36px}.step-head{border-left:6px solid var(--accent);background:var(--panel);border-radius:12px;padding:14px 18px;margin:0 0 18px}
.step-head h2{margin:0 0 6px;font-size:27px}.step-head p{margin:2px 0;color:var(--muted);font-size:18px}.step-head b{color:var(--text);font-weight:600}
.step-head .progress{color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:0 0 22px}
.card h3{font-size:22px;margin:0 0 8px}.card h3 code{color:var(--accent)}
.badge{display:inline-block;font-size:14px;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:0 6px 6px 0;color:var(--muted)}
.badge.route{color:var(--info);border-color:var(--info)}.badge.face{color:#111;background:var(--face);border-color:var(--face);font-weight:600}
.badge.golden{color:#111;background:var(--accent);border-color:var(--accent)}.badge.s5,.badge.s4{color:var(--ok);border-color:var(--ok)}
.badge.s1,.badge.s2{color:var(--bad);border-color:var(--bad)}.badge.lessons{color:var(--ok)}
.block{margin:14px 0}.block-head{display:flex;justify-content:space-between;align-items:center;gap:10px;color:var(--muted);font-size:16px}
pre{white-space:pre-wrap;word-break:break-word;background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px;margin:6px 0 0;font:18px/1.55 ui-monospace,Menlo,Consolas,monospace}
button.copy,button.copy-cmd{font:inherit;font-size:16px;background:var(--accent);color:#111;border:0;border-radius:10px;padding:6px 16px;cursor:pointer;flex:none}
button.done{background:var(--ok)}
.params{border-collapse:collapse;margin:10px 0;font-size:17px;max-width:100%}.params th{color:var(--muted);text-align:left;padding:2px 16px 2px 0;font-weight:500;vertical-align:top}
.params td{word-break:break-word}
h4{font-size:17px;color:var(--muted);margin:14px 0 6px;font-weight:600}
.wgroup{border:1px solid var(--line);border-radius:10px;padding:8px 14px;margin:8px 0;font-size:17px}.wgroup h4{margin:0 0 4px}
.wgroup ul{margin:0 0 0 22px;padding:0}.w-api{border-color:var(--bad)}.w-api h4{color:var(--bad)}
.w-lint{border-color:var(--accent)}.w-lint h4{color:var(--accent)}.w-data h4{color:var(--muted)}
.clip{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.chip.on{color:var(--text);border-style:solid;border-color:var(--info)}
.slots{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.slot{background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--line);border-radius:12px;padding:10px 12px;font-size:16px}
.slot.s-ok{border-left-color:var(--ok)}.slot.s-golden{border-left-color:var(--accent)}.slot.s-weak{border-left-color:#c9a227}.slot.s-missing{border-left-color:var(--bad)}
.slot-head{margin:0 0 6px}.slot-state{margin-top:6px}.s-missing .slot-state{color:var(--bad)}.s-ok .slot-state{color:var(--ok)}
.slot-src{color:var(--muted);font-size:14px;margin-top:4px}.slot figure,.slot figure img,.slot figure video{width:100%}
details.manual,details.lessons{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 14px;margin:8px 0}
details summary{cursor:pointer;font-weight:600;font-size:18px}.how{color:var(--muted);font-size:17px;margin:6px 0;white-space:pre-wrap}.url{margin:6px 0;font-size:16px}
.refs,.results{margin:6px 0}.results{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start}.results h4{width:100%}
figure{margin:0;width:220px;max-width:100%}figure img,figure video{width:220px;max-width:100%;border-radius:10px;border:1px solid var(--line);display:block}
figure.audio{width:320px}figure audio{width:320px;max-width:100%}figcaption{font-size:14px;color:var(--muted);margin-top:4px}
.chip{display:inline-block;font-size:15px;color:var(--muted);border:1px dashed var(--line);border-radius:10px;padding:6px 10px}
.state-in,.state-out{border-left:4px solid var(--face);padding:2px 0 2px 12px;margin:10px 0}.state-in h4,.state-out h4{margin:0 0 4px}
.state-in ul,.state-out ul,.success ul,.lessons ul{margin:4px 0 0 22px;color:var(--muted)}
.lab textarea{width:100%;min-height:80px;background:var(--code);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit;font-size:17px}
.lab .row{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0}.lab label{font-size:16px;color:var(--muted)}.lab .grow{flex:1;min-width:200px}
.lab select,.lab input{font:inherit;font-size:16px;background:var(--code);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:4px 8px}
.lab input{width:100%}.cmd:empty{display:none}.hidden{display:none}
@media (max-width:640px){body{font-size:17px}.top{position:static;padding:12px 16px}.top h1{font-size:21px}
main{padding:14px 16px 60px}.card{padding:14px;border-radius:12px}.card h3{font-size:19px}.step-head{padding:12px 14px}
.step-head h2{font-size:22px}pre{font-size:15px;padding:10px}.filters button{font-size:15px;padding:5px 10px}
.filters input{min-width:100%}.slots{grid-template-columns:1fr}figure,figure.audio,figure img,figure video,figure audio{width:100%}
.params{display:block;overflow-x:auto}}
"""

JS = r"""
function copyText(t,btn){const done=()=>{const o=btn.textContent;btn.textContent='Скопійовано';btn.classList.add('done');setTimeout(()=>{btn.textContent=o;btn.classList.remove('done')},1400)};
 if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(done,()=>fallback(t,done))}else{fallback(t,done)}}
function fallback(t,done){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy')}catch(e){}a.remove();done()}
document.querySelectorAll('button.copy').forEach(b=>b.onclick=()=>copyText(document.getElementById(b.dataset.target).textContent,b));
// у лапках '…' і zsh, і PowerShell нічого не розкривають ($, `, \); лапки в нотатках → ’, шлях без зовнішніх лапок
function q(s){return "'"+s.replace(/\s+/g,' ').replace(/['"]/g,'\u2019')+"'"}
function qf(s){s=s.trim().replace(/^["']+|["']+$/g,'');return s.includes("'")?'"'+s+'"':"'"+s+"'"}
document.querySelectorAll('.lab').forEach(box=>{const key='lab:'+box.dataset.item+':'+box.dataset.sha;const ta=box.querySelector('textarea');
 try{ta.value=localStorage.getItem(key)||''}catch(e){}ta.oninput=()=>{try{localStorage.setItem(key,ta.value)}catch(e){}};
 box.querySelector('.copy-cmd').onclick=(ev)=>{const tool=box.querySelector('.tool').value,score=box.querySelector('.score').value,file=box.querySelector('.file').value.trim();
  let c='uv run fabrica lab log '+box.dataset.item+' --story '+box.dataset.story+' --tool '+tool+' --score '+score;if(file)c+=' --file '+qf(file);if(ta.value.trim())c+=' --notes '+q(ta.value.trim());
  box.querySelector('.cmd').textContent=c;copyText(c,ev.target)}});
let kind='all',flag='all',step='all';const search=document.getElementById('search');
function apply(){const s=search.value.trim().toLowerCase();document.querySelectorAll('.card').forEach(c=>{let ok=(kind==='all'||c.dataset.kind===kind)&&(step==='all'||c.dataset.step===step);
 if(flag==='untested')ok=ok&&c.dataset.tested==='0';if(flag==='golden')ok=ok&&c.dataset.golden==='1';if(flag==='warn')ok=ok&&c.dataset.warn==='1';
 if(s)ok=ok&&c.dataset.search.includes(s);c.classList.toggle('hidden',!ok)});
 document.querySelectorAll('section.step').forEach(x=>x.classList.toggle('hidden',!x.querySelector('.card:not(.hidden)')))}
function group(attr,set){document.querySelectorAll('['+attr+']').forEach(b=>b.onclick=()=>{set(b.getAttribute(attr));document.querySelectorAll('['+attr+']').forEach(x=>x.classList.toggle('on',x===b));apply()})}
group('data-kind-filter',v=>kind=v);group('data-step-filter',v=>step=v);
document.querySelectorAll('[data-flag]').forEach(b=>b.onclick=()=>{flag=flag===b.dataset.flag?'all':b.dataset.flag;document.querySelectorAll('[data-flag]').forEach(x=>x.classList.toggle('on',x.dataset.flag===flag));apply()});
search.oninput=apply;
"""


def build_html(slug: str, set_name: str, items: list[prompts_mod.Item], base: Path,
               producers: list[prompts_mod.Item] | None = None) -> str:
    pack, carry = Pack(slug, items, producers), carry_over(items)
    table = steps()
    groups: dict[int, list[tuple[int, prompts_mod.Item]]] = {}
    for n, it in enumerate(items):
        groups.setdefault(it.step, []).append((n, it))
    order = sorted(groups, key=lambda s: (s == 0, s))
    sections = []
    for s in order:
        info = table.get(s) or (NO_STEP if s == 0 else {"step": s, "title": ""})
        cards = "".join(_card(it, n, pack, base, carry) for n, it in groups[s])
        sections.append(f'<section class="step" data-step="{s}">{_step_head(info, [it for _, it in groups[s]], pack)}'
                        f'{cards}</section>')
    counts = {k: sum(1 for i in items if i.kind == k) for k in KIND_UA}
    tested = sum(1 for i in items if pack.current(i))
    kinds = "".join(f'<button data-kind-filter="{k}">{v} ({counts[k]})</button>' for k, v in KIND_UA.items() if counts[k])
    step_btns = ('<button data-step-filter="all" class="on">усі кроки</button>'
                 + "".join(f'<button data-step-filter="{s}">{f"крок {s}" if s else "без кроку"} ({len(groups[s])})</button>'
                           for s in order)) if len(order) > 1 else ""
    nxt = pack.next_item(items)
    next_line = (f'<div class="next">Далі: {"крок " + str(nxt.step) + " · " if nxt.step else ""}<code>{html.escape(nxt.id)}</code> '
                 f'— {html.escape(nxt.title)}</div>' if nxt else '<div class="next">Усе в пакеті готово ✓</div>')
    profile = _profile_line() if counts["video"] else ""
    title = f"{slug} · {set_name} · лабораторія промптів"
    return (f'<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body>'
            f'<div class="top"><h1>{html.escape(slug.upper())} · {html.escape(set_name)}</h1>'
            f'<div class="sub">{len(items)} промптів · протестовано {tested} · режим лабораторії: автоматика вимкнена, '
            f'тестуємо руками → <code>fabrica lab log</code> → <code>fabrica lab approve</code>'
            f'{" · " + html.escape(profile) if profile else ""}</div>{next_line}'
            f'<div class="filters"><button data-kind-filter="all" class="on">усі ({len(items)})</button>{kinds}'
            f'{step_btns}'
            f'<button data-flag="untested">без результату</button><button data-flag="golden">★ golden</button>'
            f'<button data-flag="warn">⚠️ з попередженнями</button>'
            f'<input id="search" placeholder="пошук: mateo, T1, dawn…"></div></div>'
            f'<main>{"".join(sections)}</main><script>{JS}</script></body></html>')


# ---------------------------------------------------------------- markdown і пакет


def _md_how(text) -> list[str]:
    """how у .md: абзаци прози окремо, команди — блоками коду (копіюються без прози)."""
    return [x for cmd, c in how_parts(text) for x in (["```text", c, "```"] if cmd else [c]) + [""]]


def item_md(slug: str, item: prompts_mod.Item, carry: dict[str, list[str]] | None = None) -> str:
    """<елемент>.md: маршрут, payload, слоти, ручні інструкції, кліп; carry — carry_over(пакет) для стану шоту."""
    st = steps().get(item.step)
    _, face = _face(item)
    lines = [f"# {item.id} — {item.title}", ""]
    if item.step:
        lines.append(f"- Крок {item.step}" + (f" · {st['title']}" if st else ""))
    if item.route:
        lines.append(f"- Маршрут: `{item.route}`" + (f" · {face}" if face else ""))
    lines += [f"- Шаблон: `{item.template.ref}` (sha {item.template.sha}) · промпт `{item.prompt_sha}`",
              (f"- Тип: {KIND_UA.get(item.kind, item.kind)} · референси: {', '.join(item.refs) or '—'}"
               f" · потрібно: {', '.join(item.needs) or '—'}")]
    ew = item.extra.get("edit_window")
    clip = _clip_parts(item.extra.get("clip"), window=not ew) + ([f"монтаж: {ew}"] if ew else [])
    if clip:
        lines.append(f"- Кліп: {' · '.join(clip)}")
    lines.append("")
    if sin := state_in(item, carry or {}):
        lines += [f"## {STATE_IN}", ""] + [f"- {s}" for s in sin] + [""]
    for name, ws in split_warnings(item.warnings).items():
        lines += [f"> ⚠️ {name}: {w}" for w in ws]
    if item.warnings:
        lines.append("")
    lines += ["## Промпт", "", "```text", item.prompt, "```", ""]
    if item.payload:
        lines += ["## Payload (тіло запиту до API)", "", "```json", _json(item.payload), "```", ""]
    if sl := slots(item):
        lines += ["## Референси по порядку", ""] + [f"- {label} = `{ref}`" for label, ref in sl] + [""]
    for m in manual(item):
        head = " — ".join(str(x) for x in (m.get("surface"), m.get("title")) if x) or "інструкція"
        lines += [f"## Руками: {head}", ""]
        if m.get("url"):
            lines += [str(m["url"]), ""]
        if m.get("endpoint"):
            lines += [f"Endpoint: `{m['endpoint']}`", ""]
        lines += _md_how(m.get("how")) + _md_how(m.get("note"))
        for key, lang in (("text", "text"), ("body", "json"), ("json", "json"), ("cmd", "bash")):
            if m.get(key) not in (None, "", {}):
                lines += [f"```{lang}", _json(m[key]), "```", ""]
    if item.negative:
        lines += ["## Negative", "", "```text", item.negative, "```", ""]
    if item.extra.get("preview_es"):
        lines += ["## Прев'ю голосу", "", "```text", item.extra["preview_es"], "```", ""]
    lines += ["## Параметри", "", "```json", json.dumps(item.params, ensure_ascii=False, indent=2, default=str), "```", ""]
    if item.extra.get("success"):
        lines += ["## Успіх, якщо", ""] + [f"- {s}" for s in item.extra["success"]] + [""]
    if item.extra.get("state_out"):
        lines += [f"## {STATE_OUT}", ""] + [f"- {s}" for s in item.extra["state_out"]] + [""]
    if lessons := _lessons(item, slug):
        lines += [f"## Уроки в промпті ({len(lessons)})", ""] + [f"- {s}" for s in lessons] + [""]
    lines += ["## Записати результат", "", "```text",
              (f"uv run fabrica lab log {item.id} --story {slug} --tool <інструмент> --score <1-5> --file '<шлях>' "
               "--notes '<що вийшло>'"),
              "```", ""]
    return "\n".join(lines)


def manifest_entry(i: prompts_mod.Item) -> dict:
    """Елемент для manifest.json: усе, що потрібно автоматиці й студії (маршрут, payload, крок, потреби)."""
    return {"id": i.id, "title": i.title, "kind": i.kind, "step": i.step, "route": i.route, "template": i.template.ref,
            "template_sha": i.template.sha, "prompt_sha": i.prompt_sha, "refs": i.refs, "needs": i.needs,
            "produces": i.produces, "payload": i.payload, "params": i.params, "prompt": i.prompt, "negative": i.negative,
            **{k: i.extra[k] for k in ("face", "edit_window", "clip") if i.extra.get(k) is not None},
            "warnings": i.warnings}


def write_package(slug: str, set_name: str, items: list[prompts_mod.Item], out: Path = prompts_mod.OUT,
                  producers: list[prompts_mod.Item] | None = None) -> Path:
    folder = out / slug / set_name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        old.unlink()
    carry = carry_over(items)
    for it in items:
        with (folder / f"{it.id}.md").open("w", encoding="utf-8", newline="\n") as f:
            f.write(item_md(slug, it, carry))
    with (folder / "manifest.json").open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"story": slug, "set": set_name, "items": [manifest_entry(i) for i in items]},
                           ensure_ascii=False, indent=2, default=str) + "\n")
    index = folder / "index.html"
    with index.open("w", encoding="utf-8", newline="\n") as f:
        f.write(build_html(slug, set_name, items, folder, producers))
    return index
