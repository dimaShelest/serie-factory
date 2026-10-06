"""CLI fabrica (fabrica/cli.py) на справжніх файлах LA GARGANTA, результати — у тимчасовій теці.

Тести перевіряють зв'язку CLI з модулями (кількість шотів = convert, сума = estimate, код виходу = чи є «✗»),
а не константи розкадровки: правка part1_shotlist.md не має робити їх червоними.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import costs as costs_mod
from fabrica import shotlist as shotlist_mod
from fabrica.cli import app
from fabrica.models import Script, Shots

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "la-garganta" / "part1.script.json"
SHOTLIST = ROOT / "series" / "la-garganta" / "part1_shotlist.md"
runner = CliRunner()


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ізольований .env — справжній .env репо тести не читають."""
    for key in ("BUDGET_PER_EPISODE_USD", "BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text("BUDGET_PER_EPISODE_USD=none\nBUDGET_DAILY_USD=none\nBUDGET_MONTHLY_USD=none\n", encoding="utf-8")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(path))
    return path


@pytest.fixture
def out(tmp_path: Path, env: Path) -> Path:
    folder = tmp_path / "out" / "la-garganta" / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    return tmp_path / "out"


def run(*args: str) -> tuple[int, str]:
    r = runner.invoke(app, list(args))
    return r.exit_code, r.output


def test_help() -> None:
    code, text = run("--help")
    assert code == 0 and "shotlist" in text and "validate" in text and "costs" in text


def test_help_survives_non_utf8_pipe() -> None:
    """Windows: вивід у pipe/файл у cp1252 — `fabrica --help` не має падати на «→»/кирилиці."""
    r = subprocess.run([sys.executable, "-c", "from fabrica.cli import main; main()", "--help"],
                       capture_output=True, cwd=ROOT, timeout=60,
                       env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONPATH": str(ROOT)})
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")


def test_shotlist_writes_shots_json(out: Path) -> None:
    code, text = run("shotlist", "la-garganta", "1", "--out", str(out))
    dest = out / "la-garganta" / "part1" / "shots.json"
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, issues = shotlist_mod.convert(SHOTLIST, bible_mod.load("la-garganta"), 1, script)
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert len(data["shots"]) == len(raw["shots"])
    assert b"\r\n" not in dest.read_bytes()                     # LF на всіх ОС
    assert code == (1 if "✗" in text else 0), text
    assert ("✓ розбір розкадровки без втрат" in text) == (not issues)


def test_shotlist_without_script_is_not_a_failure(tmp_path: Path, env: Path) -> None:
    code, text = run("shotlist", "la-garganta", "1", "--out", str(tmp_path / "o"))
    assert "script.json немає" in text
    assert code == (1 if "✗" in text else 0), text


def test_validate_reports_each_check(out: Path) -> None:
    run("shotlist", "la-garganta", "1", "--out", str(out))
    code, text = run("validate", "la-garganta", "1", "--out", str(out))
    for title in ("script: правила PLAYBOOK", "script: без втрат щодо story.md", "shots: правила PLAYBOOK",
                  "shots покривають script"):
        assert title in text
    assert code == (1 if "✗" in text else 0), text


def test_validate_nothing_to_check_is_error(tmp_path: Path, env: Path) -> None:
    code, text = run("validate", "la-garganta", "2", "--out", str(tmp_path / "nowhere"))
    assert code == 1 and "нема що перевіряти" in text


def test_validate_broken_json(out: Path) -> None:
    (out / "la-garganta" / "part1" / "script.json").write_text('{"story": "la-garganta"}', encoding="utf-8")
    code, text = run("validate", "la-garganta", "1", "--out", str(out))
    assert code == 1 and "не за схемою" in text


def test_validate_reads_bom(out: Path) -> None:
    path = out / "la-garganta" / "part1" / "script.json"
    path.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8-sig")   # PowerShell 5.1
    code, text = run("validate", "la-garganta", "1", "--out", str(out))
    assert "не за схемою" not in text


def test_costs_matches_estimate(out: Path) -> None:
    run("shotlist", "la-garganta", "1", "--out", str(out))
    shots = Shots.model_validate_json((out / "la-garganta" / "part1" / "shots.json").read_text(encoding="utf-8"))
    for extra, min_clip in (((), 0.0), (("--min-clip", "5"), 5.0)):
        code, text = run("costs", "la-garganta", "1", "--out", str(out), *extra)
        est = costs_mod.estimate(shots, costs_mod.load_rates(), min_clip_s=min_clip)
        assert code == 0, text
        assert f"${est.usd:>8.2f}" in text
    assert (out / "fabrica.sqlite").exists()


def test_costs_over_limit_exits_1(out: Path, env: Path) -> None:
    env.write_text("BUDGET_PER_EPISODE_USD=10\nBUDGET_DAILY_USD=none\nBUDGET_MONTHLY_USD=none\n", encoding="utf-8")
    run("shotlist", "la-garganta", "1", "--out", str(out))
    code, text = run("costs", "la-garganta", "1", "--out", str(out))
    assert code == 1 and "буде перевищено" in text and "ПЕРЕВИЩЕНО (force)" not in text


def test_costs_without_limits_warns(out: Path, env: Path) -> None:
    env.write_text("", encoding="utf-8")
    run("shotlist", "la-garganta", "1", "--out", str(out))
    code, text = run("costs", "la-garganta", "1", "--out", str(out))
    assert code == 0 and "не задано" in text


@pytest.mark.parametrize("args", [("--attempts", "0"), ("--attempts", "-3"), ("--min-clip", "-1")])
def test_costs_rejects_bad_options(out: Path, args: tuple[str, str]) -> None:
    code, _ = run("costs", "la-garganta", "1", "--out", str(out), *args)
    assert code == 2


def test_costs_without_shots_is_friendly(tmp_path: Path, env: Path) -> None:
    code, text = run("costs", "la-garganta", "1", "--out", str(tmp_path / "o"))
    assert code == 1 and "спершу `fabrica shotlist" in text


def test_unknown_story_is_one_line(tmp_path: Path, env: Path) -> None:
    code, text = run("validate", "no-such-story", "1", "--out", str(tmp_path))
    assert code == 1 and "Traceback" not in text


def test_schema_command() -> None:
    code, text = run("schema", "shots")
    assert code == 0 and json.loads(text)["title"] == "Shots"
