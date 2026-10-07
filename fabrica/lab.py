"""Журнал лабораторії промптів: результати ручних тестів і golden-версії.

    fabrica lab log tp-T1-frame --tool gemini --score 4 --file ~/Downloads/t1.png --notes "камінці ок, Vale без шраму"
    fabrica lab approve image.start_frame        # версія шаблону → golden
    fabrica lab approve tp-T1-frame              # конкретний промпт елемента → golden

- lab/results.yaml (у Git) — кожен запис прив'язаний до id@версії шаблону, хешу шаблону і хешу промпту.
- media/lab/<slug>/<елемент>/… (не в Git) — файли результатів; у журналі — шлях і sha256. Відео (mp4 / mov / webm):
  ffmpeg витягує останній кадр поруч (`….last.png`, поле `last_frame`) — з нього стартує наступний кліп
  (`<produces>.last`). Немає ffmpeg — запис без кадру + попередження; кадр можна записати руками:
  `fabrica lab log <кліп>-last --file кадр.png …` (лише зображення; автоматика бере такий кадр з оцінкою ≥ 4;
  це не тест шаблону кліпу — approve / status шаблону його не рахують).
- prompts/golden.yaml (у Git) — затверджене. Golden ламається, якщо шаблон змінили без нової версії.
  Затвердити можна лише те, для чого в журналі є результат з оцінкою ≥ 4 (або явно --force).
Автоматика використовує тільки golden (require_golden; файли — golden_result / golden_file для поточного
prompt_sha). ref_file — найкращий файл референсу для людей, переглядача й студії (golden → оцінка ≥ 4 → решта).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fabrica import config
from fabrica import prompts as prompts_mod

RESULTS = config.ROOT / "lab" / "results.yaml"
MEDIA = config.ROOT / "media" / "lab"
GOLDEN = config.ROOT / "prompts" / "golden.yaml"
PASS_SCORE = 4
VIDEO = (".mp4", ".mov", ".webm", ".m4v", ".mkv")
IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")
AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".flac")
FILE_TYPES = IMAGE + VIDEO + AUDIO      # що приймає журнал (і віддає студія через /media) — лише медіа
TOOL_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,30}")      # інструмент іде в ім'я файлу: латиниця, цифри, «-», «_»
LAST = "-last"                # «<кліп>-last» — останній кадр кліпу, записаний руками
FFMPEG_TIMEOUT_S = 120


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
    config.replace_atomic(tmp, path)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _who() -> str:
    from_local = (config.ROOT / "CLAUDE.local.md")
    text = from_local.read_text(encoding="utf-8-sig") if from_local.exists() else ""
    return "B (nuchay69-max)" if "Claude B" in text else "A (dimaShelest)"


def _abs(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else config.ROOT / p


def stored_path(path: str) -> Path:
    """Шлях із журналу (відносно кореня репо або абсолютний) → Path."""
    return _abs(path)


def _stored(path: Path) -> str:
    return path.relative_to(config.ROOT).as_posix() if path.is_relative_to(config.ROOT) else path.as_posix()


def _safe_name(src: Path) -> str:
    """Ім'я копії в media/lab: латиниця, цифри, «-», «_» + розширення (Windows, URL студії, журнал у Git)."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", src.stem).strip("_")[:60] or "file"
    return f"{stem}{src.suffix.lower()}"


def results(slug: str | None = None) -> list[dict]:
    rows = _load(RESULTS, {"results": []}).get("results", [])
    return [r for r in rows if slug is None or r.get("story") == slug]


def find_item(slug: str, item_id: str) -> prompts_mod.Item:
    for item in prompts_mod.build(slug, prompts_mod.set_of(item_id)):
        if item.id == item_id:
            return item
    raise LabError(f"елемента «{item_id}» немає в наборі «{prompts_mod.set_of(item_id)}» історії {slug}")


def _target(slug: str, item_id: str) -> tuple[prompts_mod.Item, str, str]:
    """(елемент, id запису, kind запису). «<кліп>-last» — останній кадр кліпу, записаний руками (без ffmpeg)."""
    try:
        item = find_item(slug, item_id)
        return item, item.id, item.kind
    except LabError:
        if not item_id.endswith(LAST):
            raise
    clip = find_item(slug, item_id.removesuffix(LAST))
    if clip.kind != "video":
        raise LabError(f"«{item_id}»: «{LAST}» — лише для відео-кліпу, а {clip.id} — {clip.kind}")
    return clip, item_id, "image"


