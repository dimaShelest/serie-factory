"""PreToolUse-хук guard_git: force-push, reset --hard і clean -f блокуються в будь-якому місці команди."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

import guard_git  # noqa: E402


@pytest.mark.parametrize("cmd", [
    "git push --force",
    "git push origin main --force",
    "git push origin b/schemas --force-with-lease",
    "git push --force-with-lease=main:abc123 origin main",
    "git push --force-if-includes origin main",
    "git push -f origin main",
    "git push -uf origin main",
    "git push origin +main",
    "git push origin +refs/heads/a:refs/heads/a",
    "git -C D:\\project\\serie-factory push origin main --force",
    "git -c user.name=x push --force",
    "git.exe push origin main -f",
    "git add . && git commit -m x && git push origin main --force",
    "cd repo; git push --force-with-lease",
    "git reset --hard",
    "git reset HEAD~1 --hard",
    "git clean -fd",
    "git clean -xdf",
])
def test_blocks(cmd: str) -> None:
    assert guard_git.verdict(cmd) is not None, cmd


@pytest.mark.parametrize("cmd", [
    "git push",
    "git push -u origin a/feature",
    "git push origin main",
    "git push origin --delete b/schemas",
    "git push --follow-tags origin main",
    "git push -q origin main",
    "git commit -m 'fix --force handling in docs'",
    "git log --oneline -5",
    "git reset --soft HEAD~1",
    "git clean -n",
    "gh pr merge 10 --squash --delete-branch",
    "uv run pytest -q",
    "echo force",
])
def test_allows(cmd: str) -> None:
    assert guard_git.verdict(cmd) is None, cmd


def _run(payload: bytes) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOKS / "guard_git.py")], input=payload,
                          capture_output=True, timeout=30)


def test_hook_exit_codes() -> None:
    blocked = _run(json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin main --force"}}).encode())
    assert blocked.returncode == 2 and "ЗАБЛОКОВАНО" in blocked.stderr.decode("utf-8")
    ok = _run(json.dumps({"tool_name": "PowerShell", "tool_input": {"command": "git push origin main"}}).encode())
    assert ok.returncode == 0 and ok.stdout == b""
    assert _run(b"not json").returncode == 0     # внутрішня помилка → не блокуємо роботу
