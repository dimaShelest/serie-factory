"""Студія лабораторії промптів: `fabrica studio` — маленький локальний веб-застосунок (DESIGN §13, §16).

    uv run fabrica studio --sequence first30          # відкриє браузер на http://127.0.0.1:8765

Сервер — stdlib (ThreadingHTTPServer), лише 127.0.0.1; інтерфейс — fabrica/studio_ui/ (index.html, app.js,
style.css, без CDN і збірки); дані — JSON API:

    GET  /                       index.html          GET /static/<файл>   файли fabrica/studio_ui/
    GET  /media?path=<шлях>      файл з media/ або prompts/out/ (інше — 404); Range для відео (Safari)
    GET  /api/state?story=&seq=  послідовність: кроки, прогрес, «Далі», елементи (промпт, payload, референси …)
    POST /api/status             {story, item, status}                → {ok}        (lab/progress.yaml)
    POST /api/log                {story, item, tool, score, notes, file, prompt_sha} або multipart (поле upload)
                                                                      → {entry, warnings}   (lab.log)
                                 prompt_sha — скопійована версія промпту: змінився відтоді → 409
    POST /api/approve            {story, item[, force]}               → {message}   (lab.approve)
    POST /api/rewrite            {story, item, feedback}              → {proposal}  (rewrite.propose)
    POST /api/rewrite/apply      {story, proposal, save_lesson, rule} → {ok, item}  (overrides.yaml + lessons.yaml)
    GET  /api/lessons?story=     → {lessons}         POST /api/lessons/toggle {story, id, active} → {ok}

Помилки — HTTP 4xx / 5xx з {"error": "<українською>"}. Запити — лише з 127.0.0.1 / localhost на цьому самому порту
(Host і Origin), POST — лише JSON або multipart; /media — лише медіа-файли з media/ і prompts/out/, шлях
перевіряється рядком до звертання до диска (UNC, «..»). Мережа — лише localhost і бекенд переписувача;
платної генерації студія не запускає. Елементи збираються один раз і кешуються, доки не зміняться файли
(series/<slug>/, шаблони, каталоги, shots.json / script.json, GENERATION_PROFILE).
"""

from __future__ import annotations

import json
import mimetypes
import re
import sys
import tempfile
import threading
import traceback
import webbrowser
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

from fabrica import bible as bible_mod
from fabrica import config
from fabrica import lab as lab_mod
from fabrica import lessons as lessons_mod
from fabrica import lint as lint_mod
from fabrica import progress as progress_mod
from fabrica import prompts as prompts_mod
from fabrica import providers as providers_mod
from fabrica import rewrite as rewrite_mod
from fabrica import viewer as viewer_mod

UI = Path(__file__).with_name("studio_ui")
PORT = 8765
MAX_BODY = 600 * 1024 * 1024               # відео 720p × 5 с — десятки МБ; більше — точно помилка
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml",
         ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
         ".gif": "image/gif", ".avif": "image/avif",
         ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
         ".mkv": "video/x-matroska",
         ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".flac": "audio/flac",
         ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8"}
STATIC_RE = re.compile(r"[A-Za-z0-9_-]+\.(?:html|js|css|svg|png|ico)")       # файли fabrica/studio_ui/, без тек
CHUNK = 1024 * 1024
NEED_STATE = {"golden": "golden", "ok": "ok", "nofile": "nofile"}       # решта (weak, clip, missing) → missing
WARN_KEYS = {"API": "api", "lint": "lint", "дані": "data"}
SEQ_TITLES = {"casting": "Кастинг", "test-pack": "Тест-пак"}


