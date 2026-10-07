"""Налаштування з оточення й `.env` — один парсер для всієї фабрики.

Оточення має пріоритет над `.env`; порожнє значення = «не задано». Шлях до `.env` можна підмінити
змінною FABRICA_ENV_FILE (тести так ізолюються від справжнього `.env`).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLACE_TRIES = 6


class ConfigError(ValueError):
    """Налаштування задано неправильно — повідомлення пояснює, що виправити."""


def env_file() -> Path:
    return Path(os.environ.get("FABRICA_ENV_FILE") or ROOT / ".env")


def read_env(path: Path | None = None) -> dict[str, str]:
    """KEY=value з `.env`: BOM, `export KEY=…`, лапки, коментарі. UTF-16 (PowerShell 5.1 `>`) — зрозуміла помилка."""
    path = path or env_file()
    if not path.is_file():
        return {}
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in data[:400]:
        raise ConfigError(
            f"{path}: файл у UTF-16 (так пише PowerShell 5.1 через `>` / `>>`). Перезбережи як UTF-8: "
            "`(Get-Content .env) | Set-Content -Encoding utf8 .env`")
    out: dict[str, str] = {}
    for line in data.decode("utf-8-sig").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("export "):
            s = s[len("export "):].lstrip()
        key, sep, value = s.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        out[key.strip()] = value
    return out


def get(key: str, env: dict[str, str] | None = None) -> str | None:
    """Значення ключа: спершу оточення, потім `.env`. Порожньо → None."""
    value = os.environ.get(key)
    if value is None or not value.strip():
        value = (env if env is not None else read_env()).get(key)
    value = (value or "").strip()
    return value or None


def replace_atomic(tmp: Path, dest: Path) -> None:
    """tmp → dest одним кроком (os.replace). Windows: файл, який саме читає інший процес (студія в браузері,
    антивірус, OneDrive, редактор), дає PermissionError — кілька спроб з паузою, потім та сама помилка."""
    for n in range(REPLACE_TRIES):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if n == REPLACE_TRIES - 1:
                raise
            time.sleep(0.05 * (n + 1))


def automation_enabled() -> bool:
    """Режим «лабораторія промптів»: платні виклики вимкнені, доки людина явно не ввімкне AUTOMATION_ENABLED=true."""
    return (get("AUTOMATION_ENABLED") or "false").strip().lower() in {"1", "true", "yes", "on", "так"}
