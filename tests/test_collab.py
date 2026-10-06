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


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
                        *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


@pytest.fixture
def clones(tmp_path: Path) -> tuple[Path, Path]:
    """Голий origin і два клони: `me` (де працює хук) і `other` (партнер, що пушить)."""
    _git(tmp_path, "init", "--bare", "origin.git")
    for name in ("me", "other"):
        _git(tmp_path, "clone", "-q", "origin.git", name)
        for k, v in (("user.name", name), ("user.email", f"{name}@t")):
            _git(tmp_path / name, "config", k, v)
    (tmp_path / "me" / "a.txt").write_text("1\n", encoding="utf-8")
    _git(tmp_path / "me", "add", "a.txt")
    _git(tmp_path / "me", "commit", "-qm", "init")
    _git(tmp_path / "me", "push", "-q", "-u", "origin", "HEAD:main")
    _git(tmp_path / "other", "pull", "-q", "origin", "main")
    return tmp_path / "me", tmp_path / "other"


def _partner_commits(other: Path, text: str) -> None:
    (other / "a.txt").write_text(text, encoding="utf-8")
    _git(other, "commit", "-qam", "partner")
    _git(other, "push", "-q", "origin", "HEAD:main")


def test_pull_survives_double_fetch_head(clones: tuple[Path, Path]) -> None:
    """Гонка з автофетчем VS Code: main двічі у FETCH_HEAD ламала `git pull --rebase`."""
    me, other = clones
    _partner_commits(other, "2\n")
    _git(me, "fetch", "-q")
    fh = me / ".git" / "FETCH_HEAD"
    fh.write_text(fh.read_text(encoding="utf-8") * 2, encoding="utf-8")
    out = session_start.pull(me)
    assert "⚠️" not in out, out
    assert (me / "a.txt").read_text(encoding="utf-8") == "2\n"


def test_pull_conflict_aborts_rebase(clones: tuple[Path, Path]) -> None:
    me, other = clones
    _partner_commits(other, "partner\n")
    (me / "a.txt").write_text("mine\n", encoding="utf-8")
    _git(me, "commit", "-qam", "mine")
    out = session_start.pull(me)
    assert "КОНФЛІКТ" in out
    assert not (me / ".git" / "rebase-merge").exists() and not (me / ".git" / "rebase-apply").exists()
    assert (me / "a.txt").read_text(encoding="utf-8") == "mine\n"


def test_pull_without_upstream(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    assert "немає upstream" in session_start.pull(tmp_path)


def test_pull_reports_autostash_conflict(clones: tuple[Path, Path]) -> None:
    """Незакомічена правка конфліктує з партнером: rebase повертає 0, але лишає UU і stash — хук мусить кричати."""
    me, other = clones
    _partner_commits(other, "partner\n")
    (me / "a.txt").write_text("my uncommitted\n", encoding="utf-8")
    out = session_start.pull(me)
    assert "КОНФЛІКТ твоїх НЕЗАКОМІЧЕНИХ правок" in out, out
    assert "a.txt" in out and "stash@{0}" in out


def test_pull_autostash_without_conflict_is_quiet(clones: tuple[Path, Path]) -> None:
    me, other = clones
    (other / "b.txt").write_text("partner\n", encoding="utf-8")
    _git(other, "add", "b.txt")
    _git(other, "commit", "-qm", "partner b")
    _git(other, "push", "-q", "origin", "HEAD:main")
    (me / "a.txt").write_text("my uncommitted\n", encoding="utf-8")
    out = session_start.pull(me)
    assert "⚠️" not in out, out
    assert (me / "a.txt").read_text(encoding="utf-8") == "my uncommitted\n" and (me / "b.txt").exists()


def test_report_warns_when_not_on_main(clones: tuple[Path, Path]) -> None:
    me, _ = clones
    _git(me, "switch", "-q", "-c", "b/feature")
    assert "на гілці «b/feature», а не на main" in session_start.report(me, do_pull=False)
    _git(me, "switch", "-q", "main")
    assert "а не на main" not in session_start.report(me, do_pull=False)


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
