#!/usr/bin/env python3
"""PreToolUse-хук: блокує небезпечні git-команди в Bash і PowerShell, хоч де стоїть прапорець.

Deny-правила в settings.json префіксні: `git push origin main --force` їх обходить. Хук дивиться на всю команду:
- `git push` з `--force`, `--force-with-lease`, `--force-if-includes`, `-f` (і `-uf` тощо) або refspec `+гілка`;
- `git reset --hard`, `git clean -f…`.

Код виходу 2 = Claude Code блокує виклик і показує stderr Claude. Будь-яка внутрішня помилка → 0
(хук не має права зламати роботу).
"""

from __future__ import annotations

import json
import re
import sys

SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")
GIT_CMD = re.compile(r"(?:^|[\s(`'\"])git(?:\.exe)?\s+(?P<rest>.*)$", re.I)
PUSH_FORCE = re.compile(r"(?:^|\s)(?:--force(?:-with-lease|-if-includes)?(?:=\S*)?|-[a-z]*f[a-z]*)(?=\s|$)", re.I)
PLUS_REFSPEC = re.compile(r"(?:^|\s)\+\S+")
CLEAN_FORCE = re.compile(r"(?:^|\s)-[a-z]*f[a-z]*(?=\s|$)|(?:^|\s)--force(?=\s|$)", re.I)

REASONS = {
    "push": "force-push заборонено (зокрема --force-with-lease і +refspec). Гілку, що відстала, оновлюй "
            "`git merge origin/main` і звичайним push (docs/DECISIONS.md → «Процес»).",
    "reset": "`git reset --hard` заборонено: він знищує незакомічені зміни. Використай `git stash` або спитай людину.",
    "clean": "`git clean -f` заборонено: він видаляє незатрековані файли без повернення. Спитай людину.",
}


def _subcommand(rest: str) -> tuple[str, str]:
    """`-C path -c k=v push origin --force` → ("push", "origin --force")."""
    tokens = rest.split()
    i = 0
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in ("-C", "-c", "--git-dir", "--work-tree") else 1
    if i >= len(tokens):
        return "", ""
    return tokens[i].lower(), " ".join(tokens[i + 1:])


def verdict(command: str) -> str | None:
    """Причина блокування або None, якщо команда безпечна."""
    for segment in SEGMENT_SPLIT.split(command or ""):
        m = GIT_CMD.search(segment.strip())
        if not m:
            continue
        sub, args = _subcommand(m.group("rest"))
        if sub == "push" and (PUSH_FORCE.search(args) or PLUS_REFSPEC.search(args)):
            return REASONS["push"]
        if sub == "reset" and re.search(r"(?:^|\s)--hard(?=\s|$)", args):
            return REASONS["reset"]
        if sub == "clean" and CLEAN_FORCE.search(args):
            return REASONS["clean"]
    return None


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw) if raw.strip() else {}
        command = (data.get("tool_input") or {}).get("command", "")
        reason = verdict(command)
    except Exception:  # noqa: BLE001 — хук не має права падати
        return 0
    if reason:
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        print(f"[guard_git] ЗАБЛОКОВАНО: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
