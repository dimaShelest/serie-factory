"""Локальна LLM через Ollama: generate() -> текст, generate_json() -> валідний JSON за схемою.

Тільки stdlib, однаково працює на macOS і Windows. Налаштування — зі змінних оточення або `.env`
у корені репо (оточення важливіше):

    OLLAMA_URL    за замовчуванням http://localhost:11434
    OLLAMA_MODEL  за замовчуванням huihui_ai/qwen3.5-abliterated:9b

    from fabrica.local_llm import generate, generate_json
    text = generate("Escribe un gancho de dos frases.", system="Eres guionista de terror.")
    data = generate_json("Tres títulos para la serie.", {"type": "object", ...})

Нижчий рівень — chat(): повертає Reply з текстом і статистикою (токени, токени/с).
"""

from __future__ import annotations

import http.client
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "huihui_ai/qwen3.5-abliterated:9b"

NUM_CTX = 8192        # контекст: довгі сценарії не обрізаються (типово Ollama дає менше)
KEEP_ALIVE = "30m"    # модель не вивантажується з пам'яті між запитами
TAGS_TIMEOUT_S = 3     # перевірка «чи жива Ollama» — швидко, навіть якщо адреса недосяжна
TIMEOUT_S = 600       # перший запит ще й вантажить модель у пам'ять
JSON_RETRIES = 2      # повтори generate_json, якщо JSON битий

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class LocalLLMError(RuntimeError):
    """Помилка локальної LLM; текст пояснює, що робити."""


class OllamaNotRunningError(LocalLLMError):
    pass


class ModelNotFoundError(LocalLLMError):
    pass


class InvalidJSONError(LocalLLMError):
    pass


@dataclass
class Reply:
    text: str
    model: str
    done_reason: str      # "stop" — договорила, "length" — обрізано на max_tokens
    prompt_tokens: int
    tokens: int           # згенеровано
    seconds: float        # час генерації (без завантаження моделі й читання промпту)
    load_seconds: float   # завантаження моделі в пам'ять; ~0, коли вона вже там

    @property
    def tokens_per_sec(self) -> float:
        return self.tokens / self.seconds if self.seconds else 0.0


# ---------------------------------------------------------------- налаштування


def _read_env_file() -> dict[str, str]:
    if not ENV_FILE.is_file():
        return {}
    values = {}
    # utf-8-sig: PowerShell 5.1 пише .env з BOM
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        if key.startswith("OLLAMA_"):
            values[key] = value.strip().strip("'\"")
    return values


def settings() -> tuple[str, str]:
    """(url, model): змінна оточення -> `.env` -> значення за замовчуванням."""
    env_file = _read_env_file()

    def get(key: str, default: str) -> str:
        return os.environ.get(key) or env_file.get(key) or default

    return get("OLLAMA_URL", DEFAULT_URL).rstrip("/"), get("OLLAMA_MODEL", DEFAULT_MODEL)


# ---------------------------------------------------------------- HTTP


def _request(url: str, path: str, body: dict | None = None, model: str = "", timeout: float = TIMEOUT_S) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except (ValueError, AttributeError):
            pass
        if e.code == 404 and "not found" in detail:
            raise ModelNotFoundError(
                f"Модель «{model}» не знайдена в Ollama ({url}).\n"
                f"Завантаж її:  ollama pull {model}\n"
                "Або вкажи іншу в OLLAMA_MODEL у .env (що є локально — ollama list)."
            ) from None
        raise LocalLLMError(f"Ollama відповіла HTTP {e.code}: {detail}") from None
    except (TimeoutError, urllib.error.URLError) as e:
        reason = getattr(e, "reason", e)
        if isinstance(reason, TimeoutError):
            raise LocalLLMError(
                f"Ollama ({url}) не відповіла за {timeout:g} с. Модель завелика для цієї машини "
                "або max_tokens надто великий."
            ) from None
        raise OllamaNotRunningError(
            f"Ollama не запущена або недоступна за адресою {url} ({reason}).\n"
            "Запусти застосунок Ollama або в терміналі:  ollama serve\n"
            "Ollama на іншій машині — вкажи її адресу в OLLAMA_URL у .env."
        ) from None
    except (ConnectionError, http.client.HTTPException) as e:
        # обрив посеред довгої генерації: RemoteDisconnected, ConnectionResetError, IncompleteRead
        raise LocalLLMError(f"З'єднання з Ollama ({url}) обірвалось під час відповіді: {e!r}. "
                            "Перезапусти Ollama і повтори.") from None


