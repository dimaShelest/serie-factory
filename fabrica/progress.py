"""Прогрес студії: «де ми зараз» — статус кожного елемента в lab/progress.yaml (у Git, поруч із lab/results.yaml).

    {<slug>: {<id елемента>: {status, at, prompt_sha}}}

status: todo (ще не почали) | in_work (у роботі) | done (є результат ≥ 4) | approved (golden) | skip (не робимо).
Статус прив'язаний до prompt_sha: промпт змінився — збережений статус застарів (stale) і елемент знову todo з
позначкою «промпт змінився». Правила (DESIGN §16): запис результату з оцінкою ≥ 4 → done (нижче — in_work, якщо
ще не почали); approve → approved; явний вибір людини (POST /api/status) перекриває все. Елементи без запису
для поточного промпту беруть статус із журналу: golden → approved, результат ≥ 4 → done.
"""

from __future__ import annotations

from datetime import datetime, timezone

import yaml

from fabrica import config

PROGRESS = config.ROOT / "lab" / "progress.yaml"
STATUSES = ("todo", "in_work", "done", "approved", "skip")
CLOSED = ("done", "approved", "skip")          # «готово» для лічильника й «Далі»
PASS_SCORE = 4


class ProgressError(ValueError):
    """Неправильний статус або зламаний progress.yaml — повідомлення пояснює, що виправити."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _read() -> dict:
    if not PROGRESS.exists():
        return {}
    try:
        raw = yaml.safe_load(PROGRESS.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as e:
        raise ProgressError(f"{PROGRESS.name}: зламаний YAML — {e}") from None
    if not isinstance(raw, dict) or not all(isinstance(v, dict) for v in raw.values()):
        raise ProgressError(f"{PROGRESS.name}: очікую {{історія: {{елемент: {{status, at, prompt_sha}}}}}}")
    return raw


def load(slug: str) -> dict[str, dict]:
    """{id елемента: {status, at, prompt_sha}} історії; файлу немає — {}."""
    return {str(k): dict(v) for k, v in (_read().get(slug) or {}).items() if isinstance(v, dict)}


def set_status(slug: str, item_id: str, status: str, prompt_sha: str) -> dict:
    """Записати статус елемента для поточного prompt_sha → запис."""
    if status not in STATUSES:
        raise ProgressError(f"невідомий статус «{status}» (можна: {', '.join(STATUSES)})")
    data = _read()
    entry = {"status": status, "at": _now(), "prompt_sha": prompt_sha}
    data.setdefault(slug, {})[item_id] = entry
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=True, width=110)
    tmp.replace(PROGRESS)
    return entry


def on_log(slug: str, item_id: str, score: int, prompt_sha: str) -> str | None:
    """Після запису результату: ≥ 4 → done (крім approved / skip для цього промпту); нижче — in_work, якщо ще todo.
    Повертає новий статус або None (не змінювали)."""
    cur = load(slug).get(item_id) or {}
    same = cur.get("prompt_sha") == prompt_sha
    status = cur.get("status") if same else "todo"
    if int(score) >= PASS_SCORE:
        new = None if status in ("approved", "skip") else "done"
    else:
        new = "in_work" if status == "todo" else None
    if new and new != (cur.get("status") if same else None):
        set_status(slug, item_id, new, prompt_sha)
        return new
    return None


def effective(entry: dict | None, prompt_sha: str, *, golden: bool = False, passed: bool = False) -> tuple[str, bool]:
    """(статус, stale) для картки: запис для поточного промпту → він; інакше golden → approved, результат ≥ 4 →
    done; запис для старого промпту → todo + stale; нічого → todo."""
    if entry and entry.get("prompt_sha") == prompt_sha and entry.get("status") in STATUSES:
        return entry["status"], False
    if golden:
        return "approved", False
    if passed:
        return "done", False
    return "todo", bool(entry and entry.get("status") not in (None, "todo"))


def next_id(rows: list[tuple[str, str, bool]]) -> str | None:
    """rows — (id, статус, усі потреби готові) у порядку виробництва → «Далі»: перший незакритий із готовими
    потребами, інакше перший незакритий; усе закрито — None."""
    open_ = [(i, ready) for i, status, ready in rows if status not in CLOSED]
    return next((i for i, ready in open_ if ready), open_[0][0] if open_ else None)
