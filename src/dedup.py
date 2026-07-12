"""Хранение уже использованных элементов (ссылок, инструментов, тем),
чтобы не публиковать одно и то же дважды.

Файл data/used_items.json коммитится обратно в репозиторий из
GitHub Actions, поэтому состояние переживает перезапуск раннера.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "used_items.json"


def _load() -> dict:
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_used(category: str, key: str) -> bool:
    data = _load()
    return key in data.get(category, [])


def mark_used(category: str, key: str, keep_last: int = 500) -> None:
    data = _load()
    items = data.setdefault(category, [])
    if key not in items:
        items.append(key)
    data[category] = items[-keep_last:]
    _save(data)


def pick_unused(category: str, candidates: list[str]) -> str | None:
    """Возвращает первый неиспользованный элемент из списка (по кругу)."""
    data = _load()
    used = set(data.get(category, []))
    for item in candidates:
        if item not in used:
            return item
    # все уже использованы — начинаем цикл заново
    return candidates[0] if candidates else None
