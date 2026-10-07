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
"""

from __future__ import annotations

from pathlib import Path

import yaml

from fabrica import bible as bible_mod

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
    return errs


def load(slug: str) -> list[dict]:
    """Усі уроки (і вимкнені) з lessons.yaml; файлу немає — []. Зламано → LessonError."""
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
    return all(t in tags or any(x.endswith(f":{t}") for x in tags) for t in scope.get("tags") or [])


def match(slug: str, item_kind: str, route: str, template_id: str, tags: set[str]) -> list[dict]:
    """Активні уроки, що стосуються елемента: від найважливішого (priority) до найменш важливого, далі — за порядком."""
    found = [(i, r) for i, r in enumerate(load(slug))
             if r.get("active", True) and _fits(r.get("scope") or {}, item_kind, route, template_id, tags)]
    return [r for _, r in sorted(found, key=lambda x: (-x[1].get("priority", 0), x[0]))]


def rules_for(slug: str, item_kind: str, route: str, template_id: str, tags: set[str]) -> list[str]:
    """Речення активних уроків для промпту (порядок — як у match)."""
    return [r["rule"].strip() for r in match(slug, item_kind, route, template_id, tags)]
