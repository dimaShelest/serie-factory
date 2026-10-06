#!/usr/bin/env python3
"""SessionStart-хук: git pull --rebase, хто я, початок STATUS.md, нові листи в моїй скриньці.

Stdout потрапляє в контекст Claude. Хук ніколи не падає (exit 0), лише попереджає.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collab  # noqa: E402


def pull(root: Path) -> str:
    """fetch + rebase на upstream. Не `git pull`: одночасний автофетч VS Code пише гілку в FETCH_HEAD
    двічі, і pull падає з «Cannot rebase onto multiple branches». `@{u}` від FETCH_HEAD не залежить."""
    try:
        if (root / ".git" / "rebase-merge").exists() or (root / ".git" / "rebase-apply").exists():
            return "⚠️ git: незавершений rebase з минулого разу — розберись (git status) до початку роботи."
        if collab.git("rev-parse", "--abbrev-ref", "@{u}", root=root).returncode != 0:
            return "⚠️ git: у поточної гілки немає upstream — синхронізацію пропущено."
        r = collab.git("fetch", "--quiet", root=root, timeout=45)
        if r.returncode != 0:
            return "⚠️ git fetch не вдався (мережа/доступ?):\n" + r.stderr.strip()[-600:]
        r = collab.git("rebase", "--autostash", "@{u}", root=root, timeout=45)
        if r.returncode == 0:
            last = (r.stdout.strip().splitlines() or ["OK"])[-1]
            return f"git fetch + rebase @{{u}}: {last}"
        if (root / ".git" / "rebase-merge").exists() or (root / ".git" / "rebase-apply").exists():
            collab.git("rebase", "--abort", root=root)
            return ("⚠️ git rebase @{u}: КОНФЛІКТ — rebase скасовано, репо як було. "
                    "Скажи людині й розв'яжи вручну перед роботою.\n" + r.stderr.strip()[-600:])
        return "⚠️ git rebase @{u} не вдався:\n" + r.stderr.strip()[-600:]
    except Exception as e:  # noqa: BLE001 — хук не має права падати
        return f"⚠️ git pull не виконано: {e}"


def report(root: Path = collab.ROOT, do_pull: bool = True) -> str:
    out = ["=== serie-factory: старт сесії ==="]
    if do_pull:
        out.append(pull(root))

    me = collab.whoami(root)
    if me:
        p = collab.PARTNER[me]
        out.append(f"Ти — Claude {me} ({collab.HUMAN[me]}). Партнер — Claude {p} ({collab.HUMAN[p]}).")
    else:
        out.append("⚠️ Невідомо, хто ти: немає CLAUDE.local.md з рядком «Я — Claude A/B». "
                   "СПИТАЙ ЛЮДИНУ (A = Mac/dimaShelest, B = Windows/nuchay69-max) і створи файл.")

    try:
        dirty = collab.git("status", "--porcelain", root=root).stdout.strip().splitlines()
        if dirty:
            out.append(f"⚠️ Незакомічених змін: {len(dirty)} — можливо, минула сесія завершилась без /handoff.")
    except Exception:  # noqa: BLE001
        pass

    status = collab.read(root / "docs" / "STATUS.md").splitlines()[:40]
    if status:
        out += ["", "--- docs/STATUS.md (перші 40 рядків) ---", *status]

    if me:
        new = [m for m in collab.messages(me, root) if m.status == "NEW"]
        out += ["", f"--- Нові повідомлення в docs/comms/to-{me}.md: {len(new)} ---"]
        out += [m.raw + "\n" for m in new]

    out += ["", "Ритуал: почни з /start, заверши ОБОВ'ЯЗКОВО /handoff."]
    return "\n".join(out)


def main() -> int:
    collab.setup_stdio()
    try:
        print(report())
    except Exception as e:  # noqa: BLE001
        print(f"[session_start] помилка: {e}. Виконай /start вручну.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
