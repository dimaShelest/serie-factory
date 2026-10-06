"""Тести fabrica/local_llm.py.

Офлайн (завжди): .env, вирізання <think>, тіло запиту, помилки, повтори битого JSON — на підмінах.
Наживо (лише якщо Ollama запущена й модель є, інакше skip): простий запит і JSON за схемою + швидкість.
Звіт швидкості:  uv run pytest tests/test_local_llm.py -s
"""

from __future__ import annotations

import io
import json
import socket
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fabrica import local_llm  # noqa: E402
from fabrica.local_llm import (  # noqa: E402
    InvalidJSONError,
    ModelNotFoundError,
    OllamaNotRunningError,
    generate,
    generate_json,
)

SCHEMA = {
    "type": "object",
    "properties": {"ciudad": {"type": "string"}, "datos": {"type": "array", "items": {"type": "string"}}},
    "required": ["ciudad", "datos"],
}


def answer(content: str, done_reason: str = "stop") -> dict:
    """Відповідь /api/chat у форматі Ollama."""
    return {
        "model": "test:1b", "message": {"role": "assistant", "content": content}, "done": True,
        "done_reason": done_reason, "prompt_eval_count": 10, "eval_count": 40,
        "eval_duration": 2_000_000_000, "load_duration": 0,
    }


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Чисте оточення: без OLLAMA_* і з порожнім тимчасовим .env замість справжнього."""
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setattr(local_llm, "ENV_FILE", tmp_path / ".env")
    return tmp_path / ".env"


@pytest.fixture
def ollama(env: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Підміна urlopen: віддає заготовлені відповіді по черзі й запам'ятовує тіла запитів."""
    fake = SimpleNamespace(sent=[], answers=[])

    def urlopen(req, timeout):
        fake.sent.append(json.loads(req.data))
        item = fake.answers.pop(0)
        if isinstance(item, Exception):
            raise item
        return io.BytesIO(json.dumps(item).encode("utf-8"))

    monkeypatch.setattr(local_llm.urllib.request, "urlopen", urlopen)
    return fake


# ---------------------------------------------------------------- налаштування


def test_settings_defaults(env: Path):
    assert local_llm.settings() == ("http://localhost:11434", "huihui_ai/qwen3.5-abliterated:9b")


def test_settings_from_env_file_with_bom(env: Path):
    env.write_text(
        "﻿# коментар\nANTHROPIC_API_KEY=секрет\nOLLAMA_URL=http://192.168.1.5:11434/\n"
        'export OLLAMA_MODEL="qwen3:8b"\n',
        encoding="utf-8",
    )
    assert local_llm.settings() == ("http://192.168.1.5:11434", "qwen3:8b")
    assert "ANTHROPIC_API_KEY" not in local_llm._read_env_file()   # чужі ключі не читаємо