class StudioError(Exception):
    """Помилка запиту: HTTP-код + повідомлення українською."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def media_roots() -> list[Path]:
    """Звідки /media віддає файли: media/ (журнал лабораторії) і prompts/out/ (пакети)."""
    return [config.ROOT / "media", lab_mod.MEDIA, prompts_mod.OUT]


def media_file(path: str) -> Path | None:
    """Шлях із журналу → файл-медіа (lab.FILE_TYPES), лише якщо він під media_roots. Спершу — перевірка рядка, ДО
    будь-якого звертання до диска: «\\», «//…» (UNC: Windows пішов би на чужий SMB-сервер і віддав NTLM-хеш), «..»,
    чужий корінь; потім resolve (symlink-втечі)."""
    if not path or "\x00" in path or "\\" in path or path.startswith("//") or ".." in path.split("/"):
        return None
    p = Path(path)
    if p.suffix.lower() not in lab_mod.FILE_TYPES:
        return None
    p = p if p.is_absolute() else config.ROOT / p
    roots = media_roots()
    if not any(p.is_relative_to(r) for r in roots + [r.resolve() for r in roots]):
        return None
    p = p.resolve()
    return p if p.is_file() and any(p.is_relative_to(r.resolve()) for r in roots) else None


def media_url(path: str | None) -> str | None:
    return f"/media?path={quote(str(path), safe='')}" if path and media_file(str(path)) else None


def default_story() -> str:
    found = [p.name for p in bible_mod.SERIES.iterdir() if (p / "bible.yaml").exists() and not p.name.startswith("_")]
    if len(found) != 1:
        raise StudioError(400, f"вкажи story (серіали: {', '.join(sorted(found)) or 'немає'})")
    return found[0]


def safe_name(name: str) -> str:
    """Ім'я завантаженого файлу → латиниця, цифри, «-», «_», «.» (Windows і журнал)."""
    stem, suffix = Path(Path(name or "upload").name).stem, Path(name or "").suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "upload"
    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,5}", suffix) else ""
    return f"{stem[:60]}{suffix}"


# ---------------------------------------------------------------- стан


class _Ctx:
    """Усе для карток однієї послідовності: журнал / golden (Pack), перенос стану, прогрес, джерела."""

    def __init__(self, slug: str, items: list[prompts_mod.Item], producers: list[prompts_mod.Item]) -> None:
        self.slug, self.items = slug, items
        self.pack = viewer_mod.Pack(slug, items, producers)
        self.carry = viewer_mod.carry_over(items)
        self.progress = progress_mod.load(slug)
        self.data = prompts_mod.Data(slug)
        self.src_cache: dict = {}
        try:
            self.lessons = {x.get("id"): x for x in lessons_mod.load(slug)}
        except lessons_mod.LessonError:
            self.lessons = {}


