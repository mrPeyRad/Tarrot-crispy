from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import re
import time
from typing import Any

from app.config import Settings
from app.database import Storage, TarotHistoryEntry
from app.horoscope import ZODIAC_KEYBOARD, build_daily_horoscope, parse_sign
from app.tarot import (
    draw_daily_card,
    draw_relationship_card,
    draw_three_card_spread,
    draw_yes_no_card,
    format_card_guide,
    format_daily_caption,
    format_relationship_caption,
    format_three_card_caption,
    format_yes_no_caption,
    get_card_by_query,
    get_deck_info,
    search_cards,
)
from app.telegram_api import TelegramAPI, TelegramAPIError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

LOGGER = logging.getLogger(__name__)

CARD_OF_DAY_TRIGGERS = {"карта дня", "таро на сегодня"}
HOROSCOPE_TRIGGERS = {"гороскоп"}
THREE_CARD_TRIGGERS = {"расклад 3 карты", "3 карты", "прошлое настоящее будущее"}
YES_NO_TRIGGERS = {"да/нет", "да нет"}
RELATIONSHIP_TRIGGERS = {"карта отношений", "отношения"}
CARD_INFO_TRIGGERS = {"значение карты", "энциклопедия таро", "значение таро"}
CANCEL_TRIGGERS = {"отмена"}
COMMAND_RE = re.compile(r"^/(?P<command>[A-Za-z_]+)(?:@\w+)?(?:\s+(?P<args>.*))?$")

SPREAD_LABELS = {
    "daily": "Карта дня",
    "three-card": "Расклад на 3 карты",
    "yes-no": "Да/Нет",
    "relationship": "Карта отношений",
}


class TarotHoroscopeBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api = TelegramAPI(settings.bot_token, request_timeout=settings.request_timeout)
        self.storage = Storage(settings.database_path)

    @classmethod
    def from_project_root(cls, project_root: Path) -> "TarotHoroscopeBot":
        return cls(Settings.from_env(project_root))

    def run(self) -> None:
        LOGGER.info("Бот запущен и ожидает обновления.")
        offset: int | None = None

        while True:
            try:
                updates = self.api.get_updates(
                    offset=offset,
                    timeout=self.settings.polling_timeout,
                )
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    self._handle_update(update)
            except TelegramAPIError as exc:
                LOGGER.exception("Ошибка Telegram API: %s", exc)
                time.sleep(3)
            except Exception:
                LOGGER.exception("Непредвиденная ошибка в polling-цикле")
                time.sleep(3)

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            return

        chat = message.get("chat", {})
        sender = message.get("from", {})
        chat_id = chat.get("id")
        user_id = sender.get("id")
        message_id = message.get("message_id")
        if not isinstance(chat_id, int) or not isinstance(user_id, int) or not isinstance(message_id, int):
            return

        self.storage.upsert_user(
            user_id=user_id,
            username=sender.get("username"),
            first_name=sender.get("first_name"),
            last_name=sender.get("last_name"),
        )

        command, args = self._parse_command(text)
        normalized_text = self._normalize_text(text)

        if command == "cancel" or normalized_text in CANCEL_TRIGGERS:
            self.storage.clear_conversation_state(chat_id, user_id)
            self.api.send_message(
                chat_id,
                "Текущий сценарий сброшен. Можно продолжать с любой команды.",
                reply_to_message_id=message_id,
                reply_markup={"remove_keyboard": True},
            )
            return

        if command in {"start", "help"}:
            self._send_help(chat_id, message_id)
            return

        if command == "profile":
            self._send_profile(chat_id, user_id, message_id)
            return

        if command == "setsign":
            self._handle_set_sign(chat_id, user_id, message_id, args or "")
            return

        if command in {"horoscope", "goroskop"}:
            self._handle_horoscope_request(chat_id, user_id, message_id, args or "")
            return

        if command in {"card", "karta", "tarot"}:
            self._send_daily_card(chat_id, user_id, message_id)
            return

        if command == "spread3":
            self._send_three_card_spread(chat_id, user_id, message_id)
            return

        if command == "yesno":
            self._send_yes_no(chat_id, user_id, message_id, args or None)
            return

        if command in {"relationship", "relation"}:
            self._send_relationship_card(chat_id, user_id, message_id)
            return

        if command in {"cardinfo", "meaning"}:
            self._handle_card_info(chat_id, user_id, message_id, args or "")
            return

        pending_state = self.storage.get_conversation_state(chat_id, user_id)
        if pending_state and self._handle_pending_state(
            chat_id,
            user_id,
            message_id,
            text,
            pending_state.state,
            pending_state.payload,
        ):
            return

        if normalized_text in CARD_OF_DAY_TRIGGERS:
            self._send_daily_card(chat_id, user_id, message_id)
            return

        if normalized_text in HOROSCOPE_TRIGGERS:
            self._handle_horoscope_request(chat_id, user_id, message_id, "")
            return

        if normalized_text in THREE_CARD_TRIGGERS:
            self._send_three_card_spread(chat_id, user_id, message_id)
            return

        if normalized_text in YES_NO_TRIGGERS:
            self._send_yes_no(chat_id, user_id, message_id, None)
            return

        if normalized_text in RELATIONSHIP_TRIGGERS:
            self._send_relationship_card(chat_id, user_id, message_id)
            return

        if normalized_text in CARD_INFO_TRIGGERS:
            self._handle_card_info(chat_id, user_id, message_id, "")
            return

    def _handle_pending_state(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        text: str,
        state: str,
        payload: dict[str, Any],
    ) -> bool:
        if state == "await_sign":
            sign = parse_sign(text)
            if sign is None:
                self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.save_zodiac_sign(user_id, sign.name)
            self.storage.clear_conversation_state(chat_id, user_id)
            next_action = payload.get("next", "horoscope")
            if next_action == "set_sign":
                self.api.send_message(
                    chat_id,
                    f"Сохранил знак зодиака: {sign.name}. Теперь гороскоп можно получать без повторного выбора.",
                    reply_to_message_id=reply_to_message_id,
                    reply_markup={"remove_keyboard": True},
                )
                return True

            self._send_horoscope(chat_id, reply_to_message_id, sign.name)
            return True

        if state == "await_card_query":
            matches = search_cards(text)
            if not matches:
                self._ask_for_card_name(chat_id, reply_to_message_id, invalid_value=True)
                return True

            if len(matches) > 1:
                self.api.send_message(
                    chat_id,
                    "Нашёл несколько вариантов: "
                    + ", ".join(card.name_ru for card in matches)
                    + ". Напиши название точнее.",
                    reply_to_message_id=reply_to_message_id,
                )
                return True

            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_card_guide(chat_id, reply_to_message_id, matches[0])
            return True

        return False

    def _send_help(self, chat_id: int, reply_to_message_id: int) -> None:
        help_text = (
            "Я умею работать и как таро-бот, и как бот с гороскопом.\n\n"
            "Команды:\n"
            "/card — карта дня\n"
            "/spread3 — расклад на 3 карты\n"
            "/yesno [вопрос] — быстрый ответ Да/Нет\n"
            "/relationship — карта отношений\n"
            "/cardinfo [название карты] — мини-энциклопедия карты\n"
            "/horoscope [знак] — гороскоп на день\n"
            "/setsign [знак] — сохранить свой знак\n"
            "/profile — показать профиль и недавние расклады\n"
            "/cancel — сбросить текущий диалог\n\n"
            "Текстовые триггеры тоже работают: «карта дня», «гороскоп», "
            "«расклад 3 карты», «да/нет», «карта отношений», «значение карты».\n"
            "В группах plain-text триггеры видны боту, если у него отключён privacy mode в BotFather."
        )
        self.api.send_message(chat_id, help_text, reply_to_message_id=reply_to_message_id)

    def _send_profile(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        profile = self.storage.get_user_profile(user_id)
        if profile is None:
            self.api.send_message(
                chat_id,
                "Профиль ещё не создан. Напиши /setsign или /horoscope, и я всё запомню.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        history_count = self.storage.count_tarot_history(user_id)
        recent_history = self.storage.get_recent_tarot_history(user_id, limit=3)
        lines = [
            "Твой профиль",
            f"Знак зодиака: {profile.zodiac_sign or 'пока не задан'}",
            f"Колода: {get_deck_info(profile.preferred_deck).name_ru}",
            f"Сохранённых раскладов: {history_count}",
        ]

        if recent_history:
            lines.append("")
            lines.append("Последние расклады:")
            lines.extend(self._format_history_entry(entry) for entry in recent_history)

        lines.append("")
        lines.append("Чтобы обновить знак, используй /setsign.")
        self.api.send_message(
            chat_id,
            "\n".join(lines),
            reply_to_message_id=reply_to_message_id,
        )

    def _handle_set_sign(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_sign: str,
    ) -> None:
        sign = parse_sign(raw_sign)
        if sign is None:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_sign",
                {"next": "set_sign"},
            )
            self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=bool(raw_sign))
            return

        self.storage.save_zodiac_sign(user_id, sign.name)
        self.storage.clear_conversation_state(chat_id, user_id)
        self.api.send_message(
            chat_id,
            f"Сохранил знак зодиака: {sign.name}. Теперь /horoscope будет работать сразу.",
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _handle_horoscope_request(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_sign: str,
    ) -> None:
        if raw_sign:
            sign = parse_sign(raw_sign)
            if sign is None:
                self.storage.save_conversation_state(
                    chat_id,
                    user_id,
                    "await_sign",
                    {"next": "horoscope"},
                )
                self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
                return

            self.storage.save_zodiac_sign(user_id, sign.name)
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_horoscope(chat_id, reply_to_message_id, sign.name)
            return

        profile = self.storage.get_user_profile(user_id)
        if profile and profile.zodiac_sign:
            self._send_horoscope(chat_id, reply_to_message_id, profile.zodiac_sign)
            return

        self.storage.save_conversation_state(
            chat_id,
            user_id,
            "await_sign",
            {"next": "horoscope"},
        )
        self._ask_for_sign(chat_id, reply_to_message_id)

    def _send_horoscope(self, chat_id: int, reply_to_message_id: int, sign_name: str) -> None:
        sign = parse_sign(sign_name)
        if sign is None:
            self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
            return

        self.api.send_message(
            chat_id,
            build_daily_horoscope(sign),
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _send_daily_card(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        draw = draw_daily_card()
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="daily",
            deck_key=draw.card.deck_key,
            cards_payload=[draw.to_history_payload()],
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.card.image_url,
            caption=format_daily_caption(draw),
            reply_to_message_id=reply_to_message_id,
        )

    def _send_three_card_spread(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        draws = draw_three_card_spread()
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="three-card",
            deck_key=draws[0].card.deck_key,
            cards_payload=[draw.to_history_payload() for draw in draws],
        )
        self.api.send_message(
            chat_id,
            "Расклад на 3 карты: прошлое, настоящее и будущее.",
            reply_to_message_id=reply_to_message_id,
        )
        self.api.send_media_group(
            chat_id,
            media=[
                {
                    "type": "photo",
                    "media": draw.card.image_url,
                    "caption": format_three_card_caption(draw),
                }
                for draw in draws
            ],
        )

    def _send_yes_no(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        question: str | None,
    ) -> None:
        draw = draw_yes_no_card()
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="yes-no",
            deck_key=draw.card.deck_key,
            cards_payload=[draw.to_history_payload()],
            question=question,
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.card.image_url,
            caption=format_yes_no_caption(draw, question=question),
            reply_to_message_id=reply_to_message_id,
        )

    def _send_relationship_card(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        draw = draw_relationship_card()
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="relationship",
            deck_key=draw.card.deck_key,
            cards_payload=[draw.to_history_payload()],
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.card.image_url,
            caption=format_relationship_caption(draw),
            reply_to_message_id=reply_to_message_id,
        )

    def _handle_card_info(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        query: str,
    ) -> None:
        if not query:
            self.storage.save_conversation_state(chat_id, user_id, "await_card_query")
            self._ask_for_card_name(chat_id, reply_to_message_id)
            return

        exact = get_card_by_query(query)
        if exact is not None:
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_card_guide(chat_id, reply_to_message_id, exact)
            return

        matches = search_cards(query)
        if not matches:
            self.storage.save_conversation_state(chat_id, user_id, "await_card_query")
            self._ask_for_card_name(chat_id, reply_to_message_id, invalid_value=True)
            return

        if len(matches) > 1:
            self.storage.save_conversation_state(chat_id, user_id, "await_card_query")
            self.api.send_message(
                chat_id,
                "Нашёл несколько карт: "
                + ", ".join(card.name_ru for card in matches)
                + ". Напиши точное название.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        self.storage.clear_conversation_state(chat_id, user_id)
        self._send_card_guide(chat_id, reply_to_message_id, matches[0])

    def _send_card_guide(self, chat_id: int, reply_to_message_id: int, card: Any) -> None:
        self.api.send_photo(
            chat_id,
            photo_url=card.image_url,
            caption=format_card_guide(card),
            reply_to_message_id=reply_to_message_id,
        )

    def _ask_for_sign(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не распознал знак. Выбери его с клавиатуры или напиши текстом."
            if invalid_value
            else "Какой у тебя знак зодиака? Выбери его с клавиатуры или напиши текстом."
        )
        reply_markup = {
            "keyboard": [list(row) for row in ZODIAC_KEYBOARD],
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "input_field_placeholder": "Например: Овен",
        }
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    def _ask_for_card_name(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не нашёл такую карту. Попробуй написать точнее, например: Луна или Король Кубков."
            if invalid_value
            else "Какую карту показать в энциклопедии? Например: Луна, Шут или Король Кубков."
        )
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
        )

    def _format_history_entry(self, entry: TarotHistoryEntry) -> str:
        created = self._format_entry_date(entry.created_at)
        cards = ", ".join(card["name_ru"] for card in entry.cards[:3])
        label = SPREAD_LABELS.get(entry.spread_type, entry.spread_type)
        if entry.question:
            return f"{created} — {label}: {cards} | Вопрос: {entry.question}"
        return f"{created} — {label}: {cards}"

    @staticmethod
    def _format_entry_date(raw_value: str) -> str:
        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return raw_value
        return parsed.strftime("%d.%m.%Y")

    @staticmethod
    def _normalize_text(text: str) -> str:
        cleaned = text.casefold().replace("ё", "е").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    @staticmethod
    def _parse_command(text: str) -> tuple[str | None, str | None]:
        match = COMMAND_RE.match(text.strip())
        if not match:
            return None, None

        command = match.group("command")
        args = match.group("args") or ""
        return command.casefold(), args.strip()
