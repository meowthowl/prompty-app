"""Генерация текста постов через Gemini API (бесплатный тариф)."""
from __future__ import annotations

import logging

from google import genai

from .config import Settings

log = logging.getLogger("tg-channel")

_SYSTEM_PROMPT_TEMPLATE = """Ты — редактор Telegram-канала "{channel_name}" — {topic_description}.
{tone}
Пиши только готовый текст поста, без заголовков вида "Пост:", без markdown-разметки,
без кавычек вокруг всего текста. Ограничение — примерно {max_len} символов."""


def _build_client(settings: Settings) -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def generate_post(settings: Settings, rubric: str, **kwargs) -> str:
    """Тексты рубрик — не хардкод в коде, а часть профиля канала
    (profiles/<профиль>.yaml → rubric_prompts), чтобы разные ниши могли
    иметь совершенно разные формулировки без изменения кода."""
    rubric_prompts = settings.raw["rubric_prompts"]
    if rubric not in rubric_prompts:
        raise ValueError(f"Неизвестная рубрика: {rubric}")

    channel_cfg = settings.raw["channel"]
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        channel_name=channel_cfg["name"],
        topic_description=channel_cfg["topic_description"],
        tone=channel_cfg["tone"],
        max_len=channel_cfg.get("max_post_length", 900),
    )
    user_prompt = rubric_prompts[rubric].format(**kwargs)

    client = _build_client(settings)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{system_prompt}\n\n{user_prompt}",
    )
    return response.text.strip()


_IMAGE_PROMPT_INSTRUCTIONS = """Read the Telegram post below (in Russian) and write ONE short English
prompt (max 30 words) for an AI image generator, describing a cover
illustration that is CONCRETELY and LITERALLY relevant to what THIS SPECIFIC
post is about — a clear, recognizable scene or object tied to its actual
subject, not a generic tech cliche.

Hard rules:
- No surreal, abstract, cubist, glitch, or "melting" art styles.
- No generic humanoid robots, glowing brains, or circuit-board backgrounds
  unless the post is literally about robots or brains.
- Style: clean flat editorial illustration OR a realistic photo-like scene,
  muted professional color palette, no text or logos in the image.
- Return ONLY the prompt itself, nothing else — no explanations, no quotes.

Post:
{text}"""


def generate_image_prompt(settings: Settings, post_text: str) -> str | None:
    """Просит Gemini придумать предметный, конкретный промпт для обложки по
    содержанию именно этого поста — вместо общего шаблона типа "AI, digital
    art". Возвращает None при сбое — тогда пост выходит без картинки, что
    лучше, чем случайная нерелевантная иллюстрация."""
    try:
        client = _build_client(settings)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=_IMAGE_PROMPT_INSTRUCTIONS.format(text=post_text),
        )
        prompt = response.text.strip().strip('"')
        return prompt or None
    except Exception:
        log.warning("Не удалось сгенерировать промпт для обложки", exc_info=True)
        return None


def generate_poll(settings: Settings) -> tuple[str, list[str]]:
    """Генерирует вопрос для опроса вовлечения + варианты ответов."""
    topic_description = settings.raw["channel"]["topic_description"]
    client = _build_client(settings)
    prompt = (
        f"Придумай один короткий вовлекающий вопрос-опрос для Telegram-канала "
        f"{topic_description}. Ответь строго в формате:\n"
        "ВОПРОС: <текст вопроса>\n"
        "ВАРИАНТ: <вариант 1>\n"
        "ВАРИАНТ: <вариант 2>\n"
        "ВАРИАНТ: <вариант 3>\n"
        "ВАРИАНТ: <вариант 4>\n"
        "Вариантов должно быть от 2 до 6."
    )
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )
    question = ""
    options: list[str] = []
    for line in response.text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("ВОПРОС:"):
            question = line.split(":", 1)[1].strip()
        elif line.upper().startswith("ВАРИАНТ:"):
            options.append(line.split(":", 1)[1].strip())
    if not question or len(options) < 2:
        # запасной вариант, если модель не выдержала формат — нейтральный,
        # не привязан к конкретной нише
        question = "Какие посты тебе интереснее всего?"
        options = ["Новости", "Практическая польза", "Опросы и общение", "Всё нравится"]
    return question, options
