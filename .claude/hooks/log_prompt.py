#!/usr/bin/env python3
"""UserPromptSubmit-хук: дописує промпт людини в docs/prompts/YYYY-MM-DD-<A|B>.md.

Рядки, схожі на секрети, замінюються на [ПРИХОВАНО] (collab.redact).
Нічого не друкує в stdout (інакше це потрапить у контекст) і ніколи не блокує промпт.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collab  # noqa: E402


def main() -> int:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw) if raw.strip() else {}
        prompt = data.get("prompt") or ""
        if prompt.strip():
            who = collab.whoami() or "UNKNOWN"
            collab.append_prompt(who, prompt, session=(data.get("session_id") or "")[:8])
    except Exception as e:  # noqa: BLE001 — журнал не має права зламати роботу
        print(f"[log_prompt] {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
