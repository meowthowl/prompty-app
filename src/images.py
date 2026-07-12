"""Генерация обложки для поста через Pollinations.ai (бесплатно, без ключа)."""
from __future__ import annotations

from urllib.parse import quote

import requests

_BASE_URL = "https://image.pollinations.ai/prompt/{prompt}"


def generate_image(prompt: str, width: int = 1024, height: int = 576) -> bytes | None:
    """Возвращает байты картинки или None, если сервис недоступен —
    в этом случае пост публикуется без изображения."""
    url = _BASE_URL.format(prompt=quote(prompt)) + f"?width={width}&height={height}&nologo=true"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.RequestException:
        return None
