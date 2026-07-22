"""Загрузка конфигурации из .env и профиля канала (profiles/<профиль>.yaml).

Один код обслуживает несколько разных каналов/ниш одновременно — каждая
описана отдельным yaml-файлом в папке profiles/. Профиль передаётся через
--profile при запуске (по умолчанию — "prompty", исходный канал)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
PROFILES_DIR = ROOT_DIR / "profiles"
DEFAULT_PROFILE = "prompty"

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    profile: str
    telegram_bot_token: str
    telegram_channel_id: str
    gemini_api_key: str
    gemini_model: str
    cloudflare_account_id: str | None
    cloudflare_api_token: str | None
    raw: dict


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name}. "
            f"Скопируй .env.example в .env и заполни значения."
        )
    return value


def _channel_env_name(profile: str) -> str:
    """У профиля по умолчанию ('prompty') название переменной остаётся
    прежним — для обратной совместимости с уже настроенными секретами.
    У любого другого профиля — с суффиксом имени профиля в названии
    переменной, чтобы несколько каналов могли работать через один и тот же
    бот и один и тот же набор ключей Gemini/Cloudflare."""
    if profile == DEFAULT_PROFILE:
        return "TELEGRAM_CHANNEL_ID"
    return f"TELEGRAM_CHANNEL_ID_{profile.upper()}"


def load_settings(profile: str = DEFAULT_PROFILE) -> Settings:
    profile_path = PROFILES_DIR / f"{profile}.yaml"
    if not profile_path.exists():
        available = ", ".join(p.stem for p in PROFILES_DIR.glob("*.yaml"))
        raise RuntimeError(
            f"Профиль '{profile}' не найден ({profile_path}). "
            f"Доступные профили: {available}"
        )
    with open(profile_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return Settings(
        profile=profile,
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_require_env(_channel_env_name(profile)),
        gemini_api_key=_require_env("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite",
        cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID") or None,
        cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN") or None,
        raw=raw,
    )
