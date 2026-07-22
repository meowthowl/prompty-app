"""Минимальный клиент Telegram Bot API — без тяжёлых зависимостей,
только прямые HTTP-запросы (requests). Публикует в канал текущего профиля
(settings.telegram_channel_id)."""
from __future__ import annotations

import json

import requests

from .config import Settings

_API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _call(settings: Settings, method: str, data: dict | None = None, files: dict | None = None) -> dict:
    url = _API_BASE.format(token=settings.telegram_bot_token, method=method)
    response = requests.post(url, data=data, files=files, timeout=30)
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Ошибка Telegram API ({method}): {payload}")
    return payload["result"]


def send_message(settings: Settings, text: str) -> dict:
    return _call(
        settings,
        "sendMessage",
        data={
            "chat_id": settings.telegram_channel_id,
            "text": text,
            "disable_web_page_preview": True,
        },
    )


def send_photo(settings: Settings, image_bytes: bytes, caption: str) -> dict:
    return _call(
        settings,
        "sendPhoto",
        data={
            "chat_id": settings.telegram_channel_id,
            "caption": caption,
        },
        files={"photo": ("cover.jpg", image_bytes)},
    )


def send_poll(settings: Settings, question: str, options: list[str]) -> dict:
    return _call(
        settings,
        "sendPoll",
        data={
            "chat_id": settings.telegram_channel_id,
            "question": question,
            "options": json.dumps(options, ensure_ascii=False),
            "is_anonymous": True,
        },
    )


def post_text_or_photo(settings: Settings, text: str, image_bytes: bytes | None) -> dict:
    """Публикует пост: с картинкой, если она есть и подпись укладывается
    в лимит caption (1024 символа), иначе как обычный текст."""
    if image_bytes and len(text) <= 1024:
        return send_photo(settings, image_bytes, text)
    return send_message(settings, text)
