"""Генерация обложки для поста через Cloudflare Workers AI (`flux-1-schnell`,
Black Forest Labs) — без карты, 10 000 бесплатных "нейронов"/день (~230
картинок), реально следует промпту и даёт приличное качество.

Раньше здесь был фолбэк на Pollinations.ai, но на практике их бесплатный
эндпоинт оказался сломан — он игнорирует промпт и отдаёт случайные картинки
из чужой ленты, никак не связанные с постом. Это хуже, чем отсутствие
картинки вовсе, поэтому фолбэка на него больше нет: без Cloudflare пост
просто выходит без обложки (текстом).
"""
from __future__ import annotations

import base64
import logging

import requests

from .config import Settings

log = logging.getLogger("tg-channel")

_CLOUDFLARE_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}"
    "/ai/run/@cf/black-forest-labs/flux-1-schnell"
)

# Добавляется к любому промпту, чтобы систематически уводить генерацию от
# сюрреализма/абстракции/случайных роботов в сторону чистой предметной
# иллюстрации, независимо от того, что попросила модель текста.
_STYLE_SUFFIX = (
    ", clean flat editorial illustration style, realistic proportions, "
    "muted professional color palette, no surreal distortion, no abstract "
    "art, no random humanoid robots, no text or logos in the image"
)


def _generate_via_cloudflare(settings: Settings, prompt: str) -> bytes | None:
    if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
        log.info("Cloudflare не настроен (нет CLOUDFLARE_ACCOUNT_ID/API_TOKEN) — пост выйдет без картинки")
        return None
    url = _CLOUDFLARE_URL.format(account_id=settings.cloudflare_account_id)
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
            json={"prompt": prompt + _STYLE_SUFFIX, "steps": 4},
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
        log.warning("Генерация картинки через Cloudflare не удалась — пост выйдет без картинки", exc_info=True)
        return None


def generate_image(settings: Settings, prompt: str) -> bytes | None:
    """Возвращает байты картинки или None, если Cloudflare не настроен/недоступен —
    в этом случае пост публикуется без изображения (это лучше, чем случайная
    нерелевантная картинка)."""
    return _generate_via_cloudflare(settings, prompt)
