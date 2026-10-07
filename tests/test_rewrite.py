"""Переписувач студії (fabrica/rewrite.py) і правки overrides.yaml (prompts.Data + shotspec): LLM — підмінений
(FAKE-бекенд або фальшивий модуль anthropic), справжні Ollama / Claude не викликаються. Дані — копія series/<slug>
і частини 1 (лише шоти first30) у тимчасовій теці; файли репо не змінюються."""

from __future__ import annotations

import json
import shutil
import sys
import types
from pathlib import Path

import pytest
import yaml

from fabrica import bible as bible_mod
from fabrica import config
from fabrica import lessons as lessons_mod
from fabrica import prompts as P
from fabrica import rewrite as R
from fabrica import shotspec as S

SLUG = "la-garganta"
ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "output" / SLUG / "part1" / "shots.json"


def make_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """series/<slug> → tmp (bible.yaml читається з репо — лише читання); shots.json частини 1 — лише шоти first30,
    оверлей — лише вони ж (збірка швидка). Журнал, golden, прогрес, пропозиції — теж у tmp."""
    if not SHOTS.exists():
        pytest.skip("немає output/la-garganta/part1/shots.json — `fabrica shotlist la-garganta 1`")
    from fabrica import lab as lab_mod
    from fabrica import progress as progress_mod

    series = tmp_path / "series"
    shutil.copytree(ROOT / "series" / SLUG, series / SLUG)
    keep = P.sequences(SLUG)["first30"]["shots"]
    shots = json.loads(SHOTS.read_text(encoding="utf-8-sig"))
    shots["shots"] = [s for s in shots["shots"] if s["id"] in keep]
    scenes = {s["scene_id"] for s in shots["shots"]}
    out = tmp_path / "output" / SLUG / "part1"
    out.mkdir(parents=True)
    (out / "shots.json").write_text(json.dumps(shots, ensure_ascii=False), encoding="utf-8")
    ov_path = series / SLUG / "part1_prompts_en.yaml"
    raw = yaml.safe_load(ov_path.read_text(encoding="utf-8-sig")) or {}
    if "version" in raw:
        raw["shots"] = {k: v for k, v in (raw.get("shots") or {}).items() if str(k) in keep}
        for line in ((raw["shots"].get("1.02") or {}).get("lines") or {}).values():
            line["voice"] = "elevenlabs"    # у ч.1 це рідний звук Seedance; тут — репліка ElevenLabs для тестів редагування
        raw["scenes"] = {k: v for k, v in (raw.get("scenes") or {}).items()
                         if any(str(k) in S._scene_aliases(sc) for sc in scenes)}
    else:
        raw = {k: v for k, v in raw.items() if str(k) in keep}
    ov_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    monkeypatch.setattr(bible_mod, "SERIES", series)
    monkeypatch.setattr(P, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(P, "OUT", tmp_path / "prompts_out")
    monkeypatch.setattr(lab_mod, "RESULTS", tmp_path / "lab" / "results.yaml")
    monkeypatch.setattr(lab_mod, "MEDIA", tmp_path / "media" / "lab")
    monkeypatch.setattr(lab_mod, "GOLDEN", tmp_path / "golden.yaml")
    monkeypatch.setattr(progress_mod, "PROGRESS", tmp_path / "lab" / "progress.yaml")
    monkeypatch.setattr(R, "PROPOSALS", tmp_path / "tmp" / "studio_proposals.json")
    monkeypatch.setattr(R, "_MEM", {})
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("GENERATION_PROFILE", raising=False)
    lessons_mod._CACHE.clear()
    return series / SLUG


@pytest.fixture
def story(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return make_copy(tmp_path, monkeypatch)


class Fake:
    """FAKE-бекенд: запам'ятовує, що отримав, і повертає заготовлену відповідь."""

    def __init__(self, answer: dict) -> None:
        self.answer, self.calls = answer, []

    def __call__(self, prompt: str, schema: dict, system: str) -> dict:
        self.calls.append({"prompt": prompt, "schema": schema, "system": system})
        return self.answer


ACTION = "The woman with curly bangs slowly lifts her bottle toward the lens and laughs; the other two nod sharply."
RULE = "Every flashlight beam stays steady and slow; the light never flickers."


def fake(monkeypatch: pytest.MonkeyPatch, answer: dict) -> Fake:
    f = Fake(answer)
    monkeypatch.setitem(R.BACKENDS, "fake", f)
    monkeypatch.setenv("REWRITE_BACKEND", "fake")
    return f


def video_answer(**kw) -> dict:
    return {"changes": [{"field": "action", "value": ACTION}],
            "lesson": {"problem": "ліхтарі мерехтять", "rule": RULE, "scope": {"kind": "video", "route": None,
                                                                             "tags": ["vhs", "nonsense"]}}} | kw


# ---------------------------------------------------------------- overrides.yaml у збірці


def test_overrides_merge_into_shot_and_prompt_en(story: Path) -> None:
    before = {i.id: i for i in P.build(SLUG, "1")}
    (story / "lab" / "overrides.yaml").write_text(yaml.safe_dump({
        "shots": {"p1-1.03": {"action": ACTION}, "1.04": {"notes": ["з усіх частин"]}, "p2-1.03": {"action": "інша"}},
        "prompt_en": {"members": {"lupita": {"wardrobe": "a red raincoat over a grey hoodie"}}}},
        allow_unicode=True), encoding="utf-8")
    after = {i.id: i for i in P.build(SLUG, "1")}
    assert ACTION in after["p1-1.03-video"].prompt and ACTION not in before["p1-1.03-video"].prompt
    assert after["p1-1.03-video"].prompt_sha != before["p1-1.03-video"].prompt_sha
    assert after["p1-1.04-video"].prompt == before["p1-1.04-video"].prompt          # інші шоти не зачеплено
    cast = {i.id: i for i in P.build(SLUG, "casting")}
    assert "red raincoat" in cast["cast-lupita-1994"].prompt


def test_overrides_field_replace_and_lines_merge() -> None:
    base = {"camera": {"move": "push_in", "speed": "slow"}, "lines": {1: {"delivery": "shout"}, 2: {"on_screen": True}}}
    out = P.merge_fields(base, {"camera": {"text": "static"}, "lines": {"2": {"delivery": "whisper"}}})
    assert out["camera"] == {"text": "static"}                                      # поле цілком, не злиття
    assert out["lines"] == {1: {"delivery": "shout"}, 2: {"on_screen": True, "delivery": "whisper"}}
    merged = P.merge_overrides({"prompt_en": {"characters": {"m": {"dna": ["a"], "tag": "t"}}}},
                               {"prompt_en": {"characters": {"m": {"dna": ["b"]}}}, "shots": {"1.02": {"frame": "f"}}})
    assert merged["prompt_en"] == {"characters": {"m": {"dna": ["b"], "tag": "t"}}}
    assert merged["shots"] == {"1.02": {"frame": "f"}} and merged["scenes"] == {}


def test_overrides_bad_shape_is_clear(story: Path) -> None:
    (story / "lab" / "overrides.yaml").write_text("shots: [1, 2]\n", encoding="utf-8")
    with pytest.raises(P.PromptError, match="overrides.yaml"):
        P.Data(SLUG)


def test_override_spec_error_names_overrides(story: Path) -> None:
    (story / "lab" / "overrides.yaml").write_text(yaml.safe_dump({"shots": {"p1-1.02": {"bogus": 1}}}),
                                                  encoding="utf-8")
    with pytest.raises(S.SpecError, match=r"overrides\.yaml · шот 1\.02"):
        P.build(SLUG, "1")


def test_unknown_part_key_is_error(story: Path) -> None:
    (story / "lab" / "overrides.yaml").write_text(yaml.safe_dump({"shots": {"p1-9.99": {"action": "x"}}}),
                                                  encoding="utf-8")
    with pytest.raises(S.SpecError, match="9.99"):
        P.build(SLUG, "1")


def test_pending_overrides_only_inside_context(story: Path) -> None:
    with P.pending_overrides(SLUG, {"shots": {"p1-1.03": {"action": ACTION}}}):
        inside = next(i for i in P.build(SLUG, "1") if i.id == "p1-1.03-video")
    outside = next(i for i in P.build(SLUG, "1") if i.id == "p1-1.03-video")
    assert ACTION in inside.prompt and ACTION not in outside.prompt


# ---------------------------------------------------------------- propose / apply


def test_propose_video_compiles_in_memory(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = fake(monkeypatch, video_answer())
    ov_before = (story / "lab" / "overrides.yaml").read_bytes()
    p = R.propose(SLUG, "p1-1.03-video", "ліхтарі мерехтять, а дія надто різка")
    call = f.calls[0]
    assert "ліхтарі мерехтять" in call["prompt"] and "CURRENT PROMPT" in call["prompt"]
    assert "Seedance" in call["system"] and "<!--" not in call["system"]          # правила, без коментаря-шапки
    assert call["schema"]["properties"]["changes"]["items"]["properties"]["field"]["enum"] == list(R.SHOT_FIELDS)
    assert p["id"].startswith("rw-") and p["backend"] == "fake" and p["item"] == "p1-1.03-video"
    ch = p["changes"][0]
    assert (ch["target"], ch["key"], ch["field"], ch["new"], ch["part"]) == ("overlay", "1.03", "action", ACTION, 1)
    assert ch["old"] and ch["old"] != ACTION
    assert ACTION in p["prompt_new"] and ACTION not in p["prompt_old"]
    assert RULE in p["prompt_new"]                                                  # урок «на пробу» вже в промпті
    assert p["lesson"]["scope"] == {"kind": "video", "tags": ["vhs"]}               # невідомі мітки відкинуто
    assert isinstance(p["warnings_new"], list)
    assert (story / "lab" / "overrides.yaml").read_bytes() == ov_before            # нічого не записано
    assert yaml.safe_load((story / "lab" / "lessons.yaml").read_text(encoding="utf-8"))["lessons"] == []
    assert R.get(p["id"])["_patch"] == {"shots": {"p1-1.03": {"action": ACTION}}}
    assert "_patch" not in R.public(p)


def test_apply_writes_overrides_and_lesson(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer())
    p = R.propose(SLUG, "p1-1.03-video", "ліхтарі мерехтять")
    res = R.apply(SLUG, p["id"], save_lesson=True, rule="The flashlight beams move slowly and steadily.")
    assert res == {"item": "p1-1.03-video", "lesson": "L1"}
    text = (story / "lab" / "overrides.yaml").read_text(encoding="utf-8")
    assert text.startswith("# Правки промптів через студію")                     # шапку збережено
    assert yaml.safe_load(text)["shots"]["p1-1.03"]["action"] == ACTION
    rows = lessons_mod.all(SLUG)
    assert [r["id"] for r in rows] == ["L1"] and rows[0]["rule"] == "The flashlight beams move slowly and steadily."
    assert rows[0]["scope"] == {"kind": "video", "tags": ["vhs"]} and rows[0]["item"] == "p1-1.03-video"
    item = next(i for i in P.build(SLUG, "1") if i.id == "p1-1.03-video")
    assert ACTION in item.prompt and "L1" in item.extra["lessons"]
    with pytest.raises(R.RewriteError, match="уже записано"):
        R.apply(SLUG, p["id"])


def test_apply_without_lesson(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer())
    p = R.propose(SLUG, "p1-1.03-video", "дія надто різка")
    assert R.apply(SLUG, p["id"], save_lesson=False)["lesson"] is None
    assert lessons_mod.all(SLUG) == []


def test_unknown_field_rejected(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer(changes=[{"field": "tier", "value": "hero"}]))
    with pytest.raises(R.RewriteError, match="невідоме поле «tier»"):
        R.propose(SLUG, "p1-1.03-video", "зроби героєм")


def test_broken_value_returns_error_without_write(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer(changes=[{"field": "people", "value": '[{"id": "nobody"}]'}]))
    with pytest.raises(R.RewriteError, match="ламає дані"):
        R.propose(SLUG, "p1-1.03-video", "додай людину")
    assert yaml.safe_load((story / "lab" / "overrides.yaml").read_text(encoding="utf-8"))["shots"] == {}


def test_type_mismatch_rejected(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer(changes=[{"field": "frame", "value": 5}]))
    with pytest.raises(R.RewriteError, match="текст"):
        R.propose(SLUG, "p1-1.03-frame", "кадр")


def test_casting_rewrites_prompt_en(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = fake(monkeypatch, {"changes": [{"field": "wardrobe", "value": "a red raincoat over a grey hoodie"}],
                           "lesson": {"problem": "одяг", "rule": "", "scope": {"kind": "image", "route": None, "tags": []}}})
    p = R.propose(SLUG, "cast-lupita-1994", "одяг не той")
    assert "wardrobe" in f.calls[0]["schema"]["properties"]["changes"]["items"]["properties"]["field"]["enum"]
    assert p["changes"][0]["target"] == "prompt_en" and "red raincoat" in p["prompt_new"]
    R.apply(SLUG, p["id"])
    raw = yaml.safe_load((story / "lab" / "overrides.yaml").read_text(encoding="utf-8"))
    assert raw["prompt_en"] == {"members": {"lupita": {"wardrobe": "a red raincoat over a grey hoodie"}}}
    assert lessons_mod.all(SLUG) == []                                           # урок без rule не пишемо


def test_line_delivery(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    item = next(i for i in P.build(SLUG, "1") if i.id == "p1-1.02-voice1")
    new = "whisper" if item.extra["delivery"] != "whisper" else "normal"
    fake(monkeypatch, {"changes": [{"field": "delivery", "value": new}],
                       "lesson": {"problem": "", "rule": "", "scope": {"kind": "voice", "route": None, "tags": []}}})
    p = R.propose(SLUG, "p1-1.02-voice1", "тихіше")
    assert p["changes"][0] | {"old": None} == {"target": "line", "key": "1.02", "field": "delivery", "old": None,
                                               "new": new, "part": 1, "n": 1}
    assert p["prompt_new"] != p["prompt_old"]
    R.apply(SLUG, p["id"])
    raw = yaml.safe_load((story / "lab" / "overrides.yaml").read_text(encoding="utf-8"))
    assert raw["shots"]["p1-1.02"]["lines"] == {1: {"delivery": new}}
    again = next(i for i in P.build(SLUG, "1") if i.id == "p1-1.02-voice1")
    assert again.extra["delivery"] == new
    assert R.source_of(SLUG, again)["overridden"] == ["delivery"]
    assert "overridden" not in R.source_of(SLUG, next(i for i in P.build(SLUG, "1") if i.id == "p1-1.04-video"))


def test_bad_delivery_rejected(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, {"changes": [{"field": "delivery", "value": "sing"}], "lesson": {}})
    with pytest.raises(R.RewriteError, match="delivery"):
        R.propose(SLUG, "p1-1.02-voice1", "заспівай")


def test_test_pack_not_rewritten(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer())
    item = P.build(SLUG, "test-pack")[0]
    with pytest.raises(R.RewriteError, match="тест-пак"):
        R.propose(SLUG, item.id, "щось")


def test_empty_feedback_and_unknown_backend(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(R.RewriteError, match="порожнє"):
        R.propose(SLUG, "p1-1.03-video", "  ")
    monkeypatch.setenv("REWRITE_BACKEND", "nope")
    with pytest.raises(R.RewriteError, match="nope"):
        R.propose(SLUG, "p1-1.03-video", "щось")


def test_backend_failure_is_one_line(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fabrica import local_llm

    def boom(prompt, schema, system):
        raise local_llm.OllamaNotRunningError("Ollama не запущена")

    monkeypatch.setitem(R.BACKENDS, "fake", boom)
    monkeypatch.setenv("REWRITE_BACKEND", "fake")
    with pytest.raises(R.RewriteError, match="бекенд fake: Ollama не запущена"):
        R.propose(SLUG, "p1-1.03-video", "щось")


def test_proposals_survive_restart(story: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake(monkeypatch, video_answer())
    p = R.propose(SLUG, "p1-1.03-video", "щось")
    monkeypatch.setattr(R, "_MEM", {})                                           # «перезапуск» студії
    assert R.get(p["id"])["prompt_new"] == p["prompt_new"]
    with pytest.raises(R.RewriteError, match="немає"):
        R.get("rw-missing")


# ---------------------------------------------------------------- бекенди


def test_strict_schema_adds_additional_properties() -> None:
    s = R.strict_schema(R.schema_for(["action"], ("video",), "r", ["mode:i2v"]))
    assert s["additionalProperties"] is False
    assert s["properties"]["lesson"]["properties"]["scope"]["additionalProperties"] is False
    assert s["properties"]["changes"]["items"]["additionalProperties"] is False


class _Resp:
    def __init__(self, stop: str, text: str) -> None:
        self.stop_reason = stop
        self.content = [types.SimpleNamespace(type="thinking", thinking=""), types.SimpleNamespace(type="text", text=text)]


def _anthropic(monkeypatch: pytest.MonkeyPatch, resp: _Resp) -> list[dict]:
    """Фальшивий модуль anthropic: ловить аргументи виклику, мережі немає."""
    calls: list[dict] = []
    mod = types.ModuleType("anthropic")

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        status_code = 500

    class Anthropic:
        def __init__(self, api_key: str) -> None:
            calls.append({"api_key": api_key})
            self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(create=self._create))

        @staticmethod
        def _create(**kw):
            calls.append(kw)
            return resp

    mod.Anthropic, mod.APIConnectionError, mod.APIStatusError = Anthropic, APIConnectionError, APIStatusError
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return calls


def test_claude_backend_call_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    calls = _anthropic(monkeypatch, _Resp("end_turn", '{"changes": [], "lesson": {"rule": "x"}}'))
    out = R._claude("PROMPT", {"type": "object", "properties": {}}, "SYSTEM")
    assert out == {"changes": [], "lesson": {"rule": "x"}}
    kw = calls[1]
    assert calls[0]["api_key"] == "sk-test-secret"
    assert kw["model"] == "claude-opus-5-5" and kw["max_tokens"] == 16000
    assert kw["betas"] == ["server-side-fallback-2026-07-01"] and kw["fallbacks"] == "default"
    assert kw["output_config"]["effort"] == "medium"
    assert kw["output_config"]["format"] == {"type": "json_schema",
                                             "schema": {"type": "object", "properties": {},
                                                        "additionalProperties": False}}
    assert kw["system"] == "SYSTEM" and kw["messages"] == [{"role": "user", "content": "PROMPT"}]


def test_claude_refusal_and_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-secret")
    _anthropic(monkeypatch, _Resp("refusal", ""))
    with pytest.raises(R.RewriteError, match="відмовився") as e:
        R._claude("p", {"type": "object"}, "s")
    assert "sk-test-secret" not in str(e.value)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(R.RewriteError, match="ANTHROPIC_API_KEY"):
        R._claude("p", {"type": "object"}, "s")


def test_claude_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)                          # import → ImportError
    with pytest.raises(R.RewriteError, match="uv sync --extra claude"):
        R._claude("p", {"type": "object"}, "s")
    monkeypatch.setenv("REWRITE_BACKEND", "claude")
    assert R.backend_status() == {"name": "claude", "model": "claude-opus-5-5", "ok": False,
                                  "note": "не встановлено: uv sync --extra claude"}


def test_ollama_backend_uses_generate_json(monkeypatch: pytest.MonkeyPatch) -> None:
    from fabrica import local_llm

    seen = {}

    def gen(prompt, schema, system=None, temperature=0.8, max_tokens=2000):
        seen.update(prompt=prompt, schema=schema, system=system)
        return {"changes": [], "lesson": {}}

    monkeypatch.setattr(local_llm, "generate_json", gen)
    assert R._ollama("P", {"type": "object"}, "S") == {"changes": [], "lesson": {}}
    assert seen == {"prompt": "P", "schema": {"type": "object"}, "system": "S"}


def test_ollama_status_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fabrica import local_llm

    monkeypatch.setenv("FABRICA_ENV_FILE", str(tmp_path / "none.env"))
    monkeypatch.delenv("REWRITE_BACKEND", raising=False)
    monkeypatch.setattr(local_llm, "settings", lambda: ("http://localhost:11434", "m:9b"))
    monkeypatch.setattr(R, "_STATUS", {})
    n = []
    monkeypatch.setattr(local_llm, "available_models", lambda: n.append(1) or ["m:9b"])
    assert R.backend_status() == {"name": "ollama", "model": "m:9b", "ok": True, "note": ""}
    R.backend_status()
    assert len(n) == 1


def test_rules_file_is_compact() -> None:
    text = R.rules_text()
    assert 40 <= len(text.splitlines()) <= 90 and "No BGM" in text and "age words" in text
    assert config.ROOT / "prompts" / "rewrite_rules.md" == R.RULES
