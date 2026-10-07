"""Сторінка студії (fabrica/studio_ui): статичні перевірки без сервера й браузера — файли на місці, index.html
бере лише свої app.js / style.css, app.js знає кожен шлях контракту DESIGN §16, жодних CDN, синтаксис JS
(`node --check`) і чисті функції app.js (diff, попередження, профіль, кліп) — якщо є node, інакше пропуск."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "fabrica" / "studio_ui"
FILES = ("index.html", "app.js", "style.css")
# DESIGN §16: усі шляхи, які сторінка викликає сама (GET / і /static/ віддає сервер для index.html)
ENDPOINTS = ("/api/state", "/api/status", "/api/log", "/api/approve", "/api/rewrite", "/api/rewrite/apply",
             "/api/lessons", "/api/lessons/toggle", "/media")
TOOLS = ("dropshot", "ai-studio", "gemini", "elevenlabs", "replicate", "cloudflare", "other")
# DESIGN §16: точні ключі тіл POST (будують statusBody / logFields / … в app.js)
BODIES = {
    "status": ["item", "status", "story"],
    "log": ["file", "item", "notes", "prompt_sha", "score", "story", "tool"],
    "log_fields": ["item", "notes", "prompt_sha", "score", "story", "tool"],
    "approve": ["item", "story"],
    "rewrite": ["feedback", "item", "story"],
    "apply": ["proposal", "rule", "save_lesson", "story"],
    "apply_no_lesson": ["proposal", "save_lesson", "story"],
    "toggle": ["active", "id", "story"],
}
NODE = shutil.which("node")


def _read(name: str) -> str:
    return (UI / name).read_text(encoding="utf-8")


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[tuple[str, str]] = []
        self.ids: set[str] = set()
        self.html_attrs: dict[str, str | None] = {}
        self.metas: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_attrs = a
        if tag == "meta":
            self.metas.append(a)
        if a.get("id"):
            self.ids.add(a["id"])
        for key in ("src", "href"):
            if a.get(key) is not None:
                self.refs.append((tag, a[key]))


def _parsed() -> _Refs:
    p = _Refs()
    p.feed(_read("index.html"))
    return p


def _node(script: str) -> str:
    r = subprocess.run([NODE, "-e", script, str(UI / "app.js")], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_files_exist_and_utf8():
    for name in FILES:
        assert (UI / name).is_file(), name
        assert _read(name).strip()


def test_index_uses_only_own_static_files():
    p = _parsed()
    refs = [r for _, r in p.refs]
    assert ("script", "/static/app.js") in p.refs
    assert ("link", "/static/style.css") in p.refs
    assert all(r.startswith(("/static/", "data:", "#")) for r in refs), refs
    assert p.html_attrs.get("lang") == "uk"
    assert any(m.get("charset", "").lower() == "utf-8" for m in p.metas)
    assert any(m.get("name") == "viewport" and "width=device-width" in (m.get("content") or "") for m in p.metas)


@pytest.mark.parametrize("name", FILES)
def test_no_external_urls(name):
    text = _read(name)
    assert "http://" not in text and "https://" not in text, name
    assert "@import" not in text and "//cdn" not in text.lower()


@pytest.mark.parametrize("path", ENDPOINTS)
def test_app_calls_every_endpoint(path):
    assert f"'{path}'" in _read("app.js"), path


def test_app_sends_contract_fields():
    js = _read("app.js")
    # тіла POST за §16 і поле multipart-завантаження
    for key in ("story", "item", "status", "tool", "score", "notes", "file", "feedback", "proposal", "save_lesson",
                "rule", "active"):
        assert re.search(rf"\b{key}\b", js), key
    assert "fd.append('upload'" in js
    # тіла POST — лише через будівники (їхні ключі звіряє test_app_js_pure_functions), без літералів поруч
    assert "body: {story" not in js and "body: {...fields" not in js
    for fn in ("statusBody(", "logFields(", "logBody(", "approveBody(", "rewriteBody(", "applyBody(", "toggleBody("):
        assert js.count(fn) >= 2, fn                            # оголошення + виклик
    # поля відповіді, які сторінка показує
    for key in ("progress", "next", "rewrite_backend", "profile", "sequences", "needs", "manual", "warnings",
                "results", "last_frame", "stale", "golden", "prompt_old", "prompt_new", "warnings_new", "changes",
                "lesson", "state_in", "state_out", "edit_window", "clip", "lessons", "source"):
        assert re.search(rf"\b{key}\b", js), key
    assert "data.error" in js                                   # текст помилки сервера — у сповіщення


def test_tools_list():
    m = re.search(r"const TOOLS = \[([^\]]*)\]", _read("app.js"))
    assert m
    assert tuple(re.findall(r"'([^']+)'", m.group(1))) == TOOLS


def test_ukrainian_ui_and_keys():
    js, page = _read("app.js"), _read("index.html")
    for text in ("Копіювати промпт", "Записати результат", "Редагувати промпт", "Опиши, що вийшло не так",
                 "Запам'ятати урок", "Застосувати", "В роботі", "Готово", "Пропустити", "Затвердити golden",
                 "Що прикріпити", "Як зробити руками", "Попередження", "Результати"):
        assert text in js, text
    for text in ("Далі →", "Уроки", "Сховати готові"):
        assert text in page, text
    # клавіші — через keyOf (фізична клавіша: українська розкладка дає «о / л / с / т»)
    assert "const k = keyOf(e)" in js
    for key in ("j", "k", "c", "n"):
        assert f"k === '{key}'" in js and f"Key{key.upper()}: '{key}'" in js, key


def test_app_element_ids_exist_in_index():
    ids = _parsed().ids
    used = set(re.findall(r"\$\('#([\w-]+)'\)", _read("app.js")))
    assert used and used <= ids, used - ids


def test_css_dark_and_responsive():
    css = _read("style.css")
    assert "color-scheme: dark" in css
    assert re.search(r"@media \(max-width: *\d+px\)", css)
    assert "--bg:" in css and "background: var(--bg)" in css


@pytest.mark.skipif(not NODE, reason="node не встановлено")
def test_app_js_syntax():
    r = subprocess.run([NODE, "--check", str(UI / "app.js")], capture_output=True, text=True, encoding="utf-8",
                       timeout=60)
    assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not NODE, reason="node не встановлено")
def test_app_js_pure_functions():
    out = json.loads(_node(r"""
