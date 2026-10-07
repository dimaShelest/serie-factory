"""Уроки лабораторії: series/<slug>/lab/lessons.yaml — правила, які компілятори дописують у промпти (DESIGN §13).

Формат (YAML, у Git; файлу немає — уроків немає):

    lessons:
      - id: L1                                    # унікальний
        at: "2026-10-07T21:00:00+03:00"           # коли записано
        item: p1-1.02-video                       # де помітили
        route: replicate:bytedance/seedance-2.5   # на чому помітили (довідка; фільтр — у scope)
        kind: video                               # image | video
        problem: "Камера тремтить, хоч просили статичну"     # людським текстом, українською
        rule: "The camera stays locked off on a tripod for the whole clip."   # ОДНЕ позитивне речення англійською
        scope: {kind: video, route: …, template: video.i2v, location: mina, character: lupita, tags: [vhs]}
        priority: 0                               # більше — важливіше; бракує місця — першими випадають менші
        active: true                              # false — вимкнено (історія лишається)

scope: кожен заданий ключ має збігтися, незаданий — будь-який. kind / route / template — з елементом;
location / character — з мітками елемента «location:<id>», «character:<id>»; tags — кожен або мітка дослівно
(«footage:vhs»), або значення будь-якої мітки («vhs»). Мітки ставить компілятор: location, character, footage, mode,
beat, tier, set. Компілятор дописує rule у слот LESSONS (перед сталими реченнями), id — в extra["lessons"].
Репліки (voice) уроків не отримують: rule було б озвучено.

avoid (необов'язково) — список regex (без урахування регістру): що урок забороняє; знайдене в промпті елемента, до
якого урок застосовано, — попередження «lint: урок L3: «…» …» (lint_hits). Студія додає уроки (add), вмикає й
вимикає (set_active; `fabrica lab lessons --off L3`); пропозиція переписувача показує новий урок у промпті ще до
запису (pending).
"""

from __future__ import annotations

import builtins
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fabrica import bible as bible_mod
from fabrica import config

KEYS = {"id", "at", "item", "route", "kind", "problem", "rule", "scope", "priority", "active", "avoid"}
SCOPE = {"kind", "route", "template", "location", "character", "tags"}


class LessonError(ValueError):
    """lessons.yaml зламаний — повідомлення пояснює, що виправити."""


def path(slug: str) -> Path:
    return bible_mod.SERIES / slug / "lab" / "lessons.yaml"


_CACHE: dict[Path, tuple[tuple[int, int], list[dict]]] = {}


def _check(i: int, raw, name: str) -> list[str]:
    where = f"{name} · урок {raw.get('id', f'#{i}') if isinstance(raw, dict) else f'#{i}'}"
    if not isinstance(raw, dict):
        return [f"{where}: потрібен словник {{id, rule, scope, …}}"]
    errs = [f"{where}: невідомі ключі {sorted(map(str, extra))}"] if (extra := set(raw) - KEYS) else []
    if not isinstance(raw.get("id"), str) or not raw["id"].strip():
        errs.append(f"{where}: потрібен id (рядок)")
    if not isinstance(raw.get("rule"), str) or not raw["rule"].strip():
        errs.append(f"{where}: потрібне rule — одне позитивне речення англійською")
    scope = raw.get("scope") or {}
    if not isinstance(scope, dict) or set(scope) - SCOPE:
        errs.append(f"{where}: scope — словник із {', '.join(sorted(SCOPE))}")
    elif "tags" in scope and not isinstance(scope["tags"], list):
        errs.append(f"{where}: scope.tags — список")
    if not isinstance(raw.get("priority", 0), int) or not isinstance(raw.get("active", True), bool):
        errs.append(f"{where}: priority — ціле, active — true / false")
    avoid = raw.get("avoid") or []
    if not isinstance(avoid, list) or not builtins.all(isinstance(x, str) and x.strip() for x in avoid):
        errs.append(f"{where}: avoid — список regex-рядків")
    else:
        for x in avoid:
            try:
                re.compile(x)
            except re.error as e:
                errs.append(f"{where}: avoid «{x}» — зламаний regex ({e})")
    return errs


def load(slug: str) -> list[dict]:
    """Усі уроки (і вимкнені) з lessons.yaml (+ урок «на пробу», pending); файлу немає — []. Зламано → LessonError."""
    return _file(slug) + [dict(x) for x in (_PENDING.get() or {}).get(slug, [])]


def _file(slug: str) -> list[dict]:
    p = path(slug)
    try:
        st = p.stat()
    except FileNotFoundError:
        return []
    key = (st.st_mtime_ns, st.st_size)
    if (hit := _CACHE.get(p)) and hit[0] == key:
        return [dict(x) for x in hit[1]]
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as e:
        raise LessonError(f"{p.name}: YAML не читається — {e}") from None
    rows = raw.get("lessons") if isinstance(raw, dict) else None
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise LessonError(f"{p.name}: очікую lessons: [список уроків]")
    errs = [e for i, r in enumerate(rows, 1) for e in _check(i, r, p.name)]
    ids = [r.get("id") for r in rows if isinstance(r, dict)]
    errs += [f"{p.name}: id «{x}» повторюється" for x in dict.fromkeys(ids) if ids.count(x) > 1]
    if errs:
        raise LessonError("\n".join(errs))
    _CACHE[p] = (key, rows)
    return [dict(x) for x in rows]


def _fits(scope: dict, kind: str, route: str, template_id: str, tags: set[str]) -> bool:
    for k, want in (("kind", kind), ("route", route), ("template", template_id)):
        if scope.get(k) and scope[k] != want:
            return False
    for k in ("location", "character"):
        if scope.get(k) and f"{k}:{scope[k]}" not in tags:
            return False
    return builtins.all(t in tags or any(x.endswith(f":{t}") for x in tags) for t in scope.get("tags") or [])


