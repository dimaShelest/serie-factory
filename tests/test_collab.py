"""Тести спільної пам'яті (.claude/hooks/collab.py) — без мережі, на тимчасовому «репо»."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

import collab  # noqa: E402
import session_start  # noqa: E402

KYIV = timezone(timedelta(hours=3))
T0 = datetime(2026, 10, 5, 9, 0, tzinfo=KYIV)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "comms").mkdir(parents=True)
    (tmp_path / "docs" / "prompts").mkdir()
    for name in ("HANDOFF.md", "DECISIONS.md"):
        (tmp_path / "docs" / name).write_text(f"# {name}\n\n{collab.LOG_MARK}\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------- хто я


@pytest.mark.parametrize("text, expected", [
    ("Я — Claude A (Mac, партнер dimaShelest)", "A"),
    ("Я — Claude B (Windows)", "B"),
    ("Я - Claude B", "B"),
    ("Я — Claude А", "A"),   # кирилична А
    ("Я — Claude В", "B"),   # кирилична В
    ("Привіт", None),
])
def test_whoami(tmp_path: Path, text: str, expected: str | None) -> None:
    (tmp_path / "CLAUDE.local.md").write_text(text, encoding="utf-8")
    assert collab.whoami(tmp_path) == expected


def test_whoami_bom_and_missing(tmp_path: Path) -> None:
    assert collab.whoami(tmp_path) is None
    (tmp_path / "CLAUDE.local.md").write_text("Я — Claude B", encoding="utf-8-sig")  # PowerShell 5.1
    assert collab.whoami(tmp_path) == "B"


# ---------------------------------------------------------------- секрети


@pytest.mark.parametrize("line", [
    "мій ключ sk-ant-api03-AbCdEf1234567890abcdef",
    "ELEVENLABS_API_KEY=sk_0123456789abcdef0123456789abcdef0123456789abcdef",
    "export SEEDANCE_API_KEY=abc123",
    "token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "пароль: Qwerty12345!",
    "Authorization: Bearer abcdefghijklmnop.qrstuvwx",
    "AKIAIOSFODNN7EXAMPLE",
    "R2 secret 9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c",
    "ось: Zx81KqL0pN7rT2vB9mW4cY6hJ3sD5fG1aQ8uE0iO",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
])
def test_redacts_secrets(line: str) -> None:
    assert collab.redact(f"до\n{line}\nпісля") == f"до\n{collab.REDACTED}\nпісля"


@pytest.mark.parametrize("line", [
    "Зроби етап voice з ElevenLabs, ключі в ELEVENLABS_API_KEY, IMAGE_API_KEY",
    "Перевір /Users/dmitroselest/projects/serie-factory/docs/prompts/2026-10-05-A.md",
    "сесія 4b052eb3-36f3-4c78-839e-92a29e5ab5f6",
    "https://github.com/seriefactory-studio/serie-factory/pull/12",
    "ліміт 2000 токенів на відповідь",
    "SEEDANCE_*, R2_*, YOUTUBE_* — назви ключів у .env.example",
])
def test_keeps_normal_text(line: str) -> None:
    assert collab.redact(line) == line


# ---------------------------------------------------------------- скриньки


def test_send_and_mark_read(repo: Path) -> None:
    collab.send("B", "A", "Привіт", "Перевір хуки на Windows", root=repo, when=T0)
    collab.send("B", "A", "Друге · з крапкою", "текст\n\n## не заголовок", root=repo,
                when=T0 + timedelta(minutes=5))
    msgs = collab.messages("B", repo)
    assert [m.status for m in msgs] == ["NEW", "NEW"]
    assert msgs[0].title == "Привіт" and msgs[0].who == "A"
    assert msgs[1].title == "Друге · з крапкою"
    assert "## не заголовок" in msgs[1].body

    assert collab.mark_read("B", repo) == 2
    assert [m.status for m in collab.messages("B", repo)] == ["READ", "READ"]
    assert collab.mark_read("B", repo) == 0
    text = (repo / "docs" / "comms" / "to-B.md").read_text(encoding="utf-8")
    assert text.startswith("# Скринька Claude B")
    assert text.index("Привіт") < text.index("Друге")  # нові — внизу


# ---------------------------------------------------------------- журнали


def test_log_entry_newest_on_top(repo: Path) -> None:
    collab.log_entry("handoff", "A", "перша", "- зроблено", root=repo, when=T0)
    collab.log_entry("handoff", "B", "друга", "- теж", root=repo, when=T0 + timedelta(hours=1))
    entries = collab.parse_entries((repo / "docs" / "HANDOFF.md").read_text(encoding="utf-8"))
    assert [e.title for e in entries] == ["друга", "перша"]
    assert collab.last_entry_time(repo / "docs" / "HANDOFF.md", "A") == T0
    assert collab.last_entry_time(repo / "docs" / "HANDOFF.md", "B") == T0 + timedelta(hours=1)


def test_prompt_log_and_digest(repo: Path) -> None:
    collab.log_entry("handoff", "A", "старт", "- ок", root=repo, when=T0)
    collab.append_prompt("B", "стара задача", "s1", root=repo, when=T0 - timedelta(minutes=10))
    collab.append_prompt("B", "нова задача з ```кодом```", "s2", root=repo, when=T0 + timedelta(minutes=10))
    collab.log_entry("decision", "B", "SQLite для витрат", "- **Чому:** просто", root=repo,
                     when=T0 + timedelta(minutes=20))

    path = repo / "docs" / "prompts" / "2026-10-05-B.md"
    text = path.read_text(encoding="utf-8")
    assert "````text\nнова задача з ```кодом```\n````" in text  # паркан довший за вміст

    got = collab.prompts_since("B", T0, repo)
    assert len(got) == 1 and "нова задача" in got[0][1]

    (repo / "CLAUDE.local.md").write_text("Я — Claude A", encoding="utf-8")
    d = collab.digest("A", repo)
    assert "нова задача" in d and "стара задача" not in d
    assert "SQLite для витрат" in d


def test_prompt_summary_goes_on_top(repo: Path) -> None:
    collab.append_prompt("A", "зроби систему", root=repo, when=T0)
    collab.add_prompt_summary("A", "- система → готово", root=repo, when=T0 + timedelta(hours=1))
    collab.add_prompt_summary("A", "- друга сесія", root=repo, when=T0 + timedelta(hours=2))
    text = (repo / "docs" / "prompts" / "2026-10-05-A.md").read_text(encoding="utf-8")
    assert text.index("друга сесія") < text.index("система → готово") < text.index("зроби систему")
    # підсумки не плутаються з промптами
    assert len(collab.prompts_since("A", None, repo)) == 1


# ---------------------------------------------------------------- хуки


def test_session_start_report(repo: Path) -> None:
    (repo / "CLAUDE.local.md").write_text("Я — Claude B", encoding="utf-8")
    (repo / "docs" / "STATUS.md").write_text("# STATUS\n" + "\n".join(f"р{i}" for i in range(60)),
                                             encoding="utf-8")
    collab.send("B", "A", "Тест", "Привіт, B", root=repo, when=T0)
    out = session_start.report(repo, do_pull=False)
    assert "Ти — Claude B" in out
    assert "р38" in out and "р39" not in out  # рівно 40 рядків STATUS
    assert "Привіт, B" in out


def test_log_prompt_hook_is_silent(tmp_path: Path) -> None:
    """Хук через stdin, як його кличе Claude Code; stdout має бути порожнім."""
    r = subprocess.run([sys.executable, str(HOOKS / "log_prompt.py")], input=b"not json",
                       capture_output=True, timeout=30)
    assert r.returncode == 0 and r.stdout == b""


def test_no_large_files_tracked() -> None:
    """Медіа — в R2, не в Git. Ловимо випадково закомічені великі файли."""
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout
    big = [f for f in files.decode("utf-8").split("\0")
           if f and (ROOT / f).is_file() and (ROOT / f).stat().st_size > 5 * 1024 * 1024]
    assert big == [], f"Файли > 5 МБ у Git: {big}"
