"""Получение свежих новостей из RSS-источников."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser

# Новостью "дня" не может считаться то, что вышло больше этого срока назад —
# иначе при архивных/редко обновляемых фидах (например, у некоторых блогов
# в выдаче могут быть записи за много месяцев) в подборку попадают старые
# статьи только из-за того, что RSS-фид не гарантирует строгую сортировку
# "только самое новое сверху".
MAX_AGE = timedelta(days=4)


@dataclass
class NewsItem:
    title: str
    link: str
    summary: str
    published: datetime | None

    @property
    def key(self) -> str:
        return hashlib.sha1(self.link.encode("utf-8")).hexdigest()


def _parse_published(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
    return None


def fetch_news(feed_urls: list[str], limit_per_feed: int = 10) -> list[NewsItem]:
    """Тянет последние записи из списка RSS-фидов, отбрасывает всё старше
    MAX_AGE и сортирует результат от самых новых к старым — независимо от
    того, в каком порядке фиды указаны в конфиге и в каком порядке сама
    лента отдаёт записи. Ошибки отдельных фидов не должны валить весь пайплайн."""
    items: list[NewsItem] = []
    now = datetime.now(timezone.utc)
    for url in feed_urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for entry in parsed.entries[:limit_per_feed]:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "").strip()
            if not (title and link):
                continue
            published = _parse_published(entry)
            if published and now - published > MAX_AGE:
                continue
            items.append(NewsItem(title=title, link=link, summary=summary, published=published))

    # Новые сверху; записи без даты публикации (редкость) уходят в конец,
    # чтобы не перекрывать реально свежие новости из других источников.
    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


def pick_fresh_news(feed_urls: list[str], is_used_fn) -> NewsItem | None:
    """Возвращает самую свежую новость, которая ещё не была опубликована."""
    for item in fetch_news(feed_urls):
        if not is_used_fn(item.key):
            return item
    return None