const m = require(process.argv[1]);
const WEAK = {ref: 'p1.1.02.frame', state: 'missing', item: 'p1-1.02-frame', score: 3,
              label: 'лише 3/5 — переробити: крок 5 · p1-1.02-frame'};
const CLIP = {ref: 'p1.1.02.c1.last', state: 'missing', item: 'p1-1.02-video', score: null,
              label: 'кліп є (4/5), останнього кадру ще немає — uv run fabrica lab log p1-1.02-video-last --story x'};
const MISSING = {ref: 'mina.plate', state: 'missing', item: 'loc-mina', label: 'ще немає — спершу крок 3 · loc-mina'};
const res = {
  diff: m.diffWords('the old red car stops', 'the new blue car stops'),
  same: m.diffWords('a b', 'a b'),
  stat: m.diffStat(m.diffWords('one two three', 'one four three five')),
  warn: m.groupWarnings(['API: unknown key', 'lint: «boy» (вік)', 'немає кадру']),
  warnObj: m.groupWarnings({api: ['x'], lint: [], data: ['y']}),
  profile: m.profileLabel({name: 'manual-5s', surface: 'dropshot AI Studio (Seedance 2.5)', clip_s: [5],
                           resolution: '720p'}),
  profile2: m.profileLabel({name: 'replicate-2.5', clip_min_s: 4, clip_max_s: 30,
                            resolution_by_tier: {hero: '720p', secondary: '480p'}}),
  clip: m.clipParts({clip: {index: 1, of: 2, gen_s: 5, window: [0, 3], start: 'frame', start_ref: 'p1.1.02.frame',
                            start_item: 'p1-1.02-frame'}}),
  clip2: m.clipParts({clip: {index: 2, of: 2, gen_s: 5, window: [0, 2.5], start: 'prev_last',
                             start_ref: 'p1.1.02.c1.last', start_item: 'p1-1.02-video'}}),
  clipNone: m.clipParts({}),
  missing: m.slotState({ref: 'mina.plate', state: 'missing', item: 'loc-mina'}),
  ok: m.slotState({ref: 'mina.plate', state: 'ok', score: 5}),
  tool: [m.defaultTool({manual: [{surface: 'dropshot AI Studio (Seedance 2.5)'}], route: 'cloudflare:x',
                        kind: 'video'}),
         m.defaultTool({manual: [{surface: 'AI Studio / Gemini · dropshot Image'}], route: 'replicate:x',
                        kind: 'image'}),
         m.defaultTool({manual: [], route: 'elevenlabs:eleven_v4', kind: 'voice'}),
         m.defaultTool({kind: 'video'})],
  manual: m.sortManual([{surface: 'Replicate playground'}, {surface: 'dropshot AI Studio'}, 'текст'])
    .map(x => x.surface || x.text),
  how: m.howParts('Відкрий сторінку.\n\n  curl -X POST $URL\n\nГотово.'),
  qs: m.qs({story: 'la-garganta', seq: 'part:1', x: null}),
  media: m.mediaUrl('media/lab/la garganta/a#1.png'),
  keys: [{key: 'о', code: 'KeyJ'}, {key: 'л', code: 'KeyK'}, {key: 'с', code: 'KeyC'}, {key: 'т', code: 'KeyN'},
         {key: 'j', code: 'KeyJ'}, {key: 'h', code: 'KeyJ'}, {key: 'Escape', code: 'Escape'},
         {key: 'О', code: 'KeyJ', shiftKey: true}].map(m.keyOf),
  weak: [m.needState(WEAK), m.slotState(WEAK)],
  clipSlot: [m.needState(CLIP), m.slotState(CLIP)],
  missingSlot: [m.needState(MISSING), m.needState({state: 'weak'}), m.needState({state: 'clip'}), m.needState({})],
  over: [m.isOverridden({source: {overridden: []}}), m.isOverridden({source: {overridden: ['action']}}),
         m.isOverridden({overridden: true}), m.isOverridden({extra: {overridden: []}}), m.isOverridden({}),
         m.overriddenFields({source: {overridden: ['action', 'camera']}, extra: {overridden: ['action']}})],
  approve: [m.canApprove({id: 'a', results: []}),
            m.canApprove({id: 'a', results: [{item: 'a', current: true, score: 4}]}),
            m.canApprove({id: 'a', results: [{item: 'a', current: true, score: 3}]}),
            m.canApprove({id: 'a', results: [{item: 'a', current: false, score: 5}]}),
            m.canApprove({id: 'a', results: [{item: 'a-last', current: true, score: 5}]}),
            m.canApprove({id: 'a', golden: true, results: []}),
            m.canApprove({id: 'a', status: 'approved'})],
  rewritable: [m.rewritable({source: {kind: 'test', editable: []}}), m.rewritable({source: {editable: ['action']}}),
               m.rewritable({})],
  urls: [m.safeUrl('https://aistudio.dropshot.io/'), m.safeUrl('HTTP://x.y'), m.safeUrl('javascript:alert(1)'),
         m.safeUrl('aistudio.dropshot.io'), m.safeUrl(null)],
  lastRow: [m.isLastRow({item: 'p1-1.02-video-last'}), m.isLastRow({item: 'p1-1.02-video'})],
  lastWarn: [m.lastFrameWarning('немає ffmpeg — останній кадр не витягнуто; запиши кадр руками: …'),
             m.lastFrameWarning('ffmpeg не витягнув останній кадр з a.mp4: x'), m.lastFrameWarning('інше')],
  bodies: {
    status: m.statusBody('s', 'i', 'done'),
    log: m.logBody(m.logFields('s', 'i', 'dropshot', 4, ''), ''),
    log_fields: m.logFields('s', 'i-last', 'other', 5, 'n', 'abc123'),
    approve: m.approveBody('s', 'i'),
    rewrite: m.rewriteBody('s', 'i', 'ліхтарик'),
    apply: m.applyBody('s', 'rw-1', true, 'Keep the beam on the ceiling.'),
    apply_no_lesson: m.applyBody('s', 'rw-1', false, 'ignored'),
    toggle: m.toggleBody('s', 'L1', false),
  },
};
res.bodyKeys = Object.fromEntries(Object.entries(res.bodies).map(([k, v]) => [k, Object.keys(v).sort()]));
console.log(JSON.stringify(res));
"""))
    assert out["diff"] == [["=", "the "], ["-", "old red"], ["+", "new blue"], ["=", " car stops"]]
    assert out["same"] == [["=", "a b"]]
    assert out["stat"] == {"del": 1, "ins": 2}
    assert out["warn"] == {"api": ["unknown key"], "lint": ["«boy» (вік)"], "data": ["немає кадру"]}
    assert out["warnObj"] == {"api": ["x"], "lint": [], "data": ["y"]}
    assert out["profile"] == "dropshot · 5 с · 720p"
    assert out["profile2"] == "replicate-2.5 · 4–30 с · 720p/480p"
    assert out["clip"] == [["кліп 1 з 2"], ["5 с"], ["у монтаж 0–3 с"], ["старт з кадру ", {"item": "p1-1.02-frame"}]]
    assert out["clip2"][-1] == ["старт з останнього кадру ", {"item": "p1-1.02-video"}]
    assert out["clip2"][2] == ["у монтаж 0–2.5 с"]
    assert out["clipNone"] == []
    assert out["missing"] == ["ще немає — спершу ", {"item": "loc-mina"}]
    assert out["ok"] == ["✓ є (5/5)"]
    assert out["tool"] == ["dropshot", "ai-studio", "elevenlabs", "dropshot"]
    assert out["manual"] == ["dropshot AI Studio", "Replicate playground", "текст"]
    assert out["how"] == [[False, "Відкрий сторінку."], [True, "curl -X POST $URL"], [False, "Готово."]]
    assert out["qs"] == "?story=la-garganta&seq=part%3A1"
    assert out["media"] == "/media?path=media%2Flab%2Fla%20garganta%2Fa%231.png"
    # клавіші: українська розкладка → та сама фізична клавіша; латиниця (і Dvorak) — як є; Shift — не скорочення
    assert out["keys"] == ["j", "k", "c", "n", "j", "h", "Escape", "О"]
    # сервер згортає weak / clip у missing — справжній стан видно з needs[].label
    assert out["weak"] == ["weak", ["лише 3/5 — переробити", ": ", {"item": "p1-1.02-frame"}]]
    assert out["clipSlot"][0] == "clip"
    assert out["clipSlot"][1][0].startswith("кліп є (4/5), останнього кадру ще немає")
    assert {"item": "p1-1.02-video"} in out["clipSlot"][1] and "uv run" not in json.dumps(out["clipSlot"])
    assert out["missingSlot"] == ["missing", "weak", "clip", "missing"]
    # «змінено через студію»: [] — ні, ['action'] — так
    assert out["over"] == [False, True, True, False, False, ["action", "camera"]]
    assert out["approve"] == [False, True, False, False, False, True, True]
    assert out["rewritable"] == [False, True, True]
    assert out["urls"] == ["https://aistudio.dropshot.io/", "HTTP://x.y", None, None, None]
    assert out["lastRow"] == [True, False]
    assert out["lastWarn"] == [True, True, False]
    assert out["bodyKeys"] == BODIES
    b = out["bodies"]
    assert b["status"] == {"story": "s", "item": "i", "status": "done"}
    assert b["log"]["file"] is None and b["log"]["score"] == 4
    assert b["log_fields"]["item"] == "i-last" and b["log_fields"]["prompt_sha"] == "abc123"
    assert b["log"]["prompt_sha"] is None                       # не скопіювали — сервер не звіряє
    assert b["apply"]["save_lesson"] is True and b["apply_no_lesson"]["save_lesson"] is False
    assert b["toggle"] == {"story": "s", "id": "L1", "active": False}
