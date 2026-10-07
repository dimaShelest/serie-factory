"""Журнал лабораторії (fabrica/lab.py): останній кадр відео (ffmpeg підмінено), кадр «<кліп>-last» руками (лише
зображення, не тест шаблону, автоматиці — з оцінкою ≥ 4), golden_file для поточного промпту, ref_file. Елементи
збираємо руками — без компіляторів промптів."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from fabrica import lab as lab_mod
from fabrica import prompts as P

SLUG = "la-garganta"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
MP4 = b"\x00\x00\x00\x18ftypmp42fake-clip"


def _tpl(tid: str, version: int = 2) -> P.Template:
    return P.Template(tid, tid.split(".")[0], version, "", {}, "", "", {}, Path(f"{tid}.yaml"), f"{tid[:6]:0<12}")


def _item(iid: str, kind: str, *, payload: dict | None = None, produces: str | None = None, set_: str = "1",
          tpl: str | None = None) -> P.Item:
    tid = tpl or {"image": "image.start_frame", "video": "video.i2v", "voice": "voice.line"}[kind]
    payload = payload or {"prompt": f"prompt {iid}"}
    return P.Item(iid, set_, kind, f"title {iid}", _tpl(tid), payload.get("prompt", ""), "", {}, [], produces, {},
                  [], 5 if kind == "image" else 6, "replicate:x", payload, [])


@pytest.fixture
def items() -> list[P.Item]:
    return [_item("cast-beto-front", "image", produces="beto.front", set_="casting", tpl="image.character"),
            _item("p1-1.02-frame", "image", produces="p1.1.02.frame"),
            _item("p1-1.02-video", "video", payload={"prompt": "Beto turns.", "image": "ref:p1.1.02.frame"},
                  produces="p1.1.02.c1"),
            _item("p1-1.02-video-2", "video", payload={"prompt": "Continues.", "image": "ref:p1.1.02.c1.last"},
                  produces="p1.1.02.c2")]


@pytest.fixture
def built() -> list[str]:
    """Які набори збирав prompts.build."""
    return []


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, items: list[P.Item], built: list[str]) -> Path:
    """Журнал, медіа й golden — у тимчасовій теці; prompts.build віддає зібрані руками елементи."""
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))

    def build(slug, set_name, kinds=None, only=None, out_root=None, templates=None):
        built.append(set_name)
        return [i for i in items if i.set == set_name]

    monkeypatch.setattr(P, "build", build)
    return tmp_path


class FakeFFmpeg:
    """shutil.which → шлях; subprocess.run → пише PNG у останній аргумент (або падає перші fail разів)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, fail: int = 0, exe: str | None = "/opt/ffmpeg") -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.fail = fail
        monkeypatch.setattr(lab_mod.shutil, "which", lambda name: exe if name == "ffmpeg" else None)
        monkeypatch.setattr(lab_mod.subprocess, "run", self.run)

    def run(self, args, **kw):
        self.calls.append((list(args), kw))
        if len(self.calls) <= self.fail:
            return subprocess.CompletedProcess(args, 1, "", "moov atom not found\nдруга лінія")
        Path(args[-1]).write_bytes(PNG)
        return subprocess.CompletedProcess(args, 0, "", "")


def _file(tmp: Path, name: str, data: bytes = PNG) -> Path:
    f = tmp / name
    f.write_bytes(data)
    return f


# ---------------------------------------------------------------- останній кадр


def test_extract_last_frame_uses_list_args_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ff = FakeFFmpeg(monkeypatch)
    clip = _file(tmp_path, "clip.mp4", MP4)
    out, warn = lab_mod.extract_last_frame(clip)
    assert warn is None and out == tmp_path / "clip.last.png" and out.read_bytes() == PNG
    args, kw = ff.calls[0]
    assert args[0] == "/opt/ffmpeg" and args[args.index("-sseof") + 1] == "-1"
    assert args[args.index("-i") + 1] == str(clip)
    assert "-update" in args and args[-1] == str(out) and kw["timeout"] > 0 and "shell" not in kw


def test_extract_falls_back_to_whole_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ff = FakeFFmpeg(monkeypatch, fail=1)
    out, warn = lab_mod.extract_last_frame(_file(tmp_path, "c.mov", MP4), tmp_path / "new" / "x.png")   # теки ще нема
    assert warn is None and out.is_file() and len(ff.calls) == 2 and "-sseof" not in ff.calls[1][0]