def test_environment_beats_env_file(env: Path, monkeypatch: pytest.MonkeyPatch):
    env.write_text("OLLAMA_MODEL=from-file\n", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_MODEL", "from-env")
    assert local_llm.settings()[1] == "from-env"


# ---------------------------------------------------------------- <think>


@pytest.mark.parametrize("raw, clean", [
    ("¡Hola!", "¡Hola!"),
    ("<think>hmm</think>\n¡Hola!", "¡Hola!"),
    ("<think>a</think>Uno <think>b\nc</think>dos", "Uno dos"),
    ("думки без відкривального тегу</think>\n¡Hola!", "¡Hola!"),
    ("¡Hola! <think>обрізано на max_tokens", "¡Hola!"),
    ("<think>лише думки, обрізано", ""),
])
def test_strip_think(raw: str, clean: str):
    assert local_llm.strip_think(raw) == clean


# ---------------------------------------------------------------- generate


def test_request_body(ollama: SimpleNamespace):
    ollama.answers.append(answer("<think>я думаю</think>\n¡Hola!"))
    assert generate("Saluda", system="Eres amable.", temperature=0.3, max_tokens=50) == "¡Hola!"
    body = ollama.sent[0]
    assert body["model"] == "huihui_ai/qwen3.5-abliterated:9b"
    assert body["stream"] is False and body["think"] is False
    assert body["keep_alive"] == "30m"
    assert body["options"] == {"num_ctx": 8192, "temperature": 0.3, "num_predict": 50}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "format" not in body


def test_reply_speed(ollama: SimpleNamespace):
    ollama.answers.append(answer("x"))
    assert local_llm.chat([{"role": "user", "content": "x"}]).tokens_per_sec == 20.0   # 40 токенів / 2 с


def test_model_not_found(ollama: SimpleNamespace):
    body = io.BytesIO(b'{"error":"model \'nope:1b\' not found"}')
    ollama.answers.append(urllib.error.HTTPError("http://x/api/chat", 404, "Not Found", {}, body))
    with pytest.raises(ModelNotFoundError, match=r"ollama pull huihui_ai/qwen3\.5-abliterated:9b"):
        generate("hola")


def test_ollama_not_running(env: Path, monkeypatch: pytest.MonkeyPatch):
    with socket.socket() as s:      # вільний порт, на якому точно ніхто не слухає
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setenv("OLLAMA_URL", f"http://127.0.0.1:{port}")
    with pytest.raises(OllamaNotRunningError, match="ollama serve"):
        generate("hola")


# ---------------------------------------------------------------- generate_json


def test_generate_json_first_try(ollama: SimpleNamespace):
    ollama.answers.append(answer('{"ciudad": "Puebla", "datos": ["a"]}'))
    assert generate_json("Datos de Puebla", SCHEMA) == {"ciudad": "Puebla", "datos": ["a"]}
    assert ollama.sent[0]["format"] == SCHEMA
    assert '"required"' in ollama.sent[0]["messages"][-1]["content"]   # схема є і в промпті


def test_generate_json_retries_broken(ollama: SimpleNamespace):
    ollama.answers += [answer('{"ciudad": "Pue'), answer('{"ciudad": "Puebla"}'),
                       answer('{"ciudad": "Puebla", "datos": []}')]
    assert generate_json("Datos de Puebla", SCHEMA) == {"ciudad": "Puebla", "datos": []}
    assert len(ollama.sent) == 3


def test_generate_json_gives_up(ollama: SimpleNamespace):
    ollama.answers += [answer('{"ciudad": "Pue')] * 3
    with pytest.raises(InvalidJSONError, match="3 рази"):
        generate_json("Datos de Puebla", SCHEMA)
    assert len(ollama.sent) == 3


def test_generate_json_truncated_no_retries(ollama: SimpleNamespace):
    """Обрізано на max_tokens — повтор з тим самим лімітом знову обріжеться, тож одразу помилка."""
    ollama.answers += [answer('{"ciudad": "Pue', done_reason="length")] * 3
    with pytest.raises(InvalidJSONError, match="max_tokens=100"):
        generate_json("Datos de Puebla", SCHEMA, max_tokens=100)
    assert len(ollama.sent) == 1


def test_connection_drop_is_local_llm_error(ollama: SimpleNamespace):
    import http.client
    ollama.answers.append(http.client.RemoteDisconnected("Remote end closed connection"))
    with pytest.raises(local_llm.LocalLLMError, match="обірвалось"):
        generate("hola")


def test_tags_probe_uses_short_timeout(env: Path, monkeypatch: pytest.MonkeyPatch):
    """Недосяжний OLLAMA_URL не має гальмувати збирання тестів на 600 с."""
    seen = []

    def urlopen(req, timeout):
        seen.append(timeout)
        return io.BytesIO(b'{"models": [{"name": "m:1b"}]}')

    monkeypatch.setattr(local_llm.urllib.request, "urlopen", urlopen)
    assert local_llm.available_models() == ["m:1b"]
    assert seen == [local_llm.TAGS_TIMEOUT_S]


# ---------------------------------------------------------------- наживо


def _live_skip_reason() -> str:
    try:
        models = local_llm.available_models()
    except local_llm.LocalLLMError as e:
        return str(e).splitlines()[0]
    model = local_llm.settings()[1]
    return "" if model in models else f"модель {model} не завантажена (ollama pull {model})"


LIVE_SKIP = _live_skip_reason()
live = pytest.mark.skipif(bool(LIVE_SKIP), reason=f"наживо: {LIVE_SKIP}")


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[local_llm.Reply]:
    """Збирає Reply кожного виклику chat(), щоб показати токени/с."""
    seen: list[local_llm.Reply] = []
    real_chat = local_llm.chat

    def spy(*args, **kwargs):
        seen.append(real_chat(*args, **kwargs))
        return seen[-1]

    monkeypatch.setattr(local_llm, "chat", spy)
    return seen


def report(title: str, result: object, replies: list[local_llm.Reply]) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tokens = sum(r.tokens for r in replies)
    seconds = sum(r.seconds for r in replies)
    print(f"\n--- {title} · {replies[-1].model}")
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2))
    print(f"--- запитів: {len(replies)} · промпт: {sum(r.prompt_tokens for r in replies)} ток · "
          f"відповідь: {tokens} ток за {seconds:.1f} с = {tokens / seconds if seconds else 0:.1f} ток/с · "
          f"завантаження моделі: {sum(r.load_seconds for r in replies):.1f} с")


@live
def test_live_simple(replies: list[local_llm.Reply]):
    text = generate("¿Cuál es la capital de México? Responde en una frase corta.", temperature=0.2)
    report("простий запит", text, replies)
    assert "méxico" in text.lower() and "<think>" not in text


@live
def test_live_json(replies: list[local_llm.Reply]):
    data = generate_json(
        "Dame tres datos curiosos y breves sobre Guadalajara, México.",
        SCHEMA,
        system="Eres un asistente que responde en español.",
        temperature=0.4,
    )
    report("JSON за схемою", data, replies)
    assert isinstance(data["ciudad"], str) and data["datos"]
    assert all(isinstance(d, str) for d in data["datos"])
