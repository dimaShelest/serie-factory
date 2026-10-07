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
from fabrica import shotspec as S
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
    with pytest.MonkeyPatch.context() as mp:              # довжина кліпу — профіль manual-5s, хоч би що в .env
        mp.setenv("GENERATION_PROFILE", "manual-5s")
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
            "video.i2v", "video.first_last", "video.t2v", "voice.line", "voice.design"} <= set(ts)
    assert "video.shot" not in ts                                       # v2: шаблон за режимом відео
    assert all(t.version >= 1 and len(t.sha) == 12 and t.route for t in ts.values())


def test_bad_template_is_clear_error(tmp_path: Path) -> None:
    (tmp_path / "x.yaml").write_text("id: video.x\nkind: image\nversion: 1\nprompt: hi\n", encoding="utf-8")
    with pytest.raises(P.PromptError, match="kind"):
        P.load_templates(tmp_path)
    (tmp_path / "x.yaml").write_text("id: image.x\nkind: image\nversion: 1\npayload: [a]\n", encoding="utf-8")
    with pytest.raises(P.PromptError, match="payload"):
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
    assert "every person is an adult" in by["cast-vale-front"].prompt and "adult" in by["cast-vale-front"].prompt
    assert len(by["cast-vale-voice"].extra["preview_es"]) >= 100      # Voice Design вимагає ≥ 100 символів
    assert by["cast-vale-voice"].payload["text"] == by["cast-vale-voice"].extra["preview_es"]
    assert by["loc-mina-dawn"].produces == "mina.dawn" and "dawn" in by["loc-mina-dawn"].prompt
    # порядок виробництва: якорі → ракурси → локації → голоси; якорі — Pro лише текстом
    assert [i.step for i in casting] == sorted(i.step for i in casting)
    assert (by["cast-vale-front"].step, by["cast-vale-front"].route) == (1, "replicate:google/nano-banana-pro")
    assert (by["cast-tomas-1994"].step, by["loc-mina"].step, by["cast-vale-voice"].step) == (2, 3, 4)
    assert not [w for i in casting for w in i.warnings if w.startswith("API:")]
    _clean(casting)


def test_test_pack_set(test_pack: list[P.Item]) -> None:
    by = {i.id: i for i in test_pack}
    assert set(by) >= {"tp-T1-frame", "tp-T1-video", "tp-T4-buildup", "tp-T4-face-frame", "tp-T4-face-video",
                       "tp-T5-video"}
    t1 = by["tp-T1-frame"]
    assert t1.refs == ["mina.dawn", "vale.front", "diego.front", "sofia.front", "mateo.front"]   # Image 1 — локація
    assert "Lighting: dawn" in t1.prompt                                 # стан локації міняє світло
    v = by["tp-T1-video"]                                                # 8 с → два кліпи по 5 с (manual-5s)
    assert (v.payload["resolution"], v.payload["duration"], v.payload["image"]) == ("720p", 5, "ref:tp.T1.frame")
    assert v.needs == ["tp.T1.frame"] and by["tp-T1-video-2"].needs == ["tp.T1.c1.last"]
    assert v.extra["clip"] | {"window": None} == {"index": 1, "of": 2, "gen_s": 5, "window": None, "start": "frame",
                                                  "start_ref": "tp.T1.frame", "start_item": "tp-T1-frame"}
    assert by["tp-T4-buildup"].route == "replicate:bytedance/seedance-2.5"   # без обличчя → Replicate
    assert "camcorder" in by["tp-T4-buildup"].prompt
    face = by["tp-T4-face-frame"]
    assert "soaked" in face.prompt and face.refs == ["mina.tunnel", "beto.wet"]
    assert by["tp-T4-face-video"].route == "cloudflare:bytedance/seedance-2.5"   # обличчя → Cloudflare
    assert by["tp-T4-face-video"].payload["use_virtual_avatar"] is True
    assert [i.step for i in test_pack] == sorted(i.step for i in test_pack)
    assert not [w for i in test_pack for w in i.warnings if w.startswith("API:")]
    _clean(test_pack)


def test_prompt_sha_and_seed_are_stable(test_pack: list[P.Item]) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GENERATION_PROFILE", "manual-5s")
        again = {i.id: i for i in P.build(SLUG, "test-pack")}
    for it in test_pack:
        assert again[it.id].prompt_sha == it.prompt_sha and again[it.id].payload == it.payload
    seeds = [i.payload["seed"] for i in test_pack if "seed" in i.payload]      # у Nano Banana сіда немає
    assert len(seeds) == len(set(seeds)) == sum(i.kind == "video" for i in test_pack)