def test_extract_reports_failure_and_missing_ffmpeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clip = _file(tmp_path, "c.mp4", MP4)
    FakeFFmpeg(monkeypatch, fail=2)
    out, warn = lab_mod.extract_last_frame(clip, item_id="p1-1.02-video")
    assert out is None and "moov atom" in warn and "fabrica lab log p1-1.02-video-last" in warn
    assert not (tmp_path / "c.last.png").exists()
    FakeFFmpeg(monkeypatch, exe=None)
    out, warn = lab_mod.extract_last_frame(clip, item_id="p1-1.02-video")
    assert out is None and "немає ffmpeg" in warn and "p1-1.02-video-last" in warn


def test_log_video_stores_last_frame(lab: Path, monkeypatch: pytest.MonkeyPatch, items: list[P.Item]) -> None:
    FakeFFmpeg(monkeypatch)
    e = lab_mod.log(SLUG, "p1-1.02-video", "dropshot", 5, _file(lab, "clip.mp4", MP4), "ок")
    assert e["warnings"] == [] and e["last_frame"].endswith(".last.png")
    frame = Path(e["last_frame"])
    assert frame.is_file() and frame.parent == Path(e["file"]).parent == lab / "media" / "lab" / SLUG / "p1-1.02-video"
    saved = yaml.safe_load(lab_mod.RESULTS.read_text(encoding="utf-8"))["results"][0]
    assert saved["last_frame"] == e["last_frame"] and "warnings" not in saved
    assert saved["prompt_sha"] == items[2].prompt_sha


