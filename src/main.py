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


def _handle_news(settings) -> str | None:
    feeds = settings.raw["rss_feeds"]
    item = sources.pick_fresh_news(feeds, lambda key: dedup.is_used("news", key))
    if item is None:
        log.warning("Нет свежих новостей в RSS — пропускаю рубрику 'news'")
        return None
    text = generator.generate_post(
        settings, "news", title=item.title, summary=item.summary, link=item.link
    )
    dedup.mark_used("news", item.key)
    return text


def _handle_digest(settings) -> str | None:
    feeds = settings.raw["rss_feeds"]
    all_items = sources.fetch_news(feeds)
    # Пропускаем и то, что уже было в дайджесте, и то, что уже вышло в
    # ежедневной рубрике news — иначе дайджест недели будет повторяться.
    fresh = [
        i for i in all_items if not dedup.is_used("digest", i.key) and not dedup.is_used("news", i.key)
    ][:5]
    if not fresh:
        log.warning("Нет свежих новостей для дайджеста — пропускаю рубрику 'digest'")
        return None
    items_text = "\n".join(f"- {i.title} ({i.link})" for i in fresh)
    text = generator.generate_post(settings, "digest", items=items_text)
    for i in fresh:
        dedup.mark_used("digest", i.key)
    return text


def _handle_tool(settings) -> str | None:
    tools = settings.raw["tools"]
    names = [t["name"] for t in tools]
    chosen_name = dedup.pick_unused("tool", names)
    tool = next(t for t in tools if t["name"] == chosen_name)
    text = generator.generate_post(
        settings, "tool", name=tool["name"], url=tool["url"], note=tool["note"]
    )
    dedup.mark_used("tool", chosen_name)
    return text


def _handle_prompt(settings) -> str | None:
    topics = settings.raw["prompt_topics"]
    chosen = dedup.pick_unused("prompt_topic", topics)
    text = generator.generate_post(settings, "prompt", topic=chosen)
    dedup.mark_used("prompt_topic", chosen)
    return text


def _handle_lifehack(settings) -> str | None:
    topics = settings.raw["lifehack_topics"]
    chosen = dedup.pick_unused("lifehack_topic", topics)
    text = generator.generate_post(settings, "lifehack", topic=chosen)
    dedup.mark_used("lifehack_topic", chosen)
    return text


def _handle_fun(settings) -> str | None:
    topics = settings.raw["fun_topics"]
    chosen = dedup.pick_unused("fun_topic", topics)
    text = generator.generate_post(settings, "fun", topic=chosen)
    dedup.mark_used("fun_topic", chosen)
    return text


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


def _publish_en_copy(settings, text: str, image_bytes: bytes | None, dry_run: bool) -> None:
    """Переводит пост и публикует его в англоязычный канал, если он настроен
    (TELEGRAM_CHANNEL_ID_EN). Картинка не регенерируется — используется та же."""
    if not settings.telegram_channel_id_en:
        return
    en_text = generator.translate_post(settings, text)
    log.info("EN-версия поста:\n%s", en_text)
    if dry_run:
        return
    telegram_client.post_text_or_photo(
        settings, en_text, image_bytes, chat_id=settings.telegram_channel_id_en
    )
    log.info("Пост опубликован в EN-канал")


def run(
    rubric: str | None = None,
    dry_run: bool = False,
    custom_text: str | None = None,
    custom_image_prompt: str | None = None,
    translate_en: bool = False,
) -> None:
    settings = load_settings()

    if custom_text:
        # Готовый рекламный/спонсорский пост — публикуем текст как есть,
        # без ИИ-генерации. Картинка опциональна.
        log.info("Ручной пост (например, реклама):\n%s", custom_text)
        image_bytes = None
        if custom_image_prompt and not dry_run:
            image_bytes = images.generate_image(settings, custom_image_prompt)
        if dry_run:
            log.info("Dry-run: публикация пропущена")
            if translate_en:
                _publish_en_copy(settings, custom_text, image_bytes, dry_run=True)
            return
        telegram_client.post_text_or_photo(settings, custom_text, image_bytes)
        log.info("Пост опубликован")
        if translate_en:
            _publish_en_copy(settings, custom_text, image_bytes, dry_run=False)
        return

    rubric = rubric or _rubric_for_today(settings)
    log.info("Рубрика: %s", rubric)

    if rubric == "poll":
        question, options = generator.generate_poll(settings)
        log.info("Опрос: %s | %s", question, options)
        if not dry_run:
            telegram_client.send_poll(settings, question, options)
        if settings.telegram_channel_id_en:
            en_question, en_options = generator.translate_poll(settings, question, options)
            log.info("EN-опрос: %s | %s", en_question, en_options)
            if not dry_run:
                telegram_client.send_poll(
                    settings, en_question, en_options, chat_id=settings.telegram_channel_id_en
                )
        return

    handler = _RUBRIC_HANDLERS.get(rubric)
    if handler is None:
        raise ValueError(f"Неизвестная рубрика: {rubric}")

    text = handler(settings)
    if text is None:
        log.info("Пост не сгенерирован (нет данных), выхожу без публикации")
        return
    log.info("Текст поста:\n%s", text)

    # Промпт для обложки строим по содержанию именно этого поста (а не по
    # общему шаблону рубрики) — так картинка реально соответствует тексту.
    image_prompt = generator.generate_image_prompt(settings, text)
    log.info("Промпт для обложки: %s", image_prompt)

    image_bytes = None
    if not dry_run and image_prompt:
        image_bytes = images.generate_image(settings, image_prompt)
    if dry_run:
        log.info("Dry-run: публикация пропущена")
        _publish_en_copy(settings, text, image_bytes, dry_run=True)
        return

    telegram_client.post_text_or_photo(settings, text, image_bytes)
    log.info("Пост опубликован")
    _publish_en_copy(settings, text, image_bytes, dry_run=False)


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
    parser.add_argument(
        "--text",
        help="Опубликовать готовый текст как есть (без ИИ) — для рекламных/спонсорских постов",
    )
    parser.add_argument(
        "--image-prompt",
        help="Промпт для обложки к --text (на английском). Опционально, требует настроенного Cloudflare",
    )
    parser.add_argument(
        "--translate-en",
        action="store_true",
        help="Для --text: перевести и опубликовать также в EN-канал (по умолчанию рекламные посты не дублируются)",
    )
    args = parser.parse_args()

    try:
        run(
            rubric=args.rubric,
            dry_run=args.dry_run,
            custom_text=args.text,
            custom_image_prompt=args.image_prompt,
            translate_en=args.translate_en,
        )
    except Exception:
        log.exception("Ошибка при выполнении пайплайна")
        sys.exit(1)


if __name__ == "__main__":
    main()
