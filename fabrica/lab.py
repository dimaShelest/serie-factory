"""Журнал лабораторії промптів: результати ручних тестів і golden-версії.

    fabrica lab log tp-T1-frame --tool gemini --score 4 --file ~/Downloads/t1.png --notes "камінці ок, Vale без шраму"
    fabrica lab approve image.start_frame        # версія шаблону → golden
    fabrica lab approve tp-T1-frame              # конкретний промпт елемента → golden

- lab/results.yaml (у Git) — кожен запис прив'язаний до id@версії шаблону, хешу шаблону і хешу промпту.
- media/lab/<slug>/<елемент>/… (не в Git) — файли результатів; у журналі — шлях і sha256.
- prompts/golden.yaml (у Git) — затверджене. Golden ламається, якщо шаблон змінили без нової версії.
  Затвердити можна лише те, для чого в журналі є результат з оцінкою ≥ 4 (або явно --force).
Автоматика використовує тільки golden (require_golden).
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fabrica import config
from fabrica import prompts as prompts_mod

RESULTS = config.ROOT / "lab" / "results.yaml"
MEDIA = config.ROOT / "media" / "lab"
GOLDEN = config.ROOT / "prompts" / "golden.yaml"
PASS_SCORE = 4


class LabError(ValueError):
    """Неправильна дія в лабораторії — повідомлення пояснює, що зробити."""


class GoldenError(RuntimeError):
    """Автоматика спробувала взяти не-golden шаблон або промпт."""


def _load(path: Path, default):
    if not path.exists():
        return default
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or default


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=110)
    tmp.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _who() -> str:
    from_local = (config.ROOT / "CLAUDE.local.md")
    text = from_local.read_text(encoding="utf-8-sig") if from_local.exists() else ""
    return "B (nuchay69-max)" if "Claude B" in text else "A (dimaShelest)"


def results(slug: str | None = None) -> list[dict]:
    rows = _load(RESULTS, {"results": []}).get("results", [])
    return [r for r in rows if slug is None or r.get("story") == slug]


def find_item(slug: str, item_id: str) -> prompts_mod.Item:
    for item in prompts_mod.build(slug, prompts_mod.set_of(item_id)):
        if item.id == item_id:
            return item
    raise LabError(f"елемента «{item_id}» немає в наборі «{prompts_mod.set_of(item_id)}» історії {slug}")


def log(slug: str, item_id: str, tool: str, score: int, file: Path | None = None, notes: str = "",
        by: str | None = None) -> dict:
    """Записати результат ручного тесту. Файл копіюється в media/lab/ і хешується."""
    if not 1 <= int(score) <= 5:
        raise LabError("оцінка має бути від 1 до 5")
    tool = tool.strip().lower()
    if not tool:
        raise LabError("вкажи інструмент: --tool syntx | gemini | dreamina | replicate | elevenlabs | …")
    item = find_item(slug, item_id)
    stored, digest = None, None
    if file is not None:
        src = Path(file).expanduser()
        if not src.is_file():
            raise LabError(f"файлу немає: {src}")
        dest = MEDIA / slug / item.id / f"{datetime.now():%Y%m%d-%H%M%S}_{tool}_{src.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        stored = dest.relative_to(config.ROOT).as_posix() if dest.is_relative_to(config.ROOT) else dest.as_posix()
    data = _load(RESULTS, {"results": []})
    rows = data.setdefault("results", [])
    entry = {
        "id": max((r.get("id", 0) for r in rows), default=0) + 1, "at": _now(), "story": slug,
        "item": item.id, "kind": item.kind, "template": item.template.id, "template_version": item.template.version,
        "template_sha": item.template.sha, "prompt_sha": item.prompt_sha, "tool": tool, "score": int(score),
        "file": stored, "file_sha256": digest, "notes": notes.strip(), "by": by or _who(),
    }
    rows.append(entry)
    _dump(RESULTS, data)
    return entry


# ---------------------------------------------------------------- golden


def golden() -> dict:
    g = _load(GOLDEN, {})
    g.setdefault("templates", {})
    g.setdefault("items", {})
    return g


def is_golden_template(t: prompts_mod.Template, g: dict | None = None) -> bool:
    e = (g or golden())["templates"].get(t.id)
    return bool(e) and e.get("version") == t.version and e.get("sha") == t.sha


def golden_state(t: prompts_mod.Template, g: dict | None = None) -> str:
    e = (g or golden())["templates"].get(t.id)
    if not e:
        return "draft"
    if e.get("version") != t.version:
        return f"golden v{e.get('version')} (зараз v{t.version} — чернетка)"
    return "golden" if e.get("sha") == t.sha else "⚠️ golden зламано: шаблон змінено без нової версії"


def is_golden_item(slug: str, item: prompts_mod.Item, g: dict | None = None) -> bool:
    e = (g or golden())["items"].get(slug, {}).get(item.id)
    return bool(e) and e.get("prompt_sha") == item.prompt_sha


def require_golden(t: prompts_mod.Template) -> None:
    """Для автоматики: лише golden-шаблони."""
    if not is_golden_template(t):
        raise GoldenError(f"шаблон {t.ref} не golden ({golden_state(t)}) — автоматика його не використовує. "
                          "Спершу ручні тести і `fabrica lab approve`.")


def approve(slug: str, target: str, force: bool = False, by: str | None = None) -> str:
    templates = prompts_mod.load_templates()
    g = golden()
    rows = results(slug)
    if target in templates:
        t = templates[target]
        ok = any(r["template"] == t.id and r["template_version"] == t.version and r["template_sha"] == t.sha
                 and r["score"] >= PASS_SCORE for r in rows)
        if not ok and not force:
            raise LabError(f"для {t.ref} у журналі немає результату з оцінкою ≥ {PASS_SCORE} — спершу протестуй "
                           "(`fabrica lab log …`) або --force")
        g["templates"][t.id] = {"version": t.version, "sha": t.sha, "approved_at": _now(), "by": by or _who(),
                                "forced": not ok}
        _dump(GOLDEN, g)
        return f"шаблон {t.ref} → golden"
    item = find_item(slug, target)
    best = sorted((r for r in rows if r["item"] == item.id and r["prompt_sha"] == item.prompt_sha),
                  key=lambda r: (r["score"], r["id"]), reverse=True)
    ok = bool(best) and best[0]["score"] >= PASS_SCORE
    if not ok and not force:
        raise LabError(f"для {item.id} (поточна версія промпту {item.prompt_sha}) немає результату з оцінкою ≥ "
                       f"{PASS_SCORE} — спершу протестуй (`fabrica lab log {item.id} …`) або --force")
    g["items"].setdefault(slug, {})[item.id] = {
        "prompt_sha": item.prompt_sha, "template": item.template.id, "template_version": item.template.version,
        "template_sha": item.template.sha, "result": best[0]["id"] if best else None, "approved_at": _now(),
        "by": by or _who(), "forced": not ok}
    _dump(GOLDEN, g)
    return f"елемент {item.id} ({item.prompt_sha}) → golden"


def status(slug: str) -> list[str]:
    templates = prompts_mod.load_templates()
    g, rows = golden(), results(slug)
    lines = []
    for t in templates.values():
        mine = [r for r in rows if r["template"] == t.id and r["template_version"] == t.version]
        avg = f"{sum(r['score'] for r in mine) / len(mine):.1f}" if mine else "—"
        lines.append(f"{t.ref:<28} {golden_state(t, g):<16} тестів: {len(mine):>3}  середня: {avg}")
    items = g["items"].get(slug, {})
    lines.append(f"golden-елементів ({slug}): {len(items)}")
    return lines