class Studio:
    """Стан і дії студії. Кеш зібраних елементів — за (історія, послідовність) і відбитком файлів."""

    def __init__(self, story: str | None = None, sequence: str | None = None) -> None:
        self.story, self.sequence = story, sequence
        self._cache: dict[tuple[str, str], tuple[tuple, list[prompts_mod.Item]]] = {}
        self._build = threading.RLock()
        self._write = threading.Lock()

    # ------------------------------------------------------------ збірка

    def slug(self, story: str | None) -> str:
        slug = (story or self.story or default_story()).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug) or not (bible_mod.SERIES / slug / "bible.yaml").exists():
            raise StudioError(404, f"серіалу «{slug}» немає (series/<slug>/bible.yaml)")
        return slug

    def default_seq(self, slug: str) -> str:
        if self.sequence:
            return self.sequence
        seqs = prompts_mod.sequences(slug)
        return next(iter(seqs), "casting")

    @staticmethod
    def fingerprint(slug: str) -> tuple:
        files = [p for p in (bible_mod.SERIES / slug).rglob("*") if p.is_file()]
        files += [p for p in prompts_mod.TEMPLATES.rglob("*.yaml")]
        files += [providers_mod.CATALOG, lint_mod.LINT]
        out = prompts_mod.OUTPUT / slug
        files += [f for d in sorted(out.glob("part*")) for f in (d / "shots.json", d / "script.json")]
        stats = []
        for f in files:
            try:
                st = f.stat()
                stats.append((f.as_posix(), st.st_mtime_ns, st.st_size))
            except OSError:
                stats.append((f.as_posix(), 0, -1))
        return tuple(sorted(stats)), config.get("GENERATION_PROFILE")

    def _set_items(self, slug: str, seq: str) -> list[prompts_mod.Item]:
        if seq in ("casting", "test-pack"):
            return prompts_mod.build(slug, seq)
        if m := re.fullmatch(r"part:([1-4])", seq):
            return prompts_mod.build(slug, m.group(1))
        if re.fullmatch(r"[1-4]", seq):
            return prompts_mod.build(slug, seq)
        return prompts_mod.sequence_items(slug, seq)

    def items(self, slug: str, seq: str) -> list[prompts_mod.Item]:
        with self._build:
            fp = self.fingerprint(slug)
            hit = self._cache.get((slug, seq))
            if hit and hit[0] == fp:
                return hit[1]
            items = self._set_items(slug, seq)
            self._cache[(slug, seq)] = (fp, items)
            return items

    def producers(self, slug: str, seq: str) -> list[prompts_mod.Item]:
        """Кастинг для станів референсів (частина й тест-пак його не містять; послідовність — уже містить)."""
        if seq == "casting" or seq in prompts_mod.sequences(slug):
            return []
        return self.items(slug, "casting")

    def find(self, slug: str, item_id: str, seq: str | None = None) -> tuple[prompts_mod.Item, str]:
        """Елемент за id → (елемент, послідовність, де він є): спершу seq, далі кешовані, далі набір за id."""
        order = [seq] if seq else []
        order += [k[1] for k in list(self._cache) if k[0] == slug and k[1] not in order]
        for s in order:
            try:
                hit = next((i for i in self.items(slug, s) if i.id == item_id), None)
            except (prompts_mod.PromptError, ValueError):
                continue
            if hit:
                return hit, s
        set_name = prompts_mod.set_of(item_id)
        s = "casting" if set_name == "casting" else "test-pack" if set_name == "test-pack" else f"part:{set_name}"
        hit = next((i for i in self.items(slug, s) if i.id == item_id), None)
        if hit is None:
            raise StudioError(404, f"елемента «{item_id}» немає в наборі «{set_name}»")
        return hit, s

    def ctx(self, slug: str, seq: str) -> _Ctx:
        return _Ctx(slug, self.items(slug, seq), self.producers(slug, seq))

    # ------------------------------------------------------------ JSON

    def sequences(self, slug: str) -> list[dict]:
        out = [{"name": k, "title": v.get("title", k), "part": v.get("part")}
               for k, v in prompts_mod.sequences(slug).items()]
        for d in sorted((prompts_mod.OUTPUT / slug).glob("part[1-4]")):
            if (d / "shots.json").exists():
                n = d.name.removeprefix("part")
                out.append({"name": f"part:{n}", "title": f"Частина {n} — усе", "part": int(n)})
        out.append({"name": "casting", "title": SEQ_TITLES["casting"]})
        if (bible_mod.SERIES / slug / "lab" / "test_pack.yaml").exists():
            out.append({"name": "test-pack", "title": SEQ_TITLES["test-pack"]})
        return out

    @staticmethod
    def profile() -> dict:
        try:
            return providers_mod.generation()
        except providers_mod.ProviderError as e:
            return {"name": "", "error": str(e)}

    def need(self, c: _Ctx, label: str, ref: str) -> dict:
        s = c.pack.ref(ref)
        file = s.file or ((s.row or {}).get("file") if s.state == "nofile" else None)
        return {"ref": ref, "slot": label, "state": NEED_STATE.get(s.state, "missing"),
                "item": s.producer.id if s.producer else None, "file": file, "score": (s.row or {}).get("score"),
                "label": s.label(c.slug), "url": media_url(s.file)}

    @staticmethod
    def manual(item: prompts_mod.Item) -> list[dict]:
        """Інструкції поверхонь (extra.manual) у форму контракту: text (проза), cmd (команди), body (JSON), json."""
        try:
            route_surface = providers_mod.route(item.route).manual.get("surface") if item.route else None
        except providers_mod.ProviderError:
            route_surface = None
        out = []
        for m in viewer_mod.manual(item):
            parts = viewer_mod.how_parts(m.get("how") or m.get("text"))
            body = m.get("body")
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except ValueError:
                    pass
            row = {"surface": m.get("surface") or "", "title": m.get("title") or "",
                   "text": "\n\n".join(t for cmd, t in parts if not cmd),
                   "cmd": "\n\n".join(t for cmd, t in parts if cmd) or m.get("cmd") or "",
                   "url": m.get("url") or "", "endpoint": m.get("endpoint") or "", "body": body,
                   "json": m.get("json") if m.get("json") is not None else
                   (item.payload if route_surface and m.get("surface") == route_surface and not body else None),
                   "note": m.get("note") or ""}
            out.append(row)
        return out

    def item_json(self, c: _Ctx, item: prompts_mod.Item) -> dict:
        golden = c.pack.golden(item)
        current = c.pack.current(item)
        passed = any(r.get("score", 0) >= lab_mod.PASS_SCORE for r in current)
        status, stale = progress_mod.effective(c.progress.get(item.id), item.prompt_sha, golden=golden, passed=passed)
        lesson_ids = [x if isinstance(x, str) else x.get("id") for x in item.extra.get("lessons") or []]
        hits = lessons_mod.lint_hits(c.slug, rewrite_mod.lesson_ids(item), item.prompt) if c.lessons else []
        warns = {WARN_KEYS[k]: v for k, v in viewer_mod.split_warnings(item.warnings + hits).items()}
        extra = {k: v for k, v in item.extra.items() if k not in ("manual", "lessons", "state_in", "state_out")}
        st_in, st_out = viewer_mod.state_in(item, c.carry), item.extra.get("state_out") or []
        extra |= {"lessons": lesson_ids, "lessons_text": [f"{i}: {c.lessons[i].get('rule')}" if i in c.lessons else i
                                                          for i in lesson_ids],
                  "state_in": "; ".join(map(str, st_in)) if st_in else None,
                  "state_out": "; ".join(map(str, st_out)) if isinstance(st_out, list) and st_out else
                  (st_out or None)}
        rows = c.pack.rows.get(item.id, []) + (c.pack.rows.get(item.id + lab_mod.LAST, []) if item.kind == "video"
                                              else [])
        results = [{"id": r.get("id"), "item": r.get("item"), "at": r.get("at"), "tool": r.get("tool"),
                    "score": r.get("score"), "notes": r.get("notes") or "", "file": r.get("file"),
                    "last_frame": r.get("last_frame"), "current": r.get("prompt_sha") == item.prompt_sha,
                    "url": media_url(r.get("file")), "last_url": media_url(r.get("last_frame")),
                    "local": bool(media_url(r.get("file")))}
                   for r in sorted(rows, key=lambda r: r.get("id", 0), reverse=True)]
        try:
            source = rewrite_mod.source_of(c.slug, item, c.data, c.src_cache)
        except (ValueError, OSError) as e:
            source = {"kind": "other", "key": item.id, "fields": {}, "editable": [], "error": str(e)}
        return {"id": item.id, "set": item.set, "step": item.step, "kind": item.kind, "title": item.title,
                "route": item.route, "prompt": item.prompt, "payload": item.payload, "prompt_sha": item.prompt_sha,
                "template": item.template.ref, "status": status, "stale": stale, "golden": golden,
                "produces": item.produces, "refs": item.refs,
                "needs": [self.need(c, label, ref) for label, ref in viewer_mod.slots(item)],
                "manual": self.manual(item), "warnings": warns, "extra": extra, "results": results,
                "source": source}

    def state(self, story: str | None, seq: str | None) -> dict:
        slug = self.slug(story)
        seq = (seq or self.default_seq(slug)).strip()
        c = self.ctx(slug, seq)
        items = [self.item_json(c, i) for i in c.items]
        ready = {i["id"]: all(n["state"] in ("ok", "golden") for n in i["needs"]) for i in items}
        nxt = progress_mod.next_id([(i["id"], i["status"], ready[i["id"]]) for i in items])
        closed = [i for i in items if i["status"] in progress_mod.CLOSED]
        steps = [{"n": s.n, "key": s.key, "title": s.title, "todo": s.todo, "tool": s.tool,
                  "total": sum(1 for i in items if i["step"] == s.n),
                  "done": sum(1 for i in closed if i["step"] == s.n)} for s in prompts_mod.STEPS]
        return {"story": slug, "seq": seq, "sequences": self.sequences(slug), "profile": self.profile(),
                "budget": self.budget(slug, seq, c, items),
                "rewrite_backend": rewrite_mod.backend_status(), "steps": steps,
                "progress": {"done": len(closed), "total": len(items), "next": nxt,
                             "approved": sum(1 for i in items if i["status"] == "approved"),
                             "skipped": sum(1 for i in items if i["status"] == "skip")},
                "items": items}

    @staticmethod
    def budget(slug: str, seq: str, c: _Ctx, items: list[dict]) -> dict | None:
        """Ліміт тестів послідовності (sequences.yaml budget_usd): оцінка за прайсом API — кожен записаний результат
        відео = одна платна генерація за ціною поточного payload. None — у послідовності ліміту немає."""
        limit = (prompts_mod.sequences(slug).get(seq) or {}).get("budget_usd")
        if not limit:
            return None
        price = {i.id: providers_mod.price(i.route, i.payload) or 0.0 for i in c.items if i.kind == "video"}
        runs = {x["id"]: sum(1 for r in x["results"] if r["item"] == x["id"])      # «<кліп>-last» — кадр, не генерація
                for x in items if x["id"] in price}
        spent = sum(price[k] * n for k, n in runs.items())
        per_pass = sum(price.values())
        return {"limit": float(limit), "spent": round(spent, 2), "per_pass": round(per_pass, 2),
                "runs": sum(runs.values()), "left": round(float(limit) - spent, 2),
                "left_passes": int((float(limit) - spent) // per_pass) if per_pass else None}

    # ------------------------------------------------------------ дії

    def set_status(self, body: dict) -> dict:
        slug, item_id, status = self.slug(body.get("story")), _req(body, "item"), _req(body, "status")
        item, _ = self.find(slug, item_id, body.get("seq"))
        with self._write:
            progress_mod.set_status(slug, item.id, status, item.prompt_sha)
        return {"ok": True}

    def log(self, body: dict, upload: tuple[str, bytes] | None = None) -> dict:
        slug, item_id = self.slug(body.get("story")), _req(body, "item")
        try:
            score = int(body.get("score"))
        except (TypeError, ValueError):
            raise StudioError(400, "оцінка — ціле число від 1 до 5") from None
        tool, notes = str(body.get("tool") or "").strip(), str(body.get("notes") or "")
        copied = body.get("prompt_sha")
        if isinstance(copied, str) and copied.strip():
            item, _ = self.find(slug, item_id.removesuffix(lab_mod.LAST), body.get("seq"))
            if copied.strip() != item.prompt_sha:
                raise StudioError(409, f"промпт «{item.id}» змінився після копіювання (правка, урок або файли "
                                       "серіалу) — результат старого промпту не записую: скопіюй промпт ще раз "
                                       "і згенеруй заново")
        with self._write, tempfile.TemporaryDirectory(prefix="studio-") as tmp:
            file = None
            if upload:
                file = Path(tmp) / safe_name(upload[0])
                file.write_bytes(upload[1])
            elif str(body.get("file") or "").strip():
                file = Path(str(body["file"]).strip().strip("'\"")).expanduser()
            entry = lab_mod.log(slug, item_id, tool, score, file, notes)
            warnings = entry.pop("warnings", [])
            status = None
            if entry["item"] == item_id and not item_id.endswith(lab_mod.LAST):
                status = progress_mod.on_log(slug, item_id, score, entry["prompt_sha"])
        return {"entry": entry, "warnings": warnings, "status": status,
                "url": media_url(entry.get("file")), "last_url": media_url(entry.get("last_frame"))}

    def approve(self, body: dict) -> dict:
        slug, item_id = self.slug(body.get("story")), _req(body, "item")
        with self._write:
            msg = lab_mod.approve(slug, item_id, force=bool(body.get("force")))
            if item_id not in prompts_mod.load_templates():
                item, _ = self.find(slug, item_id, body.get("seq"))
                progress_mod.set_status(slug, item.id, "approved", item.prompt_sha)
        return {"message": msg}

    def rewrite(self, body: dict) -> dict:
        slug, item_id = self.slug(body.get("story")), _req(body, "item")
        p = rewrite_mod.propose(slug, item_id, str(body.get("feedback") or ""))
        return {"proposal": rewrite_mod.public(p)}

    def apply(self, body: dict) -> dict:
        slug, pid = self.slug(body.get("story")), _req(body, "proposal")
        rule = body.get("rule")
        with self._write:
            res = rewrite_mod.apply(slug, pid, save_lesson=bool(body.get("save_lesson", True)),
                                    rule=rule if isinstance(rule, str) else None)
        seq = body.get("seq") or self.default_seq(slug)
        try:
            item, seq = self.find(slug, res["item"], seq)
        except StudioError:
            return {"ok": True, "item": None, "lesson": res["lesson"]}
        return {"ok": True, "item": self.item_json(self.ctx(slug, seq), item), "lesson": res["lesson"]}

    def lessons(self, story: str | None) -> dict:
        return {"lessons": lessons_mod.all(self.slug(story))}

    def toggle(self, body: dict) -> dict:
        slug, lid = self.slug(body.get("story")), _req(body, "id")
        if not isinstance(body.get("active"), bool):
            raise StudioError(400, "active — true або false")
        with self._write:
            lessons_mod.set_active(slug, lid, body["active"])
        return {"ok": True}


def _req(body: dict, key: str) -> str:
    v = body.get(key)
    if not isinstance(v, str) or not v.strip():
        raise StudioError(400, f"бракує поля «{key}»")
    return v.strip()


# ---------------------------------------------------------------- HTTP


class Handler(BaseHTTPRequestHandler):
    server_version = "fabrica-studio"
    quiet = False

    @property
    def studio(self) -> Studio:
        return self.server.studio                              # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:           # лише помилки, без тіл запитів
        if not self.quiet and len(args) > 1 and str(args[1])[:1] in "45":
            sys.stderr.write(f"studio: {self.command} {self.path.split('?')[0]} → {args[1]}\n")

    # ------------------------------------------------------------ відповіді

    def _head(self, status: int, ctype: str, length: int, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self._head(status, ctype, len(body), extra)
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _file(self, path: Path) -> None:
        """Файл частинами по CHUNK (відео — десятки МБ: не тримаємо в пам'яті); Range — для перемотки (Safari)."""
        ctype = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        start, end, status, extra = 0, size - 1, 200, {"Accept-Ranges": "bytes"}
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if rng and (rng.group(1) or rng.group(2)):
            a, b = rng.groups()
            start = int(a) if a else max(0, size - int(b))
            end = min(int(b), size - 1) if a and b else size - 1
            if start >= size or start > end:
                self._send(416, b"", ctype, {"Content-Range": f"bytes */{size}"})
                return
            status, extra = 206, extra | {"Content-Range": f"bytes {start}-{end}/{size}"}
        self._head(status, ctype, end - start + 1, extra)
        if self.command == "HEAD":
            return
        with path.open("rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0 and (chunk := f.read(min(CHUNK, left))):
                self.wfile.write(chunk)
                left -= len(chunk)

    # ------------------------------------------------------------ безпека

    def _local(self) -> bool:
        """Захист від DNS rebinding і чужих сторінок: Host і Origin (якщо є) — лише 127.0.0.1 / localhost І саме
        цей порт (інший локальний сервер — dev-сервер, чужий застосунок — теж «чужа сторінка»)."""
        port = self.server.server_address[1]
        hosts = {"127.0.0.1", "localhost", "::1"}
        host = self.headers.get("Host")
        if host is not None:
            u = urlsplit(f"//{host}")
            try:
                if (u.hostname or "") not in hosts or (u.port or 80) != port:
                    return False
            except ValueError:                                    # «host:abc» — зламаний порт
                return False
        origin = self.headers.get("Origin")                      # «null» — sandbox-iframe чужої сторінки: ні
        if origin is not None:
            u = urlsplit(origin)
            try:
                if u.scheme != "http" or (u.hostname or "") not in hosts or (u.port or 80) != port:
                    return False
            except ValueError:
                return False
        return True

    # ------------------------------------------------------------ маршрути

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        self._handle(self._get)

    def do_POST(self) -> None:
        self._handle(self._post)

    def _handle(self, fn) -> None:
        try:
            if not self._local():
                raise StudioError(403, "студія приймає запити лише з 127.0.0.1 / localhost (цей самий порт)")
            fn()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):   # браузер закрив з'єднання
            self.close_connection = True                             # (перемотка відео, оновлення сторінки) — тихо
        except StudioError as e:
            self._error(e.status, str(e))
        except FileNotFoundError as e:
            self._error(404, f"немає файлу: {e.filename or e}")
        except (ValueError, KeyError, lab_mod.GoldenError) as e:      # PromptError, SpecError, LabError, …
            self._error(400, str(e).strip("'\""))
        except Exception as e:                                       # noqa: BLE001 — сервер не падає
            traceback.print_exc(file=sys.stderr)
            self._error(500, f"внутрішня помилка студії: {type(e).__name__}: {e}")

    def _get(self) -> None:
        url = urlsplit(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        path = url.path
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path.removeprefix("/static/"))
        if path == "/media":
            f = media_file(q.get("path", ""))
            if f is None:
                raise StudioError(404, "файлу немає або він не з media/ чи prompts/out/")
            return self._file(f)
        if path == "/api/state":
            return self._json(self.studio.state(q.get("story"), q.get("seq")))
        if path == "/api/lessons":
            return self._json(self.studio.lessons(q.get("story")))
        if path == "/favicon.ico":
            return self._send(204, b"", "image/x-icon")
        raise StudioError(404, f"немає такої сторінки: {path}")

    def _static(self, name: str) -> None:
        name = unquote(name)
        root = UI.resolve()
        f = (root / name).resolve() if STATIC_RE.fullmatch(name) else None
        if f is None or not f.is_relative_to(root) or not f.is_file():
            raise StudioError(404, "інтерфейсу студії немає (fabrica/studio_ui/)" if name == "index.html"
                              else f"немає файлу інтерфейсу: {name}")
        self._file(f)

    def _body(self) -> tuple[dict, tuple[str, bytes] | None]:
        size = int(self.headers.get("Content-Length") or 0)
        if size > MAX_BODY:
            raise StudioError(413, f"файл завеликий (> {MAX_BODY // 1024 // 1024} МБ)")
        raw = self.rfile.read(size) if size else b""            # спершу дочитати: інакше клієнт отримає RST, а не 415
        ctype = self.headers.get("Content-Type") or ""
        multipart = ctype.lower().startswith("multipart/form-data")
        # лише JSON або multipart: «простий» POST чужої сторінки (text/plain, form-urlencoded) іде без CORS-перевірки
        if not multipart and ctype.split(";")[0].strip().lower() != "application/json":
            raise StudioError(415, "тіло запиту — JSON (Content-Type: application/json) або multipart/form-data")
        if multipart:
            return _multipart(ctype, raw)
        try:
            body = json.loads(raw.decode("utf-8-sig") or "{}")
        except ValueError:
            raise StudioError(400, "тіло запиту — не JSON") from None
        if not isinstance(body, dict):
            raise StudioError(400, "тіло запиту — JSON-об'єкт {…}")
        return body, None

    def _post(self) -> None:
        path = urlsplit(self.path).path
        routes = {"/api/status": self.studio.set_status, "/api/approve": self.studio.approve,
                  "/api/rewrite": self.studio.rewrite, "/api/rewrite/apply": self.studio.apply,
                  "/api/lessons/toggle": self.studio.toggle}
        if path != "/api/log" and path not in routes:
            raise StudioError(404, f"немає такої дії: {path}")
        body, upload = self._body()
        if path == "/api/log":
            return self._json(self.studio.log(body, upload))
        if upload:
            raise StudioError(400, "файл можна надіслати лише в /api/log")
        self._json(routes[path](body))


def _multipart(ctype: str, raw: bytes) -> tuple[dict, tuple[str, bytes] | None]:
    """multipart/form-data → (поля, (ім'я файлу, байти) з поля upload). stdlib email-парсер (cgi вже немає)."""
    msg = BytesParser(policy=email_policy).parsebytes(
        f"Content-Type: {ctype}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1") + raw)
    if not msg.is_multipart():
        raise StudioError(400, "зламаний multipart/form-data")
    fields, upload = {}, None
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        if name == "upload" and part.get_filename() is not None:
            if data:
                upload = (part.get_filename() or "upload", data)
        else:
            fields[name] = data.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, upload


class Server(ThreadingHTTPServer):
    allow_reuse_address = sys.platform != "win32"      # Windows: SO_REUSEADDR дозволив би чужий bind на порт
    daemon_threads = True


def make_server(port: int = PORT, story: str | None = None, sequence: str | None = None,
                quiet: bool = False) -> Server:
    """Сервер на 127.0.0.1:port (0 — вільний порт, для тестів). Запуск — serve_forever()."""
    handler = type("StudioHandler", (Handler,), {"quiet": quiet})
    srv = Server(("127.0.0.1", port), handler)
    srv.studio = Studio(story, sequence)                    # type: ignore[attr-defined]
    return srv


def serve(story: str | None = None, sequence: str | None = None, port: int = PORT, open_browser: bool = True,
          log=print) -> None:
    """Запустити студію й (типово) відкрити браузер; Ctrl+C — зупинити."""
    try:
        srv = make_server(port, story, sequence)
    except OSError as e:
        raise StudioError(400, f"порт {port} зайнятий або недоступний ({e.strerror or e}) — спробуй "
                               f"`fabrica studio --port {port + 1}`") from None
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    if not (UI / "index.html").exists():
        log(f"⚠️ немає {UI.name}/index.html — працює лише JSON API ({url}api/state)")
    log(f"Студія: {url}  (Ctrl+C — зупинити)")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log("Студію зупинено.")
    finally:
        srv.server_close()
