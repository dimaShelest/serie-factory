"""Тести .claude/settings.json і слеш-команд: правила для Bash мають PowerShell-двійника.

На Windows основний shell-інструмент Claude Code — PowerShell, і правила `Bash(...)` на нього не діють.
Без двійника заборона (`push --force`, `reset --hard`) там просто не спрацює.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
COMMANDS = sorted((ROOT / ".claude" / "commands").glob("*.md"))

# python3 на Windows — заглушка Microsoft Store, дозволяти її в PowerShell немає сенсу
NO_TWIN = {"Bash(python3:*)"}


def twins_missing(rules: list[str]) -> list[str]:
    return [r for r in rules if r.startswith("Bash(") and r not in NO_TWIN
            and "PowerShell(" + r[5:] not in rules]


@pytest.mark.parametrize("key", ["allow", "deny"])
def test_settings_rules_have_powershell_twin(key: str) -> None:
    assert twins_missing(SETTINGS["permissions"][key]) == []


@pytest.mark.parametrize("path", COMMANDS, ids=lambda p: p.name)
def test_command_allowed_tools_have_powershell_twin(path: Path) -> None:
    m = re.search(r"^allowed-tools: (.*)$", path.read_text(encoding="utf-8"), re.M)
    assert m, f"{path.name}: немає allowed-tools"
    assert twins_missing([t.strip() for t in m.group(1).split(",")]) == []


def test_hook_commands_are_shell_neutral() -> None:
    """Команди хуків виконуються і в zsh, і в Git Bash/PowerShell: без $VAR, &&, |, перенаправлень."""
    for groups in SETTINGS["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert not re.search(r"[$&|<>;`]", hook["command"]), hook["command"]
