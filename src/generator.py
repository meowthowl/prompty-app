"""Генерация текста постов через Gemini API (бесплатный тариф)."""
from __future__ import annotations

from google import genai

from .config import Settings

_SYSTEM_PROMPT_TEMPLATE = """Ты — редактор Telegram-канала "{channel_name}" про ИИ и технологии.
{tone}
Пиши только готовый текст поста, без заголовков вида "Пост:", без markdown-разметки,
без кавычек вокруг всего текста. Ограничение — примерно {max_len} символов."""

_RUBRIC_PROMPTS = {
    "news": (
        "Рубрика 'Новость дня'. Вот новость из мира ИИ:\n\n"
        "Заголовок: {title}\nОписание: {summary}\nСсылка: {link}\n\n"
        "Перескажи суть простыми словами и обязательно добавь короткий "
        "абзац 'Что это значит для тебя' — практический вывод для обычного "
        "человека или предпринимателя. В конце укажи ссылку на источник."
    ),
    "digest": (
        "Рубрика 'Дайджест недели'. Вот несколько новостей ИИ за неделю:\n\n"
        "{items}\n\n"
        "Сделай дайджест: 4-5 пунктов списком, каждый — одна суть без воды, "
        "с указанием источника в конце строки."
    ),
    "tool": (
        "Рубрика 'Инструмент дня'. Расскажи про инструмент {name} ({url}). "
        "Короткая заметка: {note}. Опиши, для какой конкретной задачи он "
        "полезен, и приведи один жизненный пример использования. "
        "В конце дай ссылку {url}."
    ),
    "prompt": (
        "Рубрика 'Промпт дня'. Тема: {topic}. "
        "Придумай и покажи один готовый промпт для нейросети под эту задачу — "
        "текст промпта дай отдельным блоком, который можно скопировать целиком. "
        "Перед промптом — 1-2 предложения, для чего он нужен. После — короткий "
        "совет, как его доработать под себя."
    ),
    "lifehack": (
        "Рубрика 'Кейс/лайфхак'. Придумай короткую реалистичную историю "
        "(от первого лица не нужно, пиши обобщённо), как человек использовал "
        "нейросеть, чтобы сэкономить время или деньги на конкретной бытовой "
        "или рабочей задаче. Заверши конкретной цифрой результата (время/деньги)."
    ),
    "fun": (
        "Рубрика 'Забавный факт про ИИ'. Расскажи один неожиданный, "
        "проверяемый факт из истории или устройства искусственного интеллекта. "
        "Легко, с лёгкой иронией, без нравоучений."
    ),
}


def _build_client(settings: Settings) -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def generate_post(settings: Settings, rubric: str, **kwargs) -> str:
    if rubric not in _RUBRIC_PROMPTS:
        raise ValueError(f"Неизвестная рубрика: {rubric}")

    channel_cfg = settings.raw["channel"]
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        channel_name=channel_cfg["name"],
        tone=channel_cfg["tone"],
        max_len=channel_cfg.get("max_post_length", 900),
    )
    user_prompt = _RUBRIC_PROMPTS[rubric].format(**kwargs)

    client = _build_client(settings)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{system_prompt}\n\n{user_prompt}",
    )
    return response.text.strip()


def generate_poll(settings: Settings) -> tuple[str, list[str]]:
    """Генерирует вопрос для опроса вовлечения + варианты ответов."""
    client = _build_client(settings)
    prompt = (
        "Придумай один короткий вовлекающий вопрос-опрос для Telegram-канала "
        "про ИИ и технологии (например про то, какими нейросетями пользуются "
        "читатели). Ответь строго в формате:\n"
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
        # запасной вариант, если модель не выдержала формат
        question = "Какой нейросетью ты пользуешься чаще всего?"
        options = ["ChatGPT", "Gemini", "Claude", "Другая"]
    return question, options