def extract_last_frame(video: Path, out: Path | None = None, *,
                       item_id: str = "<кліп>") -> tuple[Path | None, str | None]:
    """Останній кадр відео (ffmpeg) → out (типово `<відео>.last.png` поруч): (файл, None) або (None, попередження).
    Спершу останні 1 с (`-sseof -1 … -update 1` — кадр перезаписується до останнього), не вийшло — увесь кліп."""
    out = out or video.with_name(f"{video.stem}.last.png")
    manual = f"запиши кадр руками: `fabrica lab log {item_id}{LAST} --file кадр.png …`"
    exe = shutil.which("ffmpeg")
    if not exe:
        return None, ("немає ffmpeg — останній кадр не витягнуто (Mac — `brew install ffmpeg`, Windows — "
                      f"`winget install Gyan.FFmpeg`); {manual}")
    err = ""
    out.parent.mkdir(parents=True, exist_ok=True)              # тека черги могла ще не існувати
    for seek in (["-sseof", "-1"], []):
        out.unlink(missing_ok=True)
        try:
            r = subprocess.run([exe, "-v", "error", "-y", *seek, "-i", str(video), "-an", "-update", "1", str(out)],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
                               timeout=FFMPEG_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            err = f"ffmpeg не вклався в {FFMPEG_TIMEOUT_S} с"
            continue
        if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return out, None
        err = ((r.stderr or "").strip().splitlines() or [f"код {r.returncode}"])[0][:200]
    out.unlink(missing_ok=True)
    return None, f"ffmpeg не витягнув останній кадр з {video.name}: {err}; {manual}"


def log(slug: str, item_id: str, tool: str, score: int, file: Path | None = None, notes: str = "",
        by: str | None = None) -> dict:
    """Записати результат ручного тесту. Файл копіюється в media/lab/ і хешується; з відео — ще й останній кадр
    (`last_frame`). Повертає запис + `warnings` (напр. немає ffmpeg) — їх у журнал не пишемо."""
    if not 1 <= int(score) <= 5:
        raise LabError("оцінка має бути від 1 до 5")
    tool = re.sub(r"\s+", "-", tool.strip().lower())
    if not tool:
        raise LabError("вкажи інструмент: --tool dropshot | gemini | ai-studio | replicate | elevenlabs | …")
    if not TOOL_RE.fullmatch(tool):
        raise LabError(f"інструмент «{tool[:40]}» — лише латиниця, цифри, «-», «_» (до 31 знака), напр. dropshot")
    item, row_id, kind = _target(slug, item_id)
    stored, digest, last, warnings = None, None, None, []
    if file is not None:
        src = Path(file).expanduser()
        if src.suffix.lower() not in FILE_TYPES:
            raise LabError(f"{src.name}: журнал приймає лише медіа ({' '.join(t[1:] for t in FILE_TYPES)})")
        if not src.is_file():
            raise LabError(f"файлу немає: {src}")
        if kind == "image" and src.suffix.lower() in VIDEO:
            hint = f"; відео кліпу логуй на сам кліп: `fabrica lab log {item.id} --file {src.name} …`" \
                if row_id != item.id else ""
            raise LabError(f"«{row_id}» — кадр (png / jpg / webp), а {src.name} — відео{hint}")
        dest = MEDIA / slug / row_id / f"{datetime.now():%Y%m%d-%H%M%S}_{tool}_{_safe_name(src)}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        stored = _stored(dest)
        if dest.suffix.lower() in VIDEO:
            frame, warn = extract_last_frame(dest, item_id=item.id)
            last = _stored(frame) if frame else None
            warnings += [warn] if warn else []
    data = _load(RESULTS, {"results": []})
    rows = data.setdefault("results", [])
    entry = {
        "id": max((r.get("id", 0) for r in rows), default=0) + 1, "at": _now(), "story": slug,
        "item": row_id, "kind": kind, "template": item.template.id, "template_version": item.template.version,
        "template_sha": item.template.sha, "prompt_sha": item.prompt_sha, "tool": tool, "score": int(score),
        "file": stored, "file_sha256": digest, **({"last_frame": last} if last else {}), "notes": notes.strip(),
        "by": by or _who(),
    }
    rows.append(entry)
    _dump(RESULTS, data)
    return {**entry, "warnings": warnings}


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


def golden_result(slug: str, item: prompts_mod.Item, *, g: dict | None = None,
                  rows: list[dict] | None = None) -> dict | None:
    """Рядок журналу, затверджений як golden для ПОТОЧНОГО prompt_sha; None — не golden або --force без результату."""
    g = g if g is not None else golden()
    if not is_golden_item(slug, item, g):
        return None
    rid = g["items"][slug][item.id].get("result")
    rows = rows if rows is not None else results(slug)
    return next((r for r in rows if rid and r.get("id") == rid and r.get("item") == item.id), None)


def golden_file(slug: str, item: prompts_mod.Item, *, last: bool = False, g: dict | None = None,
                rows: list[dict] | None = None) -> Path | None:
    """Файл golden-результату елемента — лише якщо golden для ПОТОЧНОГО prompt_sha (змінили промпт — старий файл
    автоматиці не годиться). last=True — останній кадр кліпу: last_frame затвердженого запису, інакше найкращий
    кадр «<кліп>-last» тієї самої версії промпту з оцінкою ≥ 4. Файлу на диску немає — None."""
    g = g if g is not None else golden()
    if not is_golden_item(slug, item, g):
        return None
    rows = rows if rows is not None else results(slug)
    row = golden_result(slug, item, g=g, rows=rows) or {}
    if not last:
        files = [row.get("file")]
    else:
        manual = [r for r in rows if r.get("item") == item.id + LAST and r.get("prompt_sha") == item.prompt_sha
                  and r.get("score", 0) >= PASS_SCORE]
        manual.sort(key=lambda r: (r.get("score", 0), r.get("id", 0)), reverse=True)
        files = [row.get("last_frame")] + [r.get("file") for r in manual]
    return next((p for f in files if f and (p := _abs(f)).is_file()), None)


def _pool(slug: str, ref_id: str) -> list[prompts_mod.Item]:
    """Елементи, серед яких шукати джерело референсу: p<N>.… → частина N, tp.… → test-pack, інше — кастинг."""
    m = re.match(r"p([1-4])\.", ref_id)
    set_name = m.group(1) if m else "test-pack" if ref_id.startswith("tp.") else "casting"
    try:
        return prompts_mod.build(slug, set_name)
    except prompts_mod.PromptError:
        return []


def ref_file(slug: str, ref_id: str, items: list[prompts_mod.Item] | None = None, *, rows: list[dict] | None = None,
             g: dict | None = None) -> Path | None:
    """Референс → найкращий файл із журналу (для людей і студії; автоматика бере golden_file):
    golden для поточного промпту → оцінка ≥ 4 (поточна версія промпту першою) → решта. «<produces>.last» —
    last_frame кліпу або кадр «<кліп>-last». Файли, яких немає на диску, пропускаємо; None — нічого немає.
    items — елементи, серед яких шукати джерело (типово — збираємо набір за id референсу)."""
    producers: dict[str, prompts_mod.Item] = {}
    for it in (items if items is not None else _pool(slug, ref_id)):
        if it.produces:
            producers.setdefault(it.produces, it)
    last = ref_id not in producers and ref_id.endswith(".last")
    item = producers.get(ref_id.removesuffix(".last") if last else ref_id)
    if item is None:
        return None
    rows = rows if rows is not None else results(slug)
    if found := golden_file(slug, item, last=last, g=g, rows=rows):
        return found
    if last:
        cands = [{**r, "file": r["last_frame"]} for r in rows if r.get("item") == item.id and r.get("last_frame")]
        cands += [r for r in rows if r.get("item") == item.id + LAST and r.get("file")]
    else:
        cands = [r for r in rows if r.get("item") == item.id and r.get("file")]
    cands.sort(key=lambda r: (r.get("score", 0) >= PASS_SCORE, r.get("prompt_sha") == item.prompt_sha,
                              r.get("score", 0), r.get("id", 0)), reverse=True)
    return next((p for r in cands if (p := _abs(r["file"])).is_file()), None)


def require_golden(t: prompts_mod.Template) -> None:
    """Для автоматики: лише golden-шаблони."""
    if not is_golden_template(t):
        raise GoldenError(f"шаблон {t.ref} не golden ({golden_state(t)}) — автоматика його не використовує. "
                          "Спершу ручні тести і `fabrica lab approve`.")


def _tests(rows: list[dict], t: prompts_mod.Template) -> list[dict]:
    """Тести версії шаблону. Кадр «<кліп>-last» (kind image під відео-шаблоном кліпу) — не тест шаблону."""
    return [r for r in rows if r["template"] == t.id and r["template_version"] == t.version
            and r.get("kind", t.kind) == t.kind]


def approve(slug: str, target: str, force: bool = False, by: str | None = None) -> str:
    templates = prompts_mod.load_templates()
    g = golden()
    rows = results(slug)
    if target in templates:
        t = templates[target]
        ok = any(r["template_sha"] == t.sha and r["score"] >= PASS_SCORE for r in _tests(rows, t))
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
        mine = _tests(rows, t)
        avg = f"{sum(r['score'] for r in mine) / len(mine):.1f}" if mine else "—"
        lines.append(f"{t.ref:<28} {golden_state(t, g):<16} тестів: {len(mine):>3}  середня: {avg}")
    items = g["items"].get(slug, {})
    lines.append(f"golden-елементів ({slug}): {len(items)}")
    return lines
