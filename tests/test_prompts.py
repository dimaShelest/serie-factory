"""Лабораторія промптів: шаблони, набори (casting / test-pack / частина), журнал, golden, переглядач, CLI."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from fabrica import bible as bible_mod
from fabrica import lab as lab_mod
from fabrica import prompts as P
from fabrica import shotlist as shotlist_mod
from fabrica import viewer as viewer_mod
from fabrica.cli import app
from fabrica.models import Script, Shots

ROOT = Path(__file__).resolve().parents[1]
SLUG = "la-garganta"
FIXTURE = ROOT / "tests" / "fixtures" / SLUG / "part1.script.json"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


@pytest.fixture(scope="module")
def casting() -> list[P.Item]:
    return P.build(SLUG, "casting")


@pytest.fixture(scope="module")
def test_pack() -> list[P.Item]:
    return P.build(SLUG, "test-pack")


@pytest.fixture
def lab_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Журнал, медіа й golden — у тимчасовій теці, не в репо."""
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    return tmp_path


# ---------------------------------------------------------------- шаблони й дані


def test_templates_load_with_versions() -> None:
    ts = P.load_templates()
    assert {"image.character", "image.member_1994", "image.location", "image.start_frame", "image.thumbnail",
            "video.shot", "voice.line", "voice.design"} <= set(ts)
    assert all(t.version >= 1 and len(t.sha) == 12 for t in ts.values())