def match(slug: str, item_kind: str, route: str, template_id: str, tags: set[str]) -> list[dict]:
    """Активні уроки, що стосуються елемента: від найважливішого (priority) до найменш важливого, далі — за порядком."""
    found = [(i, r) for i, r in enumerate(load(slug))
             if r.get("active", True) and _fits(r.get("scope") or {}, item_kind, route, template_id, tags)]
    return [r for _, r in sorted(found, key=lambda x: (-x[1].get("priority", 0), x[0]))]


def rules_for(slug: str, item_kind: str, route: str, template_id: str, tags: set[str]) -> list[str]:
    """Речення активних уроків для промпту (порядок — як у match)."""
    return [r["rule"].strip() for r in match(slug, item_kind, route, template_id, tags)]


# ---------------------------------------------------------------- запис (студія, `fabrica lab lessons`)

_PENDING: ContextVar[dict[str, list[dict]] | None] = ContextVar("pending_lessons", default=None)
HEADER = ("# Уроки лабораторії (fabrica/lessons.py): правило rule дописується в промпти елементів, яким підходить scope.\n"
          "# Додає студія (кнопка «Редагувати» → «зберегти урок»); вимкнути — `uv run fabrica lab lessons --off L3`.\n")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _head(p: Path) -> str:
    """Коментарі на початку файлу — зберігаємо при перезаписі (решту коментарів запис не тримає)."""
    if not p.exists():
        return HEADER
    lines = p.read_text(encoding="utf-8-sig").splitlines()
    head = [x for x in lines[:next((i for i, x in enumerate(lines) if x.strip() and not x.lstrip().startswith("#")),
                                   len(lines))]]
    return "\n".join(head).rstrip() + "\n" if any(x.strip() for x in head) else HEADER


def _save(slug: str, rows: list[dict]) -> None:
    p = path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    head = _head(p)
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(head + "\n")
        yaml.safe_dump({"lessons": rows}, f, allow_unicode=True, sort_keys=False, width=110)
    config.replace_atomic(tmp, p)
    _CACHE.pop(p, None)


def all(slug: str) -> list[dict]:          # noqa: A001 — назва з контракту студії (DESIGN §16)
    """Усі уроки з файлу (і вимкнені), по порядку; без уроку «на пробу»."""
    return _file(slug)


def next_id(slug: str) -> str:
    nums = [int(m.group(1)) for r in _file(slug) if (m := re.fullmatch(r"L(\d+)", str(r.get("id"))))]
    return f"L{max(nums, default=0) + 1}"


def clean(lesson: dict, lid: str) -> dict:
    """Урок від людини / переписувача → запис lessons.yaml (порядок ключів як у шапці); зайві ключі — LessonError."""
    if extra := set(lesson) - KEYS:
        raise LessonError(f"урок: невідомі ключі {sorted(extra)}")
    scope = {k: v for k, v in (lesson.get("scope") or {}).items() if v not in (None, "", [])} \
        if isinstance(lesson.get("scope") or {}, dict) else lesson.get("scope")
    row = {"id": lid, "at": lesson.get("at") or _now(), "item": lesson.get("item"), "route": lesson.get("route"),
           "kind": lesson.get("kind"), "problem": str(lesson.get("problem") or "").strip(),
           "rule": str(lesson.get("rule") or "").strip(), "scope": scope, "priority": lesson.get("priority", 0),
           "avoid": lesson.get("avoid") or [], "active": lesson.get("active", True)}
    row = {k: v for k, v in row.items() if v not in (None, []) or k in ("scope",)}
    if errs := _check(1, row, "lessons.yaml"):
        raise LessonError("\n".join(errs))
    return row


def add(slug: str, lesson: dict) -> str:
    """Дописати урок у series/<slug>/lab/lessons.yaml → id (L1, L2 …)."""
    rows = _file(slug)
    lid = next_id(slug)
    _save(slug, rows + [clean({k: v for k, v in lesson.items() if k != "id"}, lid)])
    return lid


def set_active(slug: str, lid: str, active: bool) -> dict:
    """Увімкнути / вимкнути урок (історія лишається) → оновлений урок."""
    rows = _file(slug)
    hit = next((r for r in rows if r.get("id") == lid), None)
    if hit is None:
        raise LessonError(f"уроку «{lid}» немає (є: {', '.join(str(r.get('id')) for r in rows) or '—'})")
    hit["active"] = bool(active)
    _save(slug, rows)
    return dict(hit)


@contextmanager
def pending(slug: str, lesson: dict | None):
    """Урок «на пробу»: load / match бачать його в цьому контексті (пропозиція студії до запису)."""
    if not lesson:
        yield
        return
    cur = _PENDING.get() or {}
    token = _PENDING.set({**cur, slug: [*cur.get(slug, []), lesson]})
    try:
        yield
    finally:
        _PENDING.reset(token)


def lint_hits(slug: str, ids: list[str], text: str) -> list[str]:
    """Заборони avoid уроків ids у тексті промпту → «lint: урок L3: «знайдене» → правило»."""
    by_id = {r.get("id"): r for r in load(slug)}
    out = []
    for lid in ids:
        r = by_id.get(lid) or {}
        if not r.get("active", True):
            continue
        for rx in r.get("avoid") or []:
            if m := re.search(rx, text or "", re.I):
                out.append(f"lint: урок {lid}: «{m.group(0)}» → {r.get('rule', '').strip()}")
    return list(dict.fromkeys(out))
