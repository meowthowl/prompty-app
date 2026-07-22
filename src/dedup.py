"""Хранение уже использованных элементов (ссылок, инструментов, тем),
чтобы не публиковать одно и то же дважды. У каждого профиля канала — свой
файл истории, иначе дедупликация одной ниши мешала бы другой.

Файл data/used_items[_<профиль>].json коммитится обратно в репозиторий из
GitHub Actions, поэтому состояние переживает перезапуск раннера.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import DEFAULT_PROFILE, Settings

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _data_file(settings: Settings) -> Path:
    # У профиля по умолчанию имя файла остаётся прежним — чтобы не терять
    # уже накопленную историю публикаций Prompty.
    if settings.profile == DEFAULT_PROFILE:
        return DATA_DIR / "used_items.json"
    return DATA_DIR / f"used_items_{settings.profile}.json"


def _load(settings: Settings) -> dict:
    path = _data_file(settings)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(settings: Settings, data: dict) -> None:
    path = _data_file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_used(settings: Settings, category: str, key: str) -> bool:
    data = _load(settings)
    return key in data.get(category, [])


def mark_used(settings: Settings, category: str, key: str, keep_last: int = 500) -> None:
    data = _load(settings)
    items = data.setdefault(category, [])
    if key not in items:
        items.append(key)
    data[category] = items[-keep_last:]
    _save(settings, data)


def pick_unused(settings: Settings, category: str, candidates: list[str]) -> str | None:
    """Возвращает первый неиспользованный элемент из списка (по кругу)."""
    data = _load(settings)
    used = set(data.get(category, []))
    for item in candidates:
        if item not in used:
            return item
    # все уже использованы — начинаем цикл заново
    return candidates[0] if candidates else None