def available_models() -> list[str]:
    """Моделі, завантажені в Ollama. Ollama не запущена -> OllamaNotRunningError."""
    url, _ = settings()
    return [m["name"] for m in _request(url, "/api/tags", timeout=TAGS_TIMEOUT_S).get("models", [])]


# ---------------------------------------------------------------- генерація


def strip_think(text: str) -> str:
    """Вирізає блоки <think>…</think>, навіть якщо модель «думає», хоча think вимкнено."""
    text = THINK_RE.sub("", text)
    if "</think>" in text:          # відкривальний тег з'їв шаблон чату
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text:           # блок не закрився: обрізало на max_tokens
        text = text.split("<think>", 1)[0]
    return text.strip()


def _messages(prompt: str, system: str | None) -> list[dict]:
    messages = [{"role": "system", "content": system}] if system else []
    return messages + [{"role": "user", "content": prompt}]


def chat(
    messages: list[dict],
    temperature: float = 0.8,
    max_tokens: int = 2000,
    format: dict | str | None = None,
) -> Reply:
    """Один запит до /api/chat (stream=false, think=false). format — JSON-схема або "json"."""
    url, model = settings()
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": temperature, "num_predict": max_tokens},
    }
    if format is not None:
        body["format"] = format
    data = _request(url, "/api/chat", body, model)
    return Reply(
        text=strip_think(data.get("message", {}).get("content", "")),
        model=data.get("model", model),
        done_reason=data.get("done_reason", ""),
        prompt_tokens=data.get("prompt_eval_count", 0),
        tokens=data.get("eval_count", 0),
        seconds=data.get("eval_duration", 0) / 1e9,
        load_seconds=data.get("load_duration", 0) / 1e9,
    )


def generate(
    prompt: str,
    system: str | None = None,
    temperature: float = 0.8,
    max_tokens: int = 2000,
) -> str:
    """Текст відповіді моделі без блоку <think>."""
    return chat(_messages(prompt, system), temperature, max_tokens).text


def generate_json(
    prompt: str,
    schema: dict,
    system: str | None = None,
    temperature: float = 0.8,
    max_tokens: int = 2000,
) -> Any:
    """JSON за схемою: Ollama обмежує вихід через format=schema, а ми ще й перевіряємо розбір
    і обов'язкові поля верхнього рівня. Битий JSON -> до JSON_RETRIES повторів, далі InvalidJSONError.
    """
    # Схема ще й у промпті: так модель краще заповнює поля, а не лише тримає синтаксис
    prompt = f"{prompt}\n\nВідповідай лише JSON за цією схемою:\n{json.dumps(schema, ensure_ascii=False)}"
    problem = ""
    for _ in range(1 + JSON_RETRIES):
        reply = chat(_messages(prompt, system), temperature, max_tokens, format=schema)
        try:
            data = json.loads(reply.text)
        except ValueError as e:
            problem = f"не розбирається ({e})"
        else:
            missing = [k for k in schema.get("required", []) if not isinstance(data, dict) or k not in data]
            if not missing:
                return data
            problem = f"бракує полів {missing}"
        if reply.done_reason == "length":
            # повтор з тим самим max_tokens знову обріжеться — не витрачаємо хвилини
            raise InvalidJSONError(f"Відповідь обрізано на max_tokens={max_tokens} ({problem}) — збільш max_tokens")
    raise InvalidJSONError(f"Модель {1 + JSON_RETRIES} рази повернула битий JSON: {problem}")
