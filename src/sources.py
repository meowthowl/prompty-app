"""Получение свежих новостей из RSS-источников."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import feedparser


@dataclass
class NewsItem:
    title: str
    link: str
    summary: str

    @property
    def key(self) -> str:
        return hashlib.sha1(self.link.encode("utf-8")).hexdigest()


def fetch_news(feed_urls: list[str], limit_per_feed: int = 10) -> list[NewsItem]:
    """Тянет последние записи из списка RSS-фидов. Ошибки отдельных
    фидов не должны валить весь пайплайн."""
    items: list[NewsItem] = []
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for entry in parsed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "").strip()
            if title and link:
                items.append(NewsItem(title=title, link=link, summary=summary))
    return items


def pick_fresh_news(feed_urls: list[str], is_used_fn) -> NewsItem | None:
    """Возвращает первую новость, которая ещё не была опубликована."""
    for item in fetch_news(feed_urls):
        if not is_used_fn(item.key):
            return item
    return None
