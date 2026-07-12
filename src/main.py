"""Точка входа: определяет рубрику дня, генерирует пост и публикует его
в Telegram-канал. Запускается вручную (python -m src.main) или по расписанию
из GitHub Actions."""
from __future__ import annotations

import argparse
import datetime
import logging
import sys

from . import dedup, generator, images, sources, telegram_client
from .config import load_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("tg-channel")


def _handle_news(settings) -> tuple[str, str] | None:
    feeds = settings.raw["rss_feeds"]
    item = sources.pick_fresh_news(feeds, lambda key: dedup.is_used("news", key))
    if item is None:
        log.warning("Нет свежих новостей в RSS — пропускаю рубрику 'news'")
        return None
    text = generator.generate_post(
        settings, "news", title=item.title, summary=item.summary, link=item.link
    )
    dedup.mark_used("news", item.key)
    return text, f"illustration for tech news article: {item.title}, digital art, minimalistic"


def _handle_digest(settings) -> tuple[str, str] | None:
    feeds = settings.raw["rss_feeds"]
    all_items = sources.fetch_news(feeds)
    fresh = [i for i in all_items if not dedup.is_used("digest", i.key)][:5]
    if not fresh:
        log.warning("Нет свежих новостей для дайджеста — пропускаю рубрику 'digest'")
        return None
    items_text = "\n".join(f"- {i.title} ({i.link})" for i in fresh)
    text = generator.generate_post(settings, "digest", items=items_text)
    for i in fresh:
        dedup.mark_used("digest", i.key)
    return text, "weekly AI news digest illustration, digital art, minimalistic"


def _handle_tool(settings) -> tuple[str, str] | None:
    tools = settings.raw["tools"]
    names = [t["name"] for t in tools]
    chosen_name = dedup.pick_unused("tool", names)
    tool = next(t for t in tools if t["name"] == chosen_name)
    text = generator.generate_post(
        settings, "tool", name=tool["name"], url=tool["url"], note=tool["note"]
    )
    dedup.mark_used("tool", chosen_name)
    return text, f"logo style illustration representing the AI tool {tool['name']}, flat design"


def _handle_prompt(settings) -> tuple[str, str] | None:
    topics = settings.raw["prompt_topics"]
    chosen = dedup.pick_unused("prompt_topic", topics)
    text = generator.generate_post(settings, "prompt", topic=chosen)
    dedup.mark_used("prompt_topic", chosen)
    return text, f"minimalistic illustration about: {chosen}"


def _handle_lifehack(settings) -> tuple[str, str] | None:
    text = generator.generate_post(settings, "lifehack")
    return text, "person saving time using AI assistant, digital illustration, minimalistic"


def _handle_fun(settings) -> tuple[str, str] | None:
    text = generator.generate_post(settings, "fun")
    return text, "fun quirky illustration about artificial intelligence history, flat design"


_RUBRIC_HANDLERS = {
    "news": _handle_news,
    "digest": _handle_digest,
    "tool": _handle_tool,
    "prompt": _handle_prompt,
    "lifehack": _handle_lifehack,
    "fun": _handle_fun,
}


def _rubric_for_today(settings) -> str:
    weekday = datetime.datetime.now(datetime.timezone.utc).weekday()
    return settings.raw["schedule"][weekday]


def run(rubric: str | None = None, dry_run: bool = False) -> None:
    settings = load_settings()
    rubric = rubric or _rubric_for_today(settings)
    log.info("Рубрика: %s", rubric)

    if rubric == "poll":
        question, options = generator.generate_poll(settings)
        log.info("Опрос: %s | %s", question, options)
        if not dry_run:
            telegram_client.send_poll(settings, question, options)
        return

    handler = _RUBRIC_HANDLERS.get(rubric)
    if handler is None:
        raise ValueError(f"Неизвестная рубрика: {rubric}")

    result = handler(settings)
    if result is None:
        log.info("Пост не сгенерирован (нет данных), выхожу без публикации")
        return

    text, image_prompt = result
    log.info("Текст поста:\n%s", text)

    image_bytes = None if dry_run else images.generate_image(image_prompt)
    if dry_run:
        log.info("Dry-run: публикация пропущена")
        return

    telegram_client.post_text_or_photo(settings, text, image_bytes)
    log.info("Пост опубликован")


def main() -> None:
    parser = argparse.ArgumentParser(description="Автопостинг в Telegram-канал про ИИ")
    parser.add_argument(
        "--rubric",
        choices=list(_RUBRIC_HANDLERS.keys()) + ["poll"],
        help="Принудительно запустить конкретную рубрику (по умолчанию — по дню недели)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Сгенерировать пост и вывести в лог без публикации в канал",
    )
    args = parser.parse_args()

    try:
        run(rubric=args.rubric, dry_run=args.dry_run)
    except Exception:
        log.exception("Ошибка при выполнении пайплайна")
        sys.exit(1)


if __name__ == "__main__":
    main()
