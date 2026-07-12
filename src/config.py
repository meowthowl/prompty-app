"""Загрузка конфигурации из .env и config.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    telegram_channel_id_en: str | None
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


def load_settings() -> Settings:
    with open(ROOT_DIR / "config.yaml", "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return Settings(
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_channel_id=_require_env("TELEGRAM_CHANNEL_ID"),
        # Английский канал опционален — если не задан, посты дублируются
        # только на основной (русский) канал.
        telegram_channel_id_en=os.getenv("TELEGRAM_CHANNEL_ID_EN") or None,
        gemini_api_key=_require_env("GEMINI_API_KEY"),
        # os.getenv(name) or default — а не os.getenv(name, default): в GitHub
        # Actions незаданный secret подставляется как пустая строка, а не
        # отсутствует вовсе, поэтому обычный default-параметр не сработал бы.
        gemini_model=os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite",
        # Генерация картинок через Cloudflare Workers AI (FLUX.1 schnell) —
        # опционально. Без токена пост просто выходит без картинки (текстом).
        cloudflare_account_id=os.getenv("CLOUDFLARE_ACCOUNT_ID") or None,
        cloudflare_api_token=os.getenv("CLOUDFLARE_API_TOKEN") or None,
        raw=raw,
    )