def test_log_video_without_ffmpeg_warns(lab: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    FakeFFmpeg(monkeypatch, exe=None)
    e = lab_mod.log(SLUG, "p1-1.02-video", "dropshot", 4, _file(lab, "clip.webm", MP4))
    assert "last_frame" not in e and len(e["warnings"]) == 1 and "ffmpeg" in e["warnings"][0]
    assert "last_frame" not in lab_mod.results(SLUG)[0]


def test_log_image_does_not_call_ffmpeg(lab: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ff = FakeFFmpeg(monkeypatch)
    e = lab_mod.log(SLUG, "p1-1.02-frame", "gemini", 5, _file(lab, "f.png"))
    assert ff.calls == [] and "last_frame" not in e and e["warnings"] == []


def test_manual_last_frame_of_clip(lab: Path, items: list[P.Item]) -> None:
    e = lab_mod.log(SLUG, "p1-1.02-video-last", "ffmpeg", 4, _file(lab, "last.png"))
    assert e["item"] == "p1-1.02-video-last" and e["kind"] == "image" and e["prompt_sha"] == items[2].prompt_sha
    assert Path(e["file"]).parent.name == "p1-1.02-video-last"
    with pytest.raises(lab_mod.LabError, match="лише для відео"):
        lab_mod.log(SLUG, "p1-1.02-frame-last", "gemini", 4)
    with pytest.raises(lab_mod.LabError, match="немає в наборі"):
        lab_mod.log(SLUG, "p1-9.99-video-last", "gemini", 4)


def test_last_row_takes_only_images(lab: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Регресія: «<кліп>-last --file clip.mp4» записував відео як «кадр» — автоматика стартувала б кліп з mp4."""
    ff = FakeFFmpeg(monkeypatch)
    with pytest.raises(lab_mod.LabError, match="відео кліпу логуй на сам кліп: `fabrica lab log p1-1.02-video "):
        lab_mod.log(SLUG, "p1-1.02-video-last", "dropshot", 5, _file(lab, "clip.mp4", MP4))
    with pytest.raises(lab_mod.LabError, match="«p1-1.02-frame» — кадр"):
        lab_mod.log(SLUG, "p1-1.02-frame", "gemini", 5, _file(lab, "frame.MOV", MP4))
    assert lab_mod.results(SLUG) == [] and not lab_mod.MEDIA.exists() and ff.calls == []


def test_log_checks_tool_and_file_type(lab: Path) -> None:
    """Інструмент і ім'я файлу йдуть у шлях копії в media/lab: «../» з інструмента вивів би файл з теки журналу."""
    for bad in ("../../evil", "a/b", "x" * 40, "-dash"):
        with pytest.raises(lab_mod.LabError, match="латиниця"):
            lab_mod.log(SLUG, "p1-1.02-frame", bad, 4, _file(lab, "f.png"))
    with pytest.raises(lab_mod.LabError, match="лише медіа"):
        lab_mod.log(SLUG, "p1-1.02-frame", "gemini", 4, _file(lab, "notes.txt", b"x"))
    assert lab_mod.results(SLUG) == [] and not lab_mod.MEDIA.exists()
    e = lab_mod.log(SLUG, "p1-1.02-frame", "AI Studio", 4, _file(lab, "Мій кадр (1).PNG"))
    name = Path(e["file"]).name
    assert e["tool"] == "ai-studio" and name.endswith("_ai-studio_1.png")
    assert Path(e["file"]).parent == lab / "media" / "lab" / SLUG / "p1-1.02-frame"
    assert all(c.isascii() and (c.isalnum() or c in "-_.") for c in name)


def test_last_frame_row_is_not_a_template_test(lab: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Регресія: кадр «<кліп>-last» з оцінкою 5 відкривав approve відео-шаблону без жодного кліпу ≥ 4."""
    monkeypatch.setattr(P, "load_templates", lambda root=None: {t: _tpl(t) for t in ("video.i2v", "image.start_frame")})
    lab_mod.log(SLUG, "p1-1.02-video-last", "ffmpeg", 5, _file(lab, "last.png"))
    with pytest.raises(lab_mod.LabError, match="video.i2v@v2"):
        lab_mod.approve(SLUG, "video.i2v")
    assert any(ln.startswith("video.i2v@v2") and "тестів:   0" in ln for ln in lab_mod.status(SLUG))
    lab_mod.log(SLUG, "p1-1.02-video", "dropshot", 2)
    lab_mod.log(SLUG, "p1-1.02-video-2", "dropshot", 4)
    assert "golden" in lab_mod.approve(SLUG, "video.i2v")
    line = next(ln for ln in lab_mod.status(SLUG) if ln.startswith("video.i2v@v2"))
    assert "тестів:   2" in line and "середня: 3.0" in line                      # кадр 5/5 у середню не входить


# ---------------------------------------------------------------- golden_file / ref_file


def _rows(items: list[P.Item], *rows: dict) -> list[dict]:
    by_id = {i.id: i for i in items}
    out = []
    for n, r in enumerate(rows, 1):
        it = by_id.get(r["item"]) or by_id.get(r["item"].removesuffix("-last"))
        out.append({"id": n, "story": SLUG, "tool": "gemini", "file": None, "prompt_sha": it.prompt_sha, **r})
    lab_mod._dump(lab_mod.RESULTS, {"results": out})
    return out


def _golden(**items_: tuple[P.Item, int | None, str | None]) -> None:
    """golden.yaml: {item_id: (елемент, id результату, prompt_sha або None = поточний)}."""
    lab_mod._dump(lab_mod.GOLDEN, {"templates": {}, "items": {SLUG: {
        it.id: {"prompt_sha": sha or it.prompt_sha, "result": rid} for it, rid, sha in items_.values()}}})


def test_golden_file_only_for_current_prompt(lab: Path, items: list[P.Item]) -> None:
    frame = items[1]
    old, new = _file(lab, "old.png"), _file(lab, "new.png")
    _rows(items, {"item": frame.id, "score": 5, "file": old.as_posix()},
          {"item": frame.id, "score": 4, "file": new.as_posix()})
    assert lab_mod.golden_file(SLUG, frame) is None                               # не golden
    _golden(f=(frame, 1, None))
    assert lab_mod.golden_file(SLUG, frame) == old
    _golden(f=(frame, 1, "0ldpr0mpt000"))                                         # golden для старого промпту
    assert lab_mod.golden_file(SLUG, frame) is None
    _golden(f=(frame, None, None))                                                # --force без результату
    assert lab_mod.golden_file(SLUG, frame) is None
    _golden(f=(frame, 2, None))
    new.unlink()                                                                  # файлу немає на диску
    assert lab_mod.golden_file(SLUG, frame) is None


def test_golden_file_last_frame(lab: Path, items: list[P.Item]) -> None:
    clip = items[2]
    last, manual = _file(lab, "clip.last.png"), _file(lab, "manual.png")
    _rows(items, {"item": clip.id, "score": 5, "file": "media/x.mp4", "last_frame": last.as_posix()},
          {"item": f"{clip.id}-last", "score": 4, "file": manual.as_posix()},
          {"item": f"{clip.id}-last", "score": 5, "file": manual.as_posix(), "prompt_sha": "0ldpr0mpt000"})
    _golden(c=(clip, 1, None))
    assert lab_mod.golden_file(SLUG, clip, last=True) == last
    last.unlink()
    assert lab_mod.golden_file(SLUG, clip, last=True) == manual                   # кадр, записаний руками
    assert lab_mod.golden_file(SLUG, clip) is None                                # сам кліп — немає файлу
    assert lab_mod.golden_result(SLUG, clip)["id"] == 1


def test_golden_file_ignores_weak_manual_frame(lab: Path, items: list[P.Item]) -> None:
    """Регресія: кадр «<кліп>-last» з оцінкою 1 («розмитий, не той кадр») ставав стартом платного кліпу."""
    clip = items[2]
    bad, ok = _file(lab, "bad.png"), _file(lab, "ok.png")
    _rows(items, {"item": clip.id, "score": 5},                                   # golden-кліп без файлу й кадру
          {"item": f"{clip.id}-last", "score": 1, "file": bad.as_posix(), "notes": "розмитий, не той кадр"})
    _golden(c=(clip, 1, None))
    assert lab_mod.golden_file(SLUG, clip, last=True) is None
    _rows(items, {"item": clip.id, "score": 5},
          {"item": f"{clip.id}-last", "score": 1, "file": bad.as_posix()},
          {"item": f"{clip.id}-last", "score": 4, "file": ok.as_posix()})
    assert lab_mod.golden_file(SLUG, clip, last=True) == ok
    assert lab_mod.golden_result(SLUG, items[1]) is None                          # кадр не golden


def test_ref_file_prefers_golden_then_good_scores(lab: Path, items: list[P.Item]) -> None:
    frame = items[1]
    weak, good, stale, gold = (_file(lab, f"{n}.png") for n in ("weak", "good", "stale", "gold"))
    _rows(items, {"item": frame.id, "score": 3, "file": weak.as_posix()},
          {"item": frame.id, "score": 5, "file": stale.as_posix(), "prompt_sha": "0ldpr0mpt000"},
          {"item": frame.id, "score": 5, "file": good.as_posix()},
          {"item": frame.id, "score": 4, "file": gold.as_posix()},
          {"item": frame.id, "score": 5})                                         # без файлу
    assert lab_mod.ref_file(SLUG, "p1.1.02.frame", items) == good                # ≥ 4 і поточний промпт, вища оцінка
    _golden(f=(frame, 4, None))
    assert lab_mod.ref_file(SLUG, "p1.1.02.frame", items) == gold
    good.unlink()
    gold.unlink()
    assert lab_mod.ref_file(SLUG, "p1.1.02.frame", items) == stale               # ≥ 4 старого промпту > 3 поточного
    stale.unlink()
    assert lab_mod.ref_file(SLUG, "p1.1.02.frame", items) == weak
    assert lab_mod.ref_file(SLUG, "nope.front", items) is None


def test_ref_file_last_and_default_pool(lab: Path, items: list[P.Item], built: list[str]) -> None:
    clip = items[2]
    last, manual = _file(lab, "l.png"), _file(lab, "m.png")
    _rows(items, {"item": clip.id, "score": 4, "file": "media/c.mp4", "last_frame": last.as_posix()},
          {"item": f"{clip.id}-last", "score": 5, "file": manual.as_posix()})
    assert lab_mod.ref_file(SLUG, "p1.1.02.c1.last") == manual                   # пул — частина 1 (за id референсу)
    assert built == ["1"]
    manual.unlink()
    assert lab_mod.ref_file(SLUG, "p1.1.02.c1.last") == last
    assert lab_mod.ref_file(SLUG, "p1.1.02.c2.last") is None                     # кліпу 2 ще немає
    beto = _file(lab, "beto.png")
    _rows(items, {"item": "cast-beto-front", "score": 4, "file": beto.as_posix()})
    assert lab_mod.ref_file(SLUG, "beto.front") == beto and built[-1] == "casting"
