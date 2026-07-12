"""Генерация обложки для поста.

Основной вариант — Cloudflare Workers AI (`flux-1-schnell`, Black Forest
Labs): без карты, 10 000 бесплатных "нейронов"/день (~230 картинок), и
заметно лучше по качеству, чем анонимные бесплатные генераторы вроде
Pollinations.ai. Gemini image API проверялся отдельно — на бесплатном
тарифе у него нулевая квота для генерации картинок, поэтому не используется.

Если Cloudflare не настроен (нет токена) или временно недоступен —
автоматический откат на Pollinations.ai, чтобы пост в любом случае вышел
с картинкой, просто чуть более простой.
"""
from __future__ import annotations

import base64
import logging
from urllib.parse import quote

import requests

from .config import Settings

log = logging.getLogger("tg-channel")

_CLOUDFLARE_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
    "/ai/run/@cf/black-forest-labs/flux-1-schnell"
)
_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"


def _generate_via_cloudflare(settings: Settings, prompt: str) -> bytes | None:
    if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
        return None
    url = _CLOUDFLARE_URL.format(account_id=settings.cloudflare_account_id)
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
            json={"prompt": prompt, "steps": 4},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            log.warning("Cloudflare Workers AI вернул ошибку: %s", payload.get("errors"))
            return None
        image_b64 = payload["result"]["image"]
        return base64.b64decode(image_b64)
    except (requests.RequestException, KeyError, ValueError):
        log.warning("Генерация картинки через Cloudflare не удалась, пробую Pollinations", exc_info=True)
        return None


def _generate_via_pollinations(prompt: str, width: int = 1024, height: int = 576) -> bytes | None:
    url = _POLLINATIONS_URL.format(prompt=quote(prompt)) + f"?width={width}&height={height}&nologo=true"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None


def generate_image(settings: Settings, prompt: str) -> bytes | None:
    """Возвращает байты картинки или None, если оба сервиса недоступны —
    в этом случае пост публикуется без изображения."""
    image = _generate_via_cloudflare(settings, prompt)
    if image is not None:
        return image
    return _generate_via_pollinations(prompt)