def test_bad_template_is_clear_error(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text("id: video.x\nkind: image\nversion: 1\nprompt: hi\n", encoding="utf-8")
    with pytest.raises(P.PromptError, match="kind"):
        P.load_templates(tmp_path)


def test_prompt_en_in_sync_with_bible() -> None:
    """Кожен персонаж / учасник сімки / локація біблії має англійський опис; кількість ознак ДНК однакова."""
    data = P.Data(SLUG)
    for cid, ch in data.characters.items():
        assert len(data.en["characters"][cid]["dna"]) == len(ch["visual_dna"]), cid
    assert set(data.members) == set(data.en["members"])
    assert set(data.locations) == set(data.en["locations"])


def test_missing_data_is_prompt_error() -> None:
    t = P.load_templates()["image.location"]
    with pytest.raises(P.PromptError, match="бракує даних"):
        P.render(t, {"style": {}, "rules": [], "negative": {"common": []}})


# ---------------------------------------------------------------- набори


def _clean(items: list[P.Item]) -> None:
    for it in items:
        assert it.prompt and "{{" not in it.prompt and "{%" not in it.prompt, it.id
        assert not re.search(r"[a-z][.;][A-Za-z]", it.prompt), f"злиплі речення: {it.id}"
        assert "[UA → EN]" not in it.prompt, it.id


def test_casting_set(casting: list[P.Item]) -> None:
    ids = {i.id for i in casting}
    data = P.Data(SLUG)
    for cid in data.characters:
        for suffix in ("front", "34", "profile", "full", "emo1", "emo2", "emo3", "voice"):
            assert f"cast-{cid}-{suffix}" in ids
    for mid in data.members:
        assert {f"cast-{mid}-1994", f"cast-{mid}-wet"} <= ids
    by = {i.id: i for i in casting}
    assert by["cast-mateo-front"].refs == [] and by["cast-mateo-profile"].refs == ["mateo.front"]
    assert by["cast-tomas-1994"].refs == ["mateo.front"]               # Tomás = обличчя Mateo
    assert by["cast-beto-wet"].refs == ["beto.1994"]
    assert "Strictly:" in by["cast-vale-front"].prompt and "adult" in by["cast-vale-front"].prompt
    assert len(by["cast-vale-voice"].extra["preview_es"]) >= 100      # Voice Design вимагає ≥ 100 символів
    assert by["loc-mina-dawn"].produces == "mina.dawn" and "dawn" in by["loc-mina-dawn"].prompt
    _clean(casting)


def test_test_pack_set(test_pack: list[P.Item]) -> None:
    by = {i.id: i for i in test_pack}
    assert set(by) >= {"tp-T1-frame", "tp-T1-video", "tp-T4-buildup", "tp-T4-face-frame", "tp-T4-face-video",
                       "tp-T5-video"}
    t1 = by["tp-T1-frame"]
    assert t1.refs == ["vale.front", "diego.front", "sofia.front", "mateo.front", "mina.dawn"]
    assert "Lighting: dawn" in t1.prompt                                 # стан локації міняє світло
    v = by["tp-T1-video"]
    assert v.params["resolution"] == "720p" and v.params["duration_s"] == 8 and v.extra["first_frame"] == "tp.T1.frame"
    assert by["tp-T4-buildup"].params["resolution"] == "480p" and "VHS" in by["tp-T4-buildup"].prompt
    assert "soaked" in by["tp-T4-face-frame"].prompt and by["tp-T4-face-frame"].refs[0] == "beto.wet"
    _clean(test_pack)


def test_prompt_sha_and_seed_are_stable(test_pack: list[P.Item]) -> None:
    again = {i.id: i for i in P.build(SLUG, "test-pack")}
    for it in test_pack:
        assert again[it.id].prompt_sha == it.prompt_sha and again[it.id].params["seed"] == it.params["seed"]
    assert len({i.params["seed"] for i in test_pack}) == len(test_pack)


def test_template_edit_changes_sha(tmp_path: Path) -> None:
    root = tmp_path / "templates"
    shutil.copytree(P.TEMPLATES, root)
    before = P.build(SLUG, "test-pack", only="tp-T1-frame", templates=P.load_templates(root))[0]
    f = root / "image" / "start_frame.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("16:9.", "16:9 cinematic."), encoding="utf-8")
    after = P.build(SLUG, "test-pack", only="tp-T1-frame", templates=P.load_templates(root))[0]
    assert after.template.sha != before.template.sha and after.prompt_sha != before.prompt_sha


def test_part_set_with_voice_and_warnings(tmp_path: Path) -> None:
    folder = tmp_path / SLUG / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(ROOT / "series" / SLUG / "part1_shotlist.md", bible_mod.load(SLUG), 1, script)
    shots = Shots.model_validate(raw)
    (folder / "shots.json").write_text(shots.model_dump_json(), encoding="utf-8")
    items = P.build(SLUG, "1", out_root=tmp_path)
    voices = [i for i in items if i.kind == "voice"]
    assert len(voices) == sum(len(sh.dialogue) for sh in shots.shots)
    chuy = next(i for i in voices if i.prompt.startswith("¡Chuy"))
    assert chuy.params["delivery"] == "shout" and chuy.params["settings"]["style"] == 0.7
    videos = [i for i in items if i.kind == "video"]
    assert videos and all(i.params["resolution"] in ("720p", "480p") for i in videos)
    assert any("англійського опису" in w for i in videos for w in i.warnings)     # part1_prompts_en.yaml ще немає


def test_unknown_set_and_item() -> None:
    with pytest.raises(P.PromptError, match="невідомий набір"):
        P.build(SLUG, "trailer")
    with pytest.raises(P.PromptError, match="немає елемента"):
        P.build(SLUG, "test-pack", only="tp-T9")
    assert P.set_of("cast-mateo-front") == "casting" and P.set_of("tp-T1-video") == "test-pack"
    assert P.set_of("p2-5.01-frame") == "2"


# ---------------------------------------------------------------- журнал і golden


def test_log_copies_file_and_binds_versions(lab_dirs: Path, test_pack: list[P.Item]) -> None:
    shot = lab_dirs / "t1.png"
    shot.write_bytes(PNG)
    e = lab_mod.log(SLUG, "tp-T1-frame", "Gemini", 4, shot, "камінці ок")
    item = next(i for i in test_pack if i.id == "tp-T1-frame")
    assert e["tool"] == "gemini" and e["template"] == "image.start_frame" and e["prompt_sha"] == item.prompt_sha
    assert e["template_sha"] == item.template.sha and len(e["file_sha256"]) == 64
    saved = yaml.safe_load((lab_dirs / "lab" / "results.yaml").read_text(encoding="utf-8"))["results"]
    assert saved[0]["id"] == 1 and (lab_dirs / "media" / "lab" / SLUG / "tp-T1-frame").is_dir()
    with pytest.raises(lab_mod.LabError):
        lab_mod.log(SLUG, "tp-T1-frame", "gemini", 7)
    with pytest.raises(lab_mod.LabError):
        lab_mod.log(SLUG, "tp-T1-frame", "gemini", 3, lab_dirs / "nope.png")


def test_approve_needs_a_good_result(lab_dirs: Path) -> None:
    with pytest.raises(lab_mod.LabError, match="≥ 4"):
        lab_mod.approve(SLUG, "image.start_frame")
    lab_mod.log(SLUG, "tp-T1-frame", "gemini", 3)
    with pytest.raises(lab_mod.LabError):
        lab_mod.approve(SLUG, "tp-T1-frame")
    lab_mod.log(SLUG, "tp-T1-frame", "gemini", 5)
    assert "golden" in lab_mod.approve(SLUG, "image.start_frame")
    assert "golden" in lab_mod.approve(SLUG, "tp-T1-frame")
    t = P.load_templates()["image.start_frame"]
    assert lab_mod.is_golden_template(t)
    lab_mod.require_golden(t)
    with pytest.raises(lab_mod.GoldenError):
        lab_mod.require_golden(P.load_templates()["video.shot"])     # не тестували — автоматика не бере
    assert "golden" in lab_mod.approve(SLUG, "video.shot", force=True)


def test_golden_breaks_when_template_changes_without_version(lab_dirs: Path, tmp_path: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    lab_mod.log(SLUG, "tp-T1-frame", "gemini", 5)
    lab_mod.approve(SLUG, "image.start_frame")
    root = tmp_path / "templates"
    shutil.copytree(P.TEMPLATES, root)
    f = root / "image" / "start_frame.yaml"
    f.write_text(f.read_text(encoding="utf-8") + "\n# правка\n", encoding="utf-8")
    t = P.load_templates(root)["image.start_frame"]
    assert not lab_mod.is_golden_template(t) and "зламано" in lab_mod.golden_state(t)


# ---------------------------------------------------------------- переглядач і CLI


def test_viewer_html(lab_dirs: Path, test_pack: list[P.Item], casting: list[P.Item]) -> None:
    img = lab_dirs / "mateo.png"
    img.write_bytes(PNG)
    lab_mod.log(SLUG, "cast-mateo-front", "gemini", 5, img)
    out = lab_dirs / "out"
    index = viewer_mod.write_package(SLUG, "test-pack", test_pack, out=out, producers=casting)
    text = index.read_text(encoding="utf-8")
    for it in test_pack:
        assert f"<code>{it.id}</code>" in text and (index.parent / f"{it.id}.md").exists()
    assert text.count('class="copy"') >= len(test_pack) and "Копіювати команду журналу" in text
    assert "mateo.front · 5/5" in text                         # мініатюра референсу з журналу
    assert "<script>" in text and "</html>" in text
    md = (index.parent / "tp-T1-video.md").read_text(encoding="utf-8")
    assert "uv run fabrica lab log tp-T1-video" in md and "```text" in md


def test_cli_prompts_and_lab(lab_dirs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(P, "OUT", lab_dirs / "out")
    monkeypatch.setattr(viewer_mod.write_package, "__defaults__", (lab_dirs / "out", None))
    runner = CliRunner()
    r = runner.invoke(app, ["prompts", SLUG, "test-pack", "--kind", "video"])
    assert r.exit_code == 0, r.output
    assert "Переглядач:" in r.output and (lab_dirs / "out" / SLUG / "test-pack" / "index.html").exists()
    r = runner.invoke(app, ["prompts", SLUG, "test-pack", "--kind", "sound"])
    assert r.exit_code == 1
    r = runner.invoke(app, ["lab", "log", "tp-T2-video", "--tool", "dreamina", "--score", "4", "--notes", "скло ок"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["lab", "approve", "tp-T2-video"])
    assert r.exit_code == 0 and "golden" in r.output
    r = runner.invoke(app, ["lab", "status"])
    assert r.exit_code == 0 and "video.shot@v1" in r.output
