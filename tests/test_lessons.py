"""Уроки лабораторії (fabrica/lessons.py): add / set_active / all, урок «на пробу» (pending), заборони avoid →
«lint: урок L3: …», шапка файлу при перезаписі, CLI `fabrica lab lessons --off / --on`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import lessons as L
from fabrica.cli import app

SLUG = "demo"


@pytest.fixture(autouse=True)
def series(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(bible_mod, "SERIES", tmp_path / "series")
    (tmp_path / "series" / SLUG / "lab").mkdir(parents=True)
    L._CACHE.clear()
    return tmp_path / "series" / SLUG


LESSON = {"item": "p1-1.02-video", "route": "replicate:bytedance/seedance-2.5", "kind": "video",
          "problem": "камера трясеться", "rule": "The camera stays locked off on a tripod for the whole clip.",
          "scope": {"kind": "video", "route": None, "tags": ["vhs"]}}


def test_add_assigns_ids_and_keeps_header(series: Path) -> None:
    (series / "lab" / "lessons.yaml").write_text("# моя шапка\n# ще рядок\n\nlessons: []\n", encoding="utf-8")
    assert L.add(SLUG, LESSON) == "L1"
    assert L.add(SLUG, {**LESSON, "rule": "Second rule.", "id": "L99"}) == "L2"       # id з запиту ігноруємо
    text = (series / "lab" / "lessons.yaml").read_text(encoding="utf-8")
    assert text.startswith("# моя шапка\n# ще рядок\n")
    rows = L.all(SLUG)
    assert [r["id"] for r in rows] == ["L1", "L2"]
    assert rows[0]["scope"] == {"kind": "video", "tags": ["vhs"]} and rows[0]["active"] is True and rows[0]["at"]
    assert set(rows[0]) <= L.KEYS


def test_add_creates_file_with_default_header(series: Path) -> None:
    L.add(SLUG, LESSON)
    text = (series / "lab" / "lessons.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Уроки лабораторії") and yaml.safe_load(text)["lessons"][0]["id"] == "L1"


def test_add_rejects_bad_lessons() -> None:
    with pytest.raises(L.LessonError, match="rule"):
        L.add(SLUG, {**LESSON, "rule": " "})
    with pytest.raises(L.LessonError, match="regex"):
        L.add(SLUG, {**LESSON, "avoid": ["(unclosed"]})
    with pytest.raises(L.LessonError, match="невідомі ключі"):
        L.add(SLUG, {**LESSON, "colour": "red"})
    assert L.all(SLUG) == []


def test_set_active_and_match() -> None:
    L.add(SLUG, LESSON)
    assert [r["id"] for r in L.match(SLUG, "video", "x", "video.i2v", {"footage:vhs"})] == ["L1"]
    assert L.match(SLUG, "video", "x", "video.i2v", {"footage:phone"}) == []        # tags: vhs
    assert L.set_active(SLUG, "L1", False)["active"] is False
    assert L.match(SLUG, "video", "x", "video.i2v", {"footage:vhs"}) == []
    assert L.all(SLUG)[0]["active"] is False                                        # історія лишається
    L.set_active(SLUG, "L1", True)
    assert L.rules_for(SLUG, "video", "x", "video.i2v", {"footage:vhs"}) == [LESSON["rule"]]
    with pytest.raises(L.LessonError, match="уроку «L7» немає"):
        L.set_active(SLUG, "L7", False)


def test_pending_visible_only_inside() -> None:
    preview = {**LESSON, "id": L.next_id(SLUG), "active": True}
    with L.pending(SLUG, preview):
        assert [r["id"] for r in L.load(SLUG)] == ["L1"]
        assert L.all(SLUG) == []                                                    # файлу це не стосується
    assert L.load(SLUG) == []
    with L.pending(SLUG, None):
        assert L.load(SLUG) == []


def test_lint_hits() -> None:
    L.add(SLUG, {**LESSON, "avoid": [r"\bshak(y|ing)\b", r"tripod-?less"]})
    L.add(SLUG, {**LESSON, "rule": "Keep it dark.", "avoid": [r"\bbright\b"], "active": False})
    hits = L.lint_hits(SLUG, ["L1", "L2", "L9"], "A Shaky handheld camera, bright light, shaky again")
    assert hits == [f"lint: урок L1: «Shaky» → {LESSON['rule']}"]                   # L2 вимкнено, L9 немає
    assert L.lint_hits(SLUG, ["L1"], "steady") == []


def test_cli_lab_lessons(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    runner = CliRunner()
    r = runner.invoke(app, ["lab", "lessons", "--story", SLUG])
    assert r.exit_code == 0 and "Уроків ще немає" in r.output
    L.add(SLUG, LESSON)
    r = runner.invoke(app, ["lab", "lessons", "--story", SLUG, "--off", "L1"])
    assert r.exit_code == 0, r.output
    assert "✗ вимкнено L1" in r.output and "○ L1" in r.output and "проблема: камера трясеться" in r.output
    assert L.all(SLUG)[0]["active"] is False
    r = runner.invoke(app, ["lab", "lessons", "--story", SLUG, "--on", "L1"])
    assert "● L1" in r.output and L.all(SLUG)[0]["active"] is True
    r = runner.invoke(app, ["lab", "lessons", "--story", SLUG, "--off", "L5"])
    assert r.exit_code == 1 and "L5" in r.output
