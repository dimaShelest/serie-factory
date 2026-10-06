"""CLI fabrica (fabrica/cli.py) на справжніх файлах LA GARGANTA, результати — у тимчасовій теці."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fabrica.cli import app

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "la-garganta" / "part1.script.json"
runner = CliRunner()


@pytest.fixture
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for key in ("BUDGET_PER_EPISODE_USD", "BUDGET_DAILY_USD", "BUDGET_MONTHLY_USD"):
        monkeypatch.setenv(key, "")
    folder = tmp_path / "la-garganta" / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    return tmp_path


def run(*args: str) -> tuple[int, str]:
    r = runner.invoke(app, list(args))
    return r.exit_code, r.output


def test_help() -> None:
    code, text = run("--help")
    assert code == 0 and "shotlist" in text and "validate" in text and "costs" in text


def test_shotlist_writes_shots_json(out: Path) -> None:
    code, text = run("shotlist", "la-garganta", "1", "--out", str(out))
    assert code == 0, text
    data = json.loads((out / "la-garganta" / "part1" / "shots.json").read_text(encoding="utf-8"))
    assert len(data["shots"]) == 87
    assert "✓ розбір розкадровки без втрат" in text
    assert "TEASER1: 28 с" in text                  # відома розбіжність розкадровки (tests/test_shotlist.py)


def test_validate_reports_each_check(out: Path) -> None:
    run("shotlist", "la-garganta", "1", "--out", str(out))
    code, text = run("validate", "la-garganta", "1", "--out", str(out))
    assert "✓ script: правила PLAYBOOK" in text
    assert "✓ script: без втрат щодо story.md" in text
    assert "✗ shots: правила PLAYBOOK" in text
    assert code == 1                                # поки розкадровка порушує PLAYBOOK


def test_validate_broken_json(out: Path) -> None:
    (out / "la-garganta" / "part1" / "script.json").write_text('{"story": "la-garganta"}', encoding="utf-8")
    code, text = run("validate", "la-garganta", "1", "--out", str(out))
    assert code == 1 and "script.json не за схемою" in text


def test_costs_matches_shotlist(out: Path) -> None:
    run("shotlist", "la-garganta", "1", "--out", str(out))
    code, text = run("costs", "la-garganta", "1", "--out", str(out))
    assert code == 0, text
    assert "$  126.02" in text
    code, text = run("costs", "la-garganta", "1", "--out", str(out), "--min-clip", "5")
    assert "$  145.26" in text
    assert (out / "fabrica.sqlite").exists()


def test_schema_command() -> None:
    code, text = run("schema", "shots")
    assert code == 0 and json.loads(text)["title"] == "Shots"
