"""Прогрес студії (fabrica/progress.py): статуси в lab/progress.yaml, застарілі статуси (інший prompt_sha), правила
запису результату, «Далі»; CLI `lab log` друкує попередження й останній кадр і оновлює статус."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fabrica import progress as progress_mod
from fabrica.cli import app

SLUG = "la-garganta"


@pytest.fixture(autouse=True)
def tmp_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "lab" / "progress.yaml"
    monkeypatch.setattr(progress_mod, "PROGRESS", path)
    return path


def test_set_and_load_roundtrip(tmp_progress: Path) -> None:
    assert progress_mod.load(SLUG) == {}
    e = progress_mod.set_status(SLUG, "cast-beto-1994", "in_work", "abc123")
    assert e["status"] == "in_work" and e["prompt_sha"] == "abc123" and e["at"]
    raw = yaml.safe_load(tmp_progress.read_text(encoding="utf-8"))
    assert raw == {SLUG: {"cast-beto-1994": e}}
    assert progress_mod.load(SLUG)["cast-beto-1994"]["status"] == "in_work"
    assert progress_mod.load("other") == {}


def test_bad_status_and_broken_file(tmp_progress: Path) -> None:
    with pytest.raises(progress_mod.ProgressError, match="невідомий статус «finished»"):
        progress_mod.set_status(SLUG, "x", "finished", "s")
    tmp_progress.parent.mkdir(parents=True)
    tmp_progress.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(progress_mod.ProgressError, match="progress.yaml"):
        progress_mod.load(SLUG)


@pytest.mark.parametrize("entry, sha, golden, passed, want", [
    ({"status": "skip", "prompt_sha": "new"}, "new", False, False, ("skip", False)),       # явний вибір — він
    ({"status": "todo", "prompt_sha": "new"}, "new", True, True, ("todo", False)),         # явний перекриває журнал
    ({"status": "done", "prompt_sha": "old"}, "new", False, False, ("todo", True)),        # промпт змінився
    ({"status": "approved", "prompt_sha": "old"}, "new", False, True, ("done", False)),    # новий результат ≥ 4
    ({"status": "todo", "prompt_sha": "old"}, "new", False, False, ("todo", False)),       # todo не «застаріває»
    (None, "new", True, False, ("approved", False)),
    (None, "new", False, True, ("done", False)),
    (None, "new", False, False, ("todo", False)),
])
def test_effective(entry, sha, golden, passed, want) -> None:
    assert progress_mod.effective(entry, sha, golden=golden, passed=passed) == want


def test_on_log_rules() -> None:
    assert progress_mod.on_log(SLUG, "a", 3, "s1") == "in_work"           # спроба нижче 4 — у роботі
    assert progress_mod.on_log(SLUG, "a", 2, "s1") is None                # уже in_work
    assert progress_mod.on_log(SLUG, "a", 4, "s1") == "done"
    assert progress_mod.on_log(SLUG, "a", 5, "s1") is None                # уже done
    progress_mod.set_status(SLUG, "a", "approved", "s1")
    assert progress_mod.on_log(SLUG, "a", 5, "s1") is None                # approved не знижуємо
    assert progress_mod.on_log(SLUG, "a", 1, "s2") == "in_work"           # новий промпт — заново
    assert progress_mod.load(SLUG)["a"] | {"at": ""} == {"status": "in_work", "prompt_sha": "s2", "at": ""}


def test_next_id() -> None:
    rows = [("a", "done", True), ("b", "todo", False), ("c", "in_work", True), ("d", "skip", True)]
    assert progress_mod.next_id(rows) == "c"                              # перший відкритий з готовими потребами
    assert progress_mod.next_id([("a", "approved", True), ("b", "todo", False)]) == "b"
    assert progress_mod.next_id([("a", "done", True), ("b", "skip", False)]) is None


def test_cli_lab_log_prints_warnings_and_last_frame(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fabrica import cli

    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    entry = {"id": 7, "item": "p1-1.02-video", "tool": "dropshot", "score": 5, "template": "video.i2v",
             "template_version": 3, "prompt_sha": "abc", "file": "media/lab/x.mp4", "last_frame": "media/lab/x.last.png",
             "warnings": ["немає ffmpeg — останній кадр не витягнуто"]}
    monkeypatch.setattr(cli.lab_mod, "log", lambda *a, **k: dict(entry))
    r = CliRunner().invoke(app, ["lab", "log", "p1-1.02-video", "--tool", "dropshot", "--score", "5",
                                 "--story", SLUG])
    assert r.exit_code == 0, r.output
    assert "останній кадр: media/lab/x.last.png" in r.output and "⚠️ немає ffmpeg" in r.output
    assert "статус у студії: done" in r.output
    assert progress_mod.load(SLUG)["p1-1.02-video"]["status"] == "done"


def test_cli_lab_log_last_frame_row_keeps_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fabrica import cli

    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    entry = {"id": 8, "item": "p1-1.02-video-last", "tool": "other", "score": 5, "template": "video.i2v",
             "template_version": 3, "prompt_sha": "abc", "file": "media/lab/f.png", "warnings": []}
    monkeypatch.setattr(cli.lab_mod, "log", lambda *a, **k: dict(entry))
    r = CliRunner().invoke(app, ["lab", "log", "p1-1.02-video-last", "--tool", "other", "--score", "5",
                                 "--story", SLUG])
    assert r.exit_code == 0, r.output
    assert progress_mod.load(SLUG) == {}