def test_template_edit_changes_sha(tmp_path: Path) -> None:
    root = tmp_path / "templates"
    shutil.copytree(P.TEMPLATES, root)
    before = P.build(SLUG, "test-pack", only="tp-T1-frame", templates=P.load_templates(root))[0]
    f = root / "image" / "start_frame.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("cinematic film still.", "cinematic film photo."),
                 encoding="utf-8")
    after = P.build(SLUG, "test-pack", only="tp-T1-frame", templates=P.load_templates(root))[0]
    assert after.template.sha != before.template.sha and after.prompt_sha != before.prompt_sha


def test_part_set_with_voice_and_warnings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GENERATION_PROFILE", "manual-5s")
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
    chuy = next(i for i in voices if "¡Chuy" in i.prompt)
    assert chuy.prompt.startswith("[shouting] ¡Chuy") and chuy.extra["delivery"] == "shout"
    assert chuy.payload["voice_settings"] == {"stability": 0.3, "similarity_boost": 0.8}   # v4: лише ці два
    videos = [i for i in items if i.kind == "video"]
    assert videos and all(i.payload["resolution"] == "720p" and i.payload["duration"] == 5 for i in videos)
    assert [i.step for i in items] == sorted(i.step for i in items)
    # усі шоти ч.1 мають англійський опис; API-чисто (лінт і дані — до переписування оверлею v2)
    assert not any("англійського опису" in w or w.startswith("API:") for i in items for w in i.warnings)
    assert not any("[UA" in i.prompt for i in items if i.kind != "voice")
    monkeypatch.setattr(S, "overlay_path", lambda slug, part: tmp_path / "немає.yaml")
    bare = [i for i in P.build(SLUG, "1", ["video"], out_root=tmp_path)]
    first = [i for i in bare if i.extra["clip"]["index"] == 1]
    assert first and all(any("англійського опису" in w for w in i.warnings) for i in first)


def test_unknown_set_and_item() -> None:
    with pytest.raises(P.PromptError, match="невідомий набір"):
        P.build(SLUG, "trailer")
    with pytest.raises(P.PromptError, match="немає елемента"):
        P.build(SLUG, "test-pack", only="tp-T9")
    assert P.set_of("cast-mateo-front") == "casting" and P.set_of("tp-T1-video") == "test-pack"
    assert P.set_of("p2-5.01-frame") == "2" and P.set_of("p1-1.02-video-2") == "1"


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
        lab_mod.require_golden(P.load_templates()["video.i2v"])      # не тестували — автоматика не бере
    assert "golden" in lab_mod.approve(SLUG, "video.i2v", force=True)


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
    assert "кроки: 6 Відео (кліпи):" in r.output and "попередження: API 0 · lint" in r.output
    r = runner.invoke(app, ["prompts", SLUG, "test-pack", "--kind", "sound"])
    assert r.exit_code == 1
    r = runner.invoke(app, ["lab", "log", "tp-T2-video", "--tool", "dreamina", "--score", "4", "--notes", "скло ок"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["lab", "approve", "tp-T2-video"])
    assert r.exit_code == 0 and "golden" in r.output
    r = runner.invoke(app, ["lab", "status"])
    assert r.exit_code == 0 and "video.i2v@v3" in r.output


def test_cli_prompts_sequence(lab_dirs: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--sequence first30: пакет у prompts/out/<slug>/first30/, кастинг із замикання + шоти 1.01–1.08."""
    monkeypatch.setenv("GENERATION_PROFILE", "manual-5s")
    monkeypatch.setattr(viewer_mod.write_package, "__defaults__", (lab_dirs / "out", None))
    folder = tmp_path / "o" / SLUG / "part1"
    folder.mkdir(parents=True)
    shutil.copy(FIXTURE, folder / "script.json")
    script = Script.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    raw, _ = shotlist_mod.convert(ROOT / "series" / SLUG / "part1_shotlist.md", bible_mod.load(SLUG), 1, script)
    (folder / "shots.json").write_text(Shots.model_validate(raw).model_dump_json(), encoding="utf-8")
    runner = CliRunner()
    r = runner.invoke(app, ["prompts", SLUG, "1", "--sequence", "first30", "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    assert (lab_dirs / "out" / SLUG / "first30" / "index.html").exists()
    assert "кроки: 1 Обличчя-якорі:" in r.output and "7 Репліки (озвучка): 2" in r.output and "API 0" in r.output
    r = runner.invoke(app, ["prompts", SLUG, "2", "--sequence", "first30", "--out", str(tmp_path / "o")])
    assert r.exit_code == 1 and "з частини 1" in r.output
