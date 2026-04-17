from __future__ import annotations

from dataclasses import dataclass

from app.tarot import CardDraw, get_deck_info

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - depends on optional dependency
    OpenAI = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class TarotQuestionInterpretation:
    text: str
    used_ai: bool
    note: str | None = None


class TarotQuestionInterpreter:
    def __init__(self, api_key: str | None, model: str = "gpt-5-mini") -> None:
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def availability_note(self) -> str | None:
        if OpenAI is None:
            return "Для AI-интерпретации нужно установить пакет openai."
        if not self.api_key:
            return "Для AI-интерпретации добавь OPENAI_API_KEY в .env."
        return None

    def interpret(self, question: str, draw: CardDraw) -> TarotQuestionInterpretation:
        if self.availability_note is not None:
            return TarotQuestionInterpretation(
                text=build_fallback_question_reading(question, draw),
                used_ai=False,
                note=self.availability_note,
            )

        client = self._get_client()
        prompt = (
            "Пользователь задал вопрос к таро.\n"
            f"Вопрос: {question}\n"
            f"Карта: {draw.card.name_ru} ({draw.card.name_en})\n"
            f"Колода: {get_deck_info(draw.deck_key).name_ru}\n"
            f"Положение: {draw.orientation_label}\n"
            f"Ключевые слова: {', '.join(draw.card.keywords)}\n"
            f"Базовое прямое значение: {draw.card.upright_meaning}\n"
            f"Базовое перевёрнутое значение: {draw.card.reversed_meaning}\n"
            f"Активное значение этой карты сейчас: {draw.meaning}\n\n"
            "Сделай персональную интерпретацию под вопрос пользователя.\n"
            "Отвечай по-русски, тепло и конкретно, без мистической псевдоуверенности.\n"
            "Структура ответа:\n"
            "1. Одна короткая строка-вывод.\n"
            "2. Один абзац с разбором, как символика карты касается вопроса.\n"
            "3. Одно мягкое практическое действие на ближайшее время.\n"
            "Ограничение: максимум 650 символов.\n"
            "Не давай медицинских, юридических и финансовых гарантий.\n"
        )
        response = client.responses.create(
            model=self.model,
            reasoning={"effort": "low"},
            input=prompt,
        )
        text = (response.output_text or "").strip()
        if not text:
            return TarotQuestionInterpretation(
                text=build_fallback_question_reading(question, draw),
                used_ai=False,
                note="AI не вернул текст, показал базовую трактовку.",
            )
        return TarotQuestionInterpretation(text=text, used_ai=True)

    def _get_client(self):
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client


def build_fallback_question_reading(question: str, draw: CardDraw) -> str:
    action_tip = (
        "Сейчас лучше двигаться через ясный следующий шаг и не застревать в сомнениях."
        if not draw.is_reversed
        else "Сейчас полезно сбавить темп, перепроверить мотивацию и не давить на исход."
    )
    return (
        f"Главный вектор карты — {draw.card.name_ru}.\n"
        f"На вопрос «{question}» она отвечает через тему: {draw.meaning}\n\n"
        f"Если смотреть практично, обрати внимание на связку «{', '.join(draw.card.keywords)}» и спроси себя, "
        f"где в этой ситуации уже есть ресурс, а где нужен более честный взгляд. {action_tip}"
    )
