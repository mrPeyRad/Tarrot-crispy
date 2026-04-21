from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import quote

from app.ai import TarotQuestionInterpreter
from app.biorhythm import build_biorhythm_report, build_biorhythm_snapshot, parse_birth_date
from app.config import Settings
from app.cosmic import (
    build_compatibility_insight,
    build_compatibility_report,
    build_daily_astro_alert,
    build_lunar_calendar,
    extract_signs,
)
from app.database import DeliverySubscription, JournalEntry, Storage, TarotHistoryEntry
from app.horoscope import (
    ZODIAC_KEYBOARD,
    build_daily_horoscope,
    build_weekly_horoscope,
    parse_sign,
)
from app.mystic import ask_magic_ball, draw_rune_of_day, format_magic_ball_reply, format_rune_draw
from app.share_cards import (
    render_biorhythm_share_card,
    render_compatibility_share_card,
    render_rune_share_card,
    render_tarot_share_card,
    render_welcome_card,
)
from app.tarot import (
    build_card_image_url,
    draw_daily_card,
    draw_question_card,
    draw_relationship_card,
    draw_three_card_spread,
    draw_weekly_card,
    draw_yes_no_card,
    format_card_guide,
    format_daily_caption,
    format_question_caption,
    format_relationship_caption,
    format_three_card_caption,
    format_weekly_caption,
    format_yes_no_caption,
    get_available_decks,
    get_card_by_query,
    get_deck_info,
    parse_deck,
    search_cards,
)
from app.telegram_api import TelegramAPI, TelegramAPIError
from app.webhook_server import TelegramWebhookServer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

LOGGER = logging.getLogger(__name__)

CARD_OF_DAY_TRIGGERS = {"карта дня", "таро на сегодня"}
HOROSCOPE_TRIGGERS = {"гороскоп", "гороскоп на день"}
WEEKLY_HOROSCOPE_TRIGGERS = {"гороскоп на неделю", "недельный гороскоп", "астропрогноз на неделю"}
MOON_TRIGGERS = {"лунный календарь", "фаза луны", "луна сегодня"}
COMPATIBILITY_TRIGGERS = {"совместимость", "совместимость знаков"}
ASTRO_ALERT_TRIGGERS = {"астроалерт", "астро-событие", "ретроградный меркурий"}
THREE_CARD_TRIGGERS = {"расклад 3 карты", "3 карты", "прошлое настоящее будущее"}
YES_NO_TRIGGERS = {"да/нет", "да нет", "быстрый ответ"}
RELATIONSHIP_TRIGGERS = {"карта отношений", "отношения"}
CARD_INFO_TRIGGERS = {"значение карты", "энциклопедия таро", "значение таро"}
RUNE_TRIGGERS = {"руна дня", "руна"}
MAGIC_BALL_TRIGGERS = {"шар предсказаний", "магический шар", "magic 8 ball"}
DECK_TRIGGERS = {"колода", "сменить колоду", "визуал колоды"}
JOURNAL_TRIGGERS = {"дневник предсказаний", "дневник", "журнал предсказаний"}
SUBSCRIBE_TRIGGERS = {"рассылка", "подписка", "подписаться"}
TAROT_QUESTION_TRIGGERS = {"вопрос к таро", "спросить таро", "таро по вопросу"}
BIORHYTHM_TRIGGERS = {"биоритмы", "биоритм"}
MENU_TRIGGERS = {"меню", "главное меню", "меню бота"}
CANCEL_TRIGGERS = {"отмена"}
COMMAND_RE = re.compile(r"^/(?P<command>[A-Za-z0-9_]+)(?:@\w+)?(?:\s+(?P<args>.*))?$")
TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})$")

SPREAD_LABELS = {
    "daily": "Карта дня",
    "weekly": "Карта недели",
    "three-card": "Расклад на 3 карты",
    "yes-no": "Да/Нет",
    "relationship": "Карта отношений",
    "question": "Вопрос к таро",
}

ENTRY_LABELS = {
    "tarot-daily": "Карта дня",
    "tarot-weekly": "Карта недели",
    "tarot-three-card": "Расклад на 3 карты",
    "tarot-yes-no": "Да/Нет",
    "tarot-relationship": "Карта отношений",
    "tarot-question": "Вопрос к таро",
    "horoscope-daily": "Гороскоп на день",
    "horoscope-weekly": "Гороскоп на неделю",
    "moon": "Лунный календарь",
    "astroalert": "Астро-алерт",
    "rune": "Руна дня",
    "magic-ball": "Шар предсказаний",
    "biorhythm": "Биоритмы",
}

SUBSCRIPTION_KEYBOARD = (
    ("ежедневно", "еженедельно"),
)
TIME_KEYBOARD = (
    ("08:00", "09:00", "10:00"),
    ("18:00", "19:00", "21:00"),
)
MAIN_MENU_KEYBOARD = (
    ("карта дня", "гороскоп на день"),
    ("быстрый ответ", "шар предсказаний"),
)


BOT_COMMANDS = (
    ("menu", "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e"),
    ("card", "\u041a\u0430\u0440\u0442\u0430 \u0434\u043d\u044f"),
    ("ask", "\u041a\u0430\u0440\u0442\u0430 \u043f\u043e \u0432\u0430\u0448\u0435\u043c\u0443 \u0432\u043e\u043f\u0440\u043e\u0441\u0443"),
    ("spread3", "\u0420\u0430\u0441\u043a\u043b\u0430\u0434 \u043d\u0430 3 \u043a\u0430\u0440\u0442\u044b"),
    ("yesno", "\u0411\u044b\u0441\u0442\u0440\u044b\u0439 \u043e\u0442\u0432\u0435\u0442 \u0414\u0430/\u041d\u0435\u0442"),
    ("relationship", "\u041a\u0430\u0440\u0442\u0430 \u043e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u0439"),
    ("cardinfo", "\u0417\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043a\u0430\u0440\u0442\u044b"),
    ("horoscope", "\u0413\u043e\u0440\u043e\u0441\u043a\u043e\u043f \u043d\u0430 \u0434\u0435\u043d\u044c"),
    ("week", "\u0413\u043e\u0440\u043e\u0441\u043a\u043e\u043f \u043d\u0430 \u043d\u0435\u0434\u0435\u043b\u044e"),
    ("moon", "\u041b\u0443\u043d\u043d\u044b\u0439 \u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044c"),
    ("compat", "\u0421\u043e\u0432\u043c\u0435\u0441\u0442\u0438\u043c\u043e\u0441\u0442\u044c \u0437\u043d\u0430\u043a\u043e\u0432"),
    ("astroalert", "\u0410\u0441\u0442\u0440\u043e\u0430\u043b\u0435\u0440\u0442 \u043d\u0430 \u0434\u0435\u043d\u044c"),
    ("rune", "\u0420\u0443\u043d\u0430 \u0434\u043d\u044f"),
    ("8ball", "\u0428\u0430\u0440 \u043f\u0440\u0435\u0434\u0441\u043a\u0430\u0437\u0430\u043d\u0438\u0439"),
    ("biorhythm", "\u0411\u0438\u043e\u0440\u0438\u0442\u043c\u044b \u043d\u0430 \u0441\u0435\u0433\u043e\u0434\u043d\u044f"),
    ("deck", "\u0421\u043c\u0435\u043d\u0438\u0442\u044c \u0432\u0438\u0437\u0443\u0430\u043b \u043a\u043e\u043b\u043e\u0434\u044b"),
    ("journal", "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0434\u043d\u0435\u0432\u043d\u0438\u043a"),
    ("subscribe", "\u041d\u0430\u0441\u0442\u0440\u043e\u0438\u0442\u044c \u0440\u0430\u0441\u0441\u044b\u043b\u043a\u0443"),
    ("profile", "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u043f\u0440\u043e\u0444\u0438\u043b\u044c"),
    ("help", "\u041a\u043e\u0440\u043e\u0442\u043a\u0430\u044f \u0441\u043f\u0440\u0430\u0432\u043a\u0430"),
)


class TarotHoroscopeBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api = TelegramAPI(settings.bot_token, request_timeout=settings.request_timeout)
        self.storage = Storage(settings.database_path)
        self.tarot_ai = TarotQuestionInterpreter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        self._bot_username = settings.bot_username

    @classmethod
    def from_project_root(cls, project_root: Path) -> "TarotHoroscopeBot":
        return cls(Settings.from_env(project_root))

    def run(self) -> None:
        self._configure_public_profile()
        self._configure_native_menu()
        if self.settings.run_mode == "webhook":
            self._run_webhook()
            return

        self._run_polling()

    def _run_polling(self) -> None:
        try:
            self.api.delete_webhook(drop_pending_updates=False)
        except TelegramAPIError:
            LOGGER.exception("Не удалось отключить webhook перед переходом в polling")

        LOGGER.info("Бот запущен и ожидает обновления.")
        offset: int | None = None

        while True:
            try:
                self._dispatch_due_subscriptions()
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

    def _run_webhook(self) -> None:
        if not self.settings.webhook_url:
            raise RuntimeError(
                "Для webhook-режима нужно указать WEBHOOK_URL с публичным https-адресом."
            )

        self.api.set_webhook(
            self.settings.webhook_url,
            secret_token=self.settings.webhook_secret_token,
            drop_pending_updates=False,
            allowed_updates=["message"],
        )

        self._dispatch_due_subscriptions()
        server = TelegramWebhookServer(
            host=self.settings.webhook_host,
            port=self.settings.webhook_port,
            webhook_path=self.settings.webhook_path,
            on_update=self._handle_update,
            on_tick=self._dispatch_due_subscriptions,
            tick_interval=self.settings.subscription_poll_interval,
            secret_token=self.settings.webhook_secret_token,
            logger=LOGGER,
        )

        bind_host, bind_port = server.bind_address
        LOGGER.info(
            "Webhook-сервер запущен на %s:%s и ожидает обновления по пути %s.",
            bind_host,
            bind_port,
            self.settings.webhook_path,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info("Получен сигнал остановки, завершаю webhook-сервер.")
        finally:
            server.shutdown()

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

        if command == "start":
            self._open_main_menu(chat_id, user_id, message_id)
            return

        if command == "menu":
            self._open_main_menu(chat_id, user_id, message_id)
            return

        if command == "help":
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

        if command in {"week", "horoscope_week", "weekly"}:
            self._handle_weekly_horoscope_request(chat_id, user_id, message_id, args or "")
            return

        if command in {"moon", "luna"}:
            self._send_moon_calendar(chat_id, user_id, message_id)
            return

        if command in {"compat", "compatibility"}:
            self._handle_compatibility_request(chat_id, user_id, message_id, args or "")
            return

        if command in {"astroalert", "astro"}:
            self._send_astro_alert(chat_id, user_id, message_id)
            return

        if command == "deck":
            self._handle_deck_selection(chat_id, user_id, message_id, args or "")
            return

        if command in {"card", "karta", "tarot"}:
            self._send_daily_card(chat_id, user_id, message_id)
            return

        if command in {"ask", "tarotask", "question"}:
            self._handle_tarot_question(chat_id, user_id, message_id, args or "")
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

        if command == "rune":
            self._send_rune_of_day(chat_id, user_id, message_id)
            return

        if command in {"8ball", "ball", "magicball"}:
            self._handle_magic_ball(chat_id, user_id, message_id, args or "")
            return

        if command in {"journal", "diary"}:
            self._send_journal(chat_id, user_id, message_id)
            return

        if command in {"biorhythm", "bio"}:
            self._handle_biorhythm_request(chat_id, user_id, message_id, args or "")
            return

        if command in {"subscribe", "subscription"}:
            self._handle_subscription_request(chat_id, user_id, message_id, args or "")
            return

        if command == "unsubscribe":
            self._unsubscribe(chat_id, user_id, message_id)
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

        if normalized_text in MENU_TRIGGERS:
            self._open_main_menu(chat_id, user_id, message_id)
            return

        if normalized_text in TAROT_QUESTION_TRIGGERS:
            self._handle_tarot_question(chat_id, user_id, message_id, "")
            return

        if normalized_text in HOROSCOPE_TRIGGERS:
            self._handle_horoscope_request(chat_id, user_id, message_id, "")
            return

        if normalized_text in WEEKLY_HOROSCOPE_TRIGGERS:
            self._handle_weekly_horoscope_request(chat_id, user_id, message_id, "")
            return

        if normalized_text in MOON_TRIGGERS:
            self._send_moon_calendar(chat_id, user_id, message_id)
            return

        if normalized_text in COMPATIBILITY_TRIGGERS:
            self._handle_compatibility_request(chat_id, user_id, message_id, "")
            return

        if normalized_text in ASTRO_ALERT_TRIGGERS:
            self._send_astro_alert(chat_id, user_id, message_id)
            return

        if normalized_text in DECK_TRIGGERS:
            self._handle_deck_selection(chat_id, user_id, message_id, "")
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

        if normalized_text in RUNE_TRIGGERS:
            self._send_rune_of_day(chat_id, user_id, message_id)
            return

        if normalized_text in MAGIC_BALL_TRIGGERS:
            self._handle_magic_ball(chat_id, user_id, message_id, "")
            return

        if normalized_text in JOURNAL_TRIGGERS:
            self._send_journal(chat_id, user_id, message_id)
            return

        if normalized_text in BIORHYTHM_TRIGGERS:
            self._handle_biorhythm_request(chat_id, user_id, message_id, "")
            return

        if normalized_text in SUBSCRIBE_TRIGGERS:
            self._handle_subscription_request(chat_id, user_id, message_id, "")
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
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
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

            if next_action == "horoscope_week":
                self._send_weekly_horoscope(chat_id, user_id, reply_to_message_id, sign.name)
                return True

            if next_action == "subscribe":
                self._save_subscription(
                    chat_id,
                    user_id,
                    reply_to_message_id,
                    payload.get("cadence", "daily"),
                    payload.get("hour_local", 9),
                    payload.get("minute_local", 0),
                )
                return True

            if next_action == "subscribe_daily":
                self._save_subscription(chat_id, user_id, reply_to_message_id, "daily", 9, 0)
                return True

            if next_action == "subscribe_weekly":
                self._save_subscription(chat_id, user_id, reply_to_message_id, "weekly", 9, 0)
                return True

            self._send_horoscope(chat_id, user_id, reply_to_message_id, sign.name)
            return True

        if state == "await_card_query":
            matches = search_cards(text)
            if not matches:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
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
            self._send_card_guide(chat_id, user_id, reply_to_message_id, matches[0])
            return True

        if state == "await_compatibility_first":
            sign = parse_sign(text)
            if sign is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_compatibility_second",
                {"first_sign": sign.name},
            )
            self._ask_for_partner_sign(chat_id, reply_to_message_id, sign.name)
            return True

        if state == "await_compatibility_second":
            second_sign = parse_sign(text)
            if second_sign is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                first_sign_name = payload.get("first_sign")
                self._ask_for_partner_sign(
                    chat_id,
                    reply_to_message_id,
                    first_sign_name,
                    invalid_value=True,
                )
                return True

            first_sign_name = payload.get("first_sign")
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_compatibility_report(
                chat_id,
                reply_to_message_id,
                first_sign_name,
                second_sign.name,
            )
            return True

        if state == "await_magic_question":
            question = text.strip()
            if not question:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_magic_question(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_magic_ball(chat_id, user_id, reply_to_message_id, question)
            return True

        if state == "await_tarot_question":
            question = text.strip()
            if not question:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_tarot_question(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_tarot_question_reading(chat_id, user_id, reply_to_message_id, question)
            return True

        if state == "await_birth_date":
            birth_date = parse_birth_date(text)
            if birth_date is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_birth_date(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.save_birth_date(user_id, birth_date.isoformat())
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_biorhythm(chat_id, user_id, reply_to_message_id, birth_date)
            return True

        if state == "await_deck_choice":
            deck = parse_deck(text)
            if deck is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_deck(chat_id, reply_to_message_id, invalid_value=True)
                return True

            self.storage.save_preferred_deck(user_id, deck.key)
            self.storage.clear_conversation_state(chat_id, user_id)
            self.api.send_message(
                chat_id,
                f"Сохранил колоду: {deck.name_ru}. Теперь новые карты будут приходить в этом визуале.",
                reply_to_message_id=reply_to_message_id,
                reply_markup={"remove_keyboard": True},
            )
            return True

        if state == "await_subscription_cadence":
            cadence, hour_local, minute_local = self._parse_subscription_args(text)
            if cadence is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_subscription_cadence(chat_id, reply_to_message_id, invalid_value=True)
                return True

            if hour_local is None or minute_local is None:
                payload_hour = payload.get("hour_local")
                payload_minute = payload.get("minute_local")
                if isinstance(payload_hour, int) and isinstance(payload_minute, int):
                    hour_local = payload_hour
                    minute_local = payload_minute

            self.storage.clear_conversation_state(chat_id, user_id)
            if hour_local is None or minute_local is None:
                self.storage.save_conversation_state(
                    chat_id,
                    user_id,
                    "await_subscription_time",
                    {"cadence": cadence},
                )
                self._ask_for_subscription_time(chat_id, reply_to_message_id)
                return True

            self._save_subscription(chat_id, user_id, reply_to_message_id, cadence, hour_local, minute_local)
            return True

        if state == "await_subscription_time":
            hour_local, minute_local = self._parse_subscription_time(text)
            if hour_local is None or minute_local is None:
                if self._normalize_text(text) in MENU_TRIGGERS:
                    self._open_main_menu(chat_id, user_id, reply_to_message_id)
                    return True
                self._ask_for_subscription_time(chat_id, reply_to_message_id, invalid_value=True)
                return True

            cadence = str(payload.get("cadence", "daily"))
            self.storage.clear_conversation_state(chat_id, user_id)
            self._save_subscription(
                chat_id,
                user_id,
                reply_to_message_id,
                cadence,
                hour_local,
                minute_local,
            )
            return True

        return False

    def _open_main_menu(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        self.storage.clear_conversation_state(chat_id, user_id)
        self._send_start(chat_id, reply_to_message_id)

    def _send_start(self, chat_id: int, reply_to_message_id: int) -> None:
        caption = (
            "Привет. Я помогаю с таро, гороскопами и небольшими мистическими ритуалами.\n\n"
            "Выбери кнопку снизу или начни с фразы «карта дня»."
        )
        reply_markup = self._build_main_menu_keyboard()
        try:
            card_bytes = render_welcome_card(self._get_bot_username())
        except Exception:
            LOGGER.exception("Не удалось собрать стартовую карточку")
            self.api.send_message(
                chat_id,
                caption,
                reply_to_message_id=reply_to_message_id,
                reply_markup=reply_markup,
            )
            return

        self.api.send_photo(
            chat_id,
            caption=caption,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
            photo_bytes=card_bytes,
            filename="welcome-card.png",
        )

    def _send_help(self, chat_id: int, reply_to_message_id: int) -> None:
        help_text = (
            "Что можно сделать быстро:\n"
            "• карта дня — вытянуть карту с трактовкой\n"
            "• гороскоп — прогноз на день или неделю\n"
            "• вопрос к таро — карта под конкретный запрос\n"
            "• совместимость — сравнить два знака\n"
            "• колода — переключить визуал карт\n\n"
            "Полезные команды:\n"
            "/card, /ask, /spread3, /yesno, /relationship, /cardinfo\n"
            "/horoscope, /week, /moon, /compat, /astroalert\n"
            "/rune, /8ball, /biorhythm, /journal, /profile\n"
            "/deck, /subscribe, /unsubscribe, /setsign, /cancel\n\n"
            "Текстовые триггеры тоже работают. В группе обычные фразы видны боту, если у него отключён privacy mode в BotFather."
        )
        self.api.send_message(
            chat_id,
            help_text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=self._build_main_menu_keyboard(),
        )

    def _build_main_menu_keyboard(self) -> dict[str, object]:
        return {
            "keyboard": [list(row) for row in MAIN_MENU_KEYBOARD],
            "resize_keyboard": True,
            "input_field_placeholder": "Например: карта дня",
        }

    @staticmethod
    def _with_menu_button(rows: tuple[tuple[str, ...], ...] | list[list[str]]) -> list[list[str]]:
        keyboard = [list(row) for row in rows]
        has_menu = any(any(button == "меню" for button in row) for row in keyboard)
        if not has_menu:
            keyboard.append(["меню"])
        return keyboard

    def _configure_native_menu(self) -> None:
        try:
            self.api.set_my_commands(self._build_native_menu_commands())
        except TelegramAPIError:
            LOGGER.exception("Не удалось зарегистрировать системные команды")

        try:
            self.api.set_chat_menu_button(self._build_native_menu_button())
        except TelegramAPIError:
            LOGGER.exception("Не удалось включить нативную кнопку меню")

    def _configure_public_profile(self) -> None:
        if self.settings.bot_name:
            try:
                self.api.set_my_name(self.settings.bot_name)
            except TelegramAPIError:
                LOGGER.exception("Не удалось обновить имя бота")

        try:
            self.api.set_my_description(self.settings.bot_description)
        except TelegramAPIError:
            LOGGER.exception("Не удалось обновить описание бота")

        try:
            self.api.set_my_short_description(self.settings.bot_short_description)
        except TelegramAPIError:
            LOGGER.exception("Не удалось обновить короткое описание бота")

    @staticmethod
    def _build_native_menu_commands() -> list[dict[str, str]]:
        return [
            {"command": command, "description": description}
            for command, description in BOT_COMMANDS
        ]

    @staticmethod
    def _build_native_menu_button() -> dict[str, str]:
        return {"type": "commands"}

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
        journal_count = self.storage.count_journal_entries(user_id)
        recent_history = self.storage.get_recent_tarot_history(user_id, limit=3)
        subscription = self.storage.get_subscription(user_id)
        lines = [
            "Твой профиль",
            f"Знак зодиака: {profile.zodiac_sign or 'пока не задан'}",
            f"Дата рождения: {self._format_birth_date(profile.birth_date)}",
            f"Колода: {get_deck_info(profile.preferred_deck).name_ru}",
            f"Сохранённых раскладов: {history_count}",
            f"Записей в дневнике: {journal_count}",
        ]

        if subscription is None:
            lines.append("Рассылка: выключена")
        else:
            cadence_label = "ежедневно" if subscription.cadence == "daily" else "еженедельно"
            lines.append(
                f"Рассылка: {cadence_label} в {subscription.hour_local:02d}:{subscription.minute_local:02d}"
            )

        if recent_history:
            lines.append("")
            lines.append("Последние расклады:")
            lines.extend(self._format_history_entry(entry) for entry in recent_history)

        lines.append("")
        lines.append(
            "Чтобы обновить знак, используй /setsign. Колоду можно сменить через /deck, "
            "дневник открыть через /journal, а биоритмы посмотреть через /biorhythm."
        )
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
            self._send_horoscope(chat_id, user_id, reply_to_message_id, sign.name)
            return

        profile = self.storage.get_user_profile(user_id)
        if profile and profile.zodiac_sign:
            self._send_horoscope(chat_id, user_id, reply_to_message_id, profile.zodiac_sign)
            return

        self.storage.save_conversation_state(
            chat_id,
            user_id,
            "await_sign",
            {"next": "horoscope"},
        )
        self._ask_for_sign(chat_id, reply_to_message_id)

    def _handle_weekly_horoscope_request(
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
                    {"next": "horoscope_week"},
                )
                self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
                return

            self.storage.save_zodiac_sign(user_id, sign.name)
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_weekly_horoscope(chat_id, user_id, reply_to_message_id, sign.name)
            return

        profile = self.storage.get_user_profile(user_id)
        if profile and profile.zodiac_sign:
            self._send_weekly_horoscope(chat_id, user_id, reply_to_message_id, profile.zodiac_sign)
            return

        self.storage.save_conversation_state(
            chat_id,
            user_id,
            "await_sign",
            {"next": "horoscope_week"},
        )
        self._ask_for_sign(chat_id, reply_to_message_id)

    def _send_horoscope(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        sign_name: str,
        source: str = "manual",
    ) -> None:
        sign = parse_sign(sign_name)
        if sign is None:
            self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
            return

        message = build_daily_horoscope(sign)
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="horoscope-daily",
            title=f"Гороскоп на день: {sign.name}",
            summary=f"Дневной прогноз для знака {sign.name}.",
            source=source,
            details={"sign": sign.name},
        )
        self.api.send_message(
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _send_weekly_horoscope(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        sign_name: str,
        source: str = "manual",
    ) -> None:
        sign = parse_sign(sign_name)
        if sign is None:
            self._ask_for_sign(chat_id, reply_to_message_id, invalid_value=True)
            return

        message = build_weekly_horoscope(sign)
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="horoscope-weekly",
            title=f"Гороскоп на неделю: {sign.name}",
            summary=f"Недельный прогноз для знака {sign.name}.",
            source=source,
            details={"sign": sign.name},
        )
        self.api.send_message(
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _send_moon_calendar(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        source: str = "manual",
    ) -> None:
        message = build_lunar_calendar()
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="moon",
            title="Лунный календарь",
            summary="Фаза луны и совет на день.",
            source=source,
        )
        self.api.send_message(
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
        )

    def _handle_compatibility_request(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_text: str,
    ) -> None:
        signs = extract_signs(raw_text)
        profile = self.storage.get_user_profile(user_id)
        saved_sign = profile.zodiac_sign if profile else None

        if len(signs) >= 2:
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_compatibility_report(chat_id, reply_to_message_id, signs[0].name, signs[1].name)
            return

        if len(signs) == 1 and saved_sign:
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_compatibility_report(chat_id, reply_to_message_id, saved_sign, signs[0].name)
            return

        if len(signs) == 1:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_compatibility_second",
                {"first_sign": signs[0].name},
            )
            self._ask_for_partner_sign(chat_id, reply_to_message_id, signs[0].name)
            return

        if saved_sign:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_compatibility_second",
                {"first_sign": saved_sign},
            )
            self._ask_for_partner_sign(chat_id, reply_to_message_id, saved_sign)
            return

        self.storage.save_conversation_state(
            chat_id,
            user_id,
            "await_compatibility_first",
        )
        self._ask_for_sign(chat_id, reply_to_message_id)

    def _handle_tarot_question(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_question: str,
    ) -> None:
        question = raw_question.strip()
        if not question:
            self.storage.save_conversation_state(chat_id, user_id, "await_tarot_question")
            self._ask_for_tarot_question(chat_id, reply_to_message_id)
            return

        self.storage.clear_conversation_state(chat_id, user_id)
        self._send_tarot_question_reading(chat_id, user_id, reply_to_message_id, question)

    def _handle_biorhythm_request(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_birth_date: str,
    ) -> None:
        if raw_birth_date.strip():
            birth_date = parse_birth_date(raw_birth_date)
            if birth_date is None:
                self.storage.save_conversation_state(chat_id, user_id, "await_birth_date")
                self._ask_for_birth_date(chat_id, reply_to_message_id, invalid_value=True)
                return

            self.storage.save_birth_date(user_id, birth_date.isoformat())
            self.storage.clear_conversation_state(chat_id, user_id)
            self._send_biorhythm(chat_id, user_id, reply_to_message_id, birth_date)
            return

        profile = self.storage.get_user_profile(user_id)
        if profile and profile.birth_date:
            birth_date = parse_birth_date(profile.birth_date)
            if birth_date is not None:
                self._send_biorhythm(chat_id, user_id, reply_to_message_id, birth_date)
                return

        self.storage.save_conversation_state(chat_id, user_id, "await_birth_date")
        self._ask_for_birth_date(chat_id, reply_to_message_id)

    def _send_compatibility_report(
        self,
        chat_id: int,
        reply_to_message_id: int,
        first_sign_name: str | None,
        second_sign_name: str,
    ) -> None:
        first_sign = parse_sign(first_sign_name or "")
        second_sign = parse_sign(second_sign_name)
        if first_sign is None:
            self.api.send_message(
                chat_id,
                "Не понял первый знак для совместимости. Попробуй снова через /compat.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        if second_sign is None:
            self.api.send_message(
                chat_id,
                "Не понял второй знак для совместимости. Попробуй снова через /compat.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        report = build_compatibility_report(first_sign, second_sign)
        insight = build_compatibility_insight(first_sign, second_sign)
        share_markup = self._build_share_keyboard(
            report,
            button_text="Поделиться с партнером",
        )

        try:
            card_bytes = render_compatibility_share_card(insight, self._get_bot_username())
        except Exception:
            LOGGER.exception("Не удалось собрать карточку совместимости")
            card_bytes = None

        if card_bytes is not None:
            self.api.send_photo(
                chat_id,
                photo_bytes=card_bytes,
                caption=report,
                reply_to_message_id=reply_to_message_id,
                reply_markup=share_markup,
                filename="compatibility-card.png",
            )
            return

        self.api.send_message(
            chat_id,
            report,
            reply_to_message_id=reply_to_message_id,
            reply_markup=share_markup,
        )

    def _send_astro_alert(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        source: str = "manual",
    ) -> None:
        message = build_daily_astro_alert()
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="astroalert",
            title="Астро-алерт дня",
            summary="Короткий астро-сигнал и предупреждение на день.",
            source=source,
        )
        self.api.send_message(
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
        )

    def _send_rune_of_day(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        draw = draw_rune_of_day(user_id)
        message = format_rune_draw(draw)
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="rune",
            title=f"Руна дня: {draw.rune.name}",
            summary=draw.rune.theme,
            details={"rune": draw.rune.name},
        )
        try:
            card_bytes = render_rune_share_card(draw, self._get_bot_username())
        except Exception:
            LOGGER.exception("Не удалось собрать карточку руны")
            self.api.send_message(
                chat_id,
                message,
                reply_to_message_id=reply_to_message_id,
            )
            return

        self.api.send_photo(
            chat_id,
            caption=message,
            reply_to_message_id=reply_to_message_id,
            photo_bytes=card_bytes,
            filename="rune-card.png",
        )

    def _handle_magic_ball(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_question: str,
    ) -> None:
        question = raw_question.strip()
        if not question:
            self.storage.save_conversation_state(chat_id, user_id, "await_magic_question")
            self._ask_for_magic_question(chat_id, reply_to_message_id)
            return

        self.storage.clear_conversation_state(chat_id, user_id)
        self._send_magic_ball(chat_id, user_id, reply_to_message_id, question)

    def _send_magic_ball(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        question: str,
        source: str = "manual",
    ) -> None:
        reply = ask_magic_ball(question)
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="magic-ball",
            title="Шар предсказаний",
            summary=f"Вопрос: {question} | Ответ: {reply.answer}",
            source=source,
            details={"question": question, "answer": reply.answer},
        )
        self.api.send_message(
            chat_id,
            format_magic_ball_reply(question, reply),
            reply_to_message_id=reply_to_message_id,
        )

    def _handle_deck_selection(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_deck: str,
    ) -> None:
        if not raw_deck:
            self.storage.save_conversation_state(chat_id, user_id, "await_deck_choice")
            self._ask_for_deck(chat_id, reply_to_message_id)
            return

        deck = parse_deck(raw_deck)
        if deck is None:
            self.storage.save_conversation_state(chat_id, user_id, "await_deck_choice")
            self._ask_for_deck(chat_id, reply_to_message_id, invalid_value=True)
            return

        self.storage.save_preferred_deck(user_id, deck.key)
        self.storage.clear_conversation_state(chat_id, user_id)
        self.api.send_message(
            chat_id,
            f"Переключил колоду на «{deck.name_ru}». Следующие карты придут уже в этом визуале.",
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _send_journal(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        entries = self.storage.get_recent_journal_entries(user_id, limit=8)
        if not entries:
            self.api.send_message(
                chat_id,
                "Дневник пока пуст. Получи карту, гороскоп или руну, и я начну сохранять записи.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        month_prefix = datetime.now().strftime("%Y-%m")
        stats = self.storage.get_journal_stats(user_id, month_prefix=month_prefix)
        source_stats = self.storage.get_journal_source_stats(user_id, month_prefix=month_prefix)
        card_stats = self.storage.get_tarot_card_stats(user_id, month_prefix=month_prefix, limit=5)
        lines = ["Дневник предсказаний"]

        if stats:
            lines.append("")
            lines.append("Статистика за текущий месяц:")
            lines.extend(f"{ENTRY_LABELS.get(entry_type, entry_type)}: {total}" for entry_type, total in stats[:6])

        if source_stats:
            lines.append("")
            lines.append("Откуда пришли записи:")
            lines.extend(
                f"{self._format_journal_source_label(source)}: {total}"
                for source, total in source_stats
            )

        if card_stats:
            lines.append("")
            lines.append("Самые частые карты месяца:")
            lines.extend(f"{card_name}: {total}" for card_name, total in card_stats)

        lines.append("")
        lines.append("Последние записи:")
        lines.extend(self._format_journal_entry(entry) for entry in entries)

        self.api.send_message(
            chat_id,
            "\n".join(lines),
            reply_to_message_id=reply_to_message_id,
        )

    def _handle_subscription_request(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        raw_args: str,
    ) -> None:
        existing = self.storage.get_subscription(user_id)
        cadence, hour_local, minute_local = self._parse_subscription_args(raw_args)

        if cadence is None and existing is not None and hour_local is not None and minute_local is not None:
            cadence = existing.cadence

        if cadence is None:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_subscription_cadence",
                {
                    "hour_local": hour_local,
                    "minute_local": minute_local,
                },
            )
            self._ask_for_subscription_cadence(chat_id, reply_to_message_id, invalid_value=bool(raw_args))
            return

        if hour_local is None or minute_local is None:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_subscription_time",
                {"cadence": cadence},
            )
            self._ask_for_subscription_time(chat_id, reply_to_message_id)
            return

        self.storage.clear_conversation_state(chat_id, user_id)
        self._save_subscription(chat_id, user_id, reply_to_message_id, cadence, hour_local, minute_local)

    def _save_subscription(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        cadence: str,
        hour_local: int = 9,
        minute_local: int = 0,
    ) -> None:
        profile = self.storage.get_user_profile(user_id)
        if profile is None or not profile.zodiac_sign:
            self.storage.save_conversation_state(
                chat_id,
                user_id,
                "await_sign",
                {
                    "next": "subscribe",
                    "cadence": cadence,
                    "hour_local": hour_local,
                    "minute_local": minute_local,
                },
            )
            self._ask_for_sign(chat_id, reply_to_message_id)
            return

        self.storage.save_subscription(
            user_id=user_id,
            chat_id=chat_id,
            cadence=cadence,
            hour_local=hour_local,
            minute_local=minute_local,
        )
        cadence_label = "каждый день" if cadence == "daily" else "раз в неделю"
        self.api.send_message(
            chat_id,
            f"Рассылка включена: {cadence_label} в {hour_local:02d}:{minute_local:02d} по локальному времени сервера. "
            "Ежедневно я буду присылать гороскоп на день и карту дня, а еженедельно — гороскоп на неделю и карту недели.",
            reply_to_message_id=reply_to_message_id,
            reply_markup={"remove_keyboard": True},
        )

    def _unsubscribe(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        subscription = self.storage.get_subscription(user_id)
        if subscription is None:
            self.api.send_message(
                chat_id,
                "Активной рассылки сейчас нет.",
                reply_to_message_id=reply_to_message_id,
            )
            return

        self.storage.delete_subscription(user_id)
        self.api.send_message(
            chat_id,
            "Рассылка выключена. В любой момент можно вернуть её через /subscribe.",
            reply_to_message_id=reply_to_message_id,
        )

    def _dispatch_due_subscriptions(self) -> None:
        now_local = datetime.now().astimezone()
        for subscription in self.storage.list_active_subscriptions():
            delivery_key = self._subscription_due_key(subscription, now_local)
            if delivery_key is None or subscription.last_delivery_key == delivery_key:
                continue

            try:
                self._send_subscription_bundle(subscription)
                self.storage.update_subscription_delivery(subscription.user_id, delivery_key)
            except TelegramAPIError:
                LOGGER.exception("Не удалось отправить рассылку пользователю %s", subscription.user_id)
            except Exception:
                LOGGER.exception("Непредвиденная ошибка при рассылке пользователю %s", subscription.user_id)

    def _send_subscription_bundle(self, subscription: DeliverySubscription) -> None:
        profile = self.storage.get_user_profile(subscription.user_id)
        if profile is None or not profile.zodiac_sign:
            self.api.send_message(
                subscription.chat_id,
                "Для продолжения рассылки нужно сохранить знак зодиака через /setsign.",
            )
            return

        if subscription.cadence == "daily":
            self._send_horoscope(
                subscription.chat_id,
                subscription.user_id,
                None,
                profile.zodiac_sign,
                source="subscription",
            )
            self._send_daily_card(
                subscription.chat_id,
                subscription.user_id,
                None,
                source="subscription",
            )
            return

        self._send_weekly_horoscope(
            subscription.chat_id,
            subscription.user_id,
            None,
            profile.zodiac_sign,
            source="subscription",
        )
        self._send_weekly_card(
            subscription.chat_id,
            subscription.user_id,
            None,
            source="subscription",
        )

    def _subscription_due_key(
        self,
        subscription: DeliverySubscription,
        now_local: datetime,
    ) -> str | None:
        scheduled_reached = (
            (now_local.hour, now_local.minute)
            >= (subscription.hour_local, subscription.minute_local)
        )
        if subscription.cadence == "daily":
            if not scheduled_reached:
                return None
            return f"daily:{now_local.date().isoformat()}"

        if now_local.weekday() == 0 and not scheduled_reached:
            return None

        year, week_number, _ = now_local.isocalendar()
        return f"weekly:{year}-W{week_number:02d}"

    def _get_user_deck_key(self, user_id: int) -> str:
        profile = self.storage.get_user_profile(user_id)
        if profile is None:
            return get_deck_info().key
        return get_deck_info(profile.preferred_deck).key

    def _send_daily_card(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int | None,
        source: str = "manual",
    ) -> None:
        deck_key = self._get_user_deck_key(user_id)
        draw = draw_daily_card(deck_key=deck_key)
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="daily",
            deck_key=draw.deck_key,
            cards_payload=[draw.to_history_payload()],
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-daily",
            title=f"Карта дня: {draw.card.name_ru}",
            summary=f"{get_deck_info(draw.deck_key).name_ru}, {draw.orientation_label}.",
            source=source,
            details=draw.to_history_payload(),
        )
        caption = format_daily_caption(draw)
        share_markup = self._build_share_keyboard(caption, button_text="Поделиться картой")

        try:
            card_bytes = render_tarot_share_card(
                draw_result=draw,
                title="Карта дня",
                body_text=draw.meaning,
                bot_username=self._get_bot_username(),
            )
        except Exception:
            LOGGER.exception("Не удалось собрать карточку карты дня")
            card_bytes = None

        if card_bytes is not None:
            self.api.send_photo(
                chat_id,
                photo_bytes=card_bytes,
                caption=caption,
                reply_to_message_id=reply_to_message_id,
                reply_markup=share_markup,
                filename="daily-card.png",
            )
            return

        self.api.send_photo(
            chat_id,
            photo_url=draw.image_url,
            caption=caption,
            reply_to_message_id=reply_to_message_id,
            reply_markup=share_markup,
        )

    def _send_weekly_card(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int | None,
        source: str = "manual",
    ) -> None:
        deck_key = self._get_user_deck_key(user_id)
        draw = draw_weekly_card(deck_key=deck_key)
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="weekly",
            deck_key=draw.deck_key,
            cards_payload=[draw.to_history_payload()],
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-weekly",
            title=f"Карта недели: {draw.card.name_ru}",
            summary=f"{get_deck_info(draw.deck_key).name_ru}, {draw.orientation_label}.",
            source=source,
            details=draw.to_history_payload(),
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.image_url,
            caption=format_weekly_caption(draw),
            reply_to_message_id=reply_to_message_id,
        )

    def _send_tarot_question_reading(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        question: str,
    ) -> None:
        deck_key = self._get_user_deck_key(user_id)
        draw = draw_question_card(deck_key=deck_key)
        interpretation = self.tarot_ai.interpret(question, draw)

        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="question",
            deck_key=draw.deck_key,
            cards_payload=[draw.to_history_payload()],
            question=question,
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-question",
            title=f"Вопрос к таро: {draw.card.name_ru}",
            summary=question,
            details={
                "question": question,
                "card": draw.to_history_payload(),
                "used_ai": interpretation.used_ai,
            },
        )

        caption = format_question_caption(draw, question, interpretation.text)
        if interpretation.note:
            caption = f"{caption}\n\n{interpretation.note}"

        share_markup = self._build_share_keyboard(caption, button_text="Поделиться раскладом")
        try:
            card_bytes = render_tarot_share_card(
                draw_result=draw,
                title="Вопрос к таро",
                body_text=interpretation.text,
                bot_username=self._get_bot_username(),
                question=question,
            )
        except Exception:
            LOGGER.exception("Не удалось собрать карточку вопроса к таро")
            card_bytes = None

        if card_bytes is not None:
            self.api.send_photo(
                chat_id,
                photo_bytes=card_bytes,
                caption=caption,
                reply_to_message_id=reply_to_message_id,
                reply_markup=share_markup,
                filename="tarot-question.png",
            )
            return

        self.api.send_message(
            chat_id,
            caption,
            reply_to_message_id=reply_to_message_id,
            reply_markup=share_markup,
        )

    def _send_biorhythm(
        self,
        chat_id: int,
        user_id: int,
        reply_to_message_id: int,
        birth_date: date,
    ) -> None:
        snapshot = build_biorhythm_snapshot(birth_date)
        report = build_biorhythm_report(snapshot)
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="biorhythm",
            title="Биоритмы на сегодня",
            summary=f"Дата рождения: {birth_date.strftime('%d.%m.%Y')}",
            details={
                "birth_date": birth_date.isoformat(),
                "physical": round(snapshot.physical, 4),
                "emotional": round(snapshot.emotional, 4),
                "intellectual": round(snapshot.intellectual, 4),
            },
        )

        share_markup = self._build_share_keyboard(report, button_text="Поделиться графиком")
        try:
            card_bytes = render_biorhythm_share_card(snapshot, self._get_bot_username())
        except Exception:
            LOGGER.exception("Не удалось собрать карточку биоритмов")
            card_bytes = None

        if card_bytes is not None:
            self.api.send_photo(
                chat_id,
                photo_bytes=card_bytes,
                caption=report,
                reply_to_message_id=reply_to_message_id,
                reply_markup=share_markup,
                filename="biorhythm-card.png",
            )
            return

        self.api.send_message(
            chat_id,
            report,
            reply_to_message_id=reply_to_message_id,
            reply_markup=share_markup,
        )

    def _send_three_card_spread(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        deck_key = self._get_user_deck_key(user_id)
        draws = draw_three_card_spread(deck_key=deck_key)
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="three-card",
            deck_key=draws[0].deck_key,
            cards_payload=[draw.to_history_payload() for draw in draws],
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-three-card",
            title="Расклад на 3 карты",
            summary=", ".join(draw.card.name_ru for draw in draws),
            details={"cards": [draw.to_history_payload() for draw in draws]},
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
                    "media": draw.image_url,
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
        deck_key = self._get_user_deck_key(user_id)
        draw = draw_yes_no_card(deck_key=deck_key)
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="yes-no",
            deck_key=draw.deck_key,
            cards_payload=[draw.to_history_payload()],
            question=question,
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-yes-no",
            title=f"Да/Нет: {draw.card.name_ru}",
            summary=question or "Быстрый ответ без текста вопроса.",
            details={"question": question, "card": draw.to_history_payload()},
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.image_url,
            caption=format_yes_no_caption(draw, question=question),
            reply_to_message_id=reply_to_message_id,
        )

    def _send_relationship_card(self, chat_id: int, user_id: int, reply_to_message_id: int) -> None:
        deck_key = self._get_user_deck_key(user_id)
        draw = draw_relationship_card(deck_key=deck_key)
        self.storage.record_tarot_history(
            chat_id=chat_id,
            user_id=user_id,
            spread_type="relationship",
            deck_key=draw.deck_key,
            cards_payload=[draw.to_history_payload()],
        )
        self.storage.record_journal_entry(
            chat_id=chat_id,
            user_id=user_id,
            entry_type="tarot-relationship",
            title=f"Карта отношений: {draw.card.name_ru}",
            summary=f"{get_deck_info(draw.deck_key).name_ru}, {draw.orientation_label}.",
            details=draw.to_history_payload(),
        )
        self.api.send_photo(
            chat_id,
            photo_url=draw.image_url,
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
            self._send_card_guide(chat_id, user_id, reply_to_message_id, exact)
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
        self._send_card_guide(chat_id, user_id, reply_to_message_id, matches[0])

    def _send_card_guide(self, chat_id: int, user_id: int, reply_to_message_id: int, card: Any) -> None:
        deck_key = self._get_user_deck_key(user_id)
        self.api.send_photo(
            chat_id,
            photo_url=build_card_image_url(card, deck_key),
            caption=format_card_guide(card, deck_key=deck_key),
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
            "keyboard": self._with_menu_button(ZODIAC_KEYBOARD),
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

    def _ask_for_partner_sign(
        self,
        chat_id: int,
        reply_to_message_id: int,
        first_sign_name: str | None,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не распознал второй знак. Выбери его с клавиатуры или напиши текстом."
            if invalid_value
            else f"С кем сравнить совместимость для знака {first_sign_name}? Выбери знак с клавиатуры или напиши его текстом."
        )
        reply_markup = {
            "keyboard": self._with_menu_button(ZODIAC_KEYBOARD),
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "input_field_placeholder": "Например: Лев",
        }
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    def _ask_for_magic_question(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Нужен сам вопрос. Напиши его одним сообщением, и шар ответит."
            if invalid_value
            else "Задай вопрос, на который можно ответить коротко, и я спрошу шар предсказаний."
        )
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
        )

    def _ask_for_tarot_question(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Мне нужен сам вопрос. Напиши его одним сообщением, например: Стоит ли менять работу?"
            if invalid_value
            else "Задай конкретный вопрос к таро. Например: Стоит ли мне менять работу?"
        )
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
        )

    def _ask_for_birth_date(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не понял дату рождения. Напиши её в формате ДД.ММ.ГГГГ, например 14.08.1996."
            if invalid_value
            else "Чтобы посчитать биоритмы, пришли дату рождения в формате ДД.ММ.ГГГГ."
        )
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
        )

    def _ask_for_deck(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        deck_rows = [[deck.name_ru] for deck in get_available_decks()]
        deck_list = "\n".join(f"• {deck.name_ru} — {deck.description}" for deck in get_available_decks())
        text = (
            "Не распознал колоду. Выбери вариант с клавиатуры или напиши его текстом.\n\n"
            f"{deck_list}"
            if invalid_value
            else "Какой визуал колоды использовать?\n\n"
            f"{deck_list}"
        )
        reply_markup = {
            "keyboard": self._with_menu_button(deck_rows),
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "input_field_placeholder": "Например: Марсельская классика",
        }
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    def _ask_for_subscription_cadence(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не понял тип рассылки. Выбери «ежедневно» или «еженедельно»."
            if invalid_value
            else "Какую рассылку включить: ежедневно или еженедельно?"
        )
        reply_markup = {
            "keyboard": self._with_menu_button(SUBSCRIPTION_KEYBOARD),
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "input_field_placeholder": "Например: ежедневно",
        }
        self.api.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=reply_markup,
        )

    def _ask_for_subscription_time(
        self,
        chat_id: int,
        reply_to_message_id: int,
        invalid_value: bool = False,
    ) -> None:
        text = (
            "Не понял время. Напиши его в формате ЧЧ:ММ, например 08:30 или 19:00."
            if invalid_value
            else "Во сколько присылать рассылку? Напиши время в формате ЧЧ:ММ, например 08:30."
        )
        reply_markup = {
            "keyboard": self._with_menu_button(TIME_KEYBOARD),
            "resize_keyboard": True,
            "one_time_keyboard": True,
            "input_field_placeholder": "Например: 08:30",
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

    def _format_journal_entry(self, entry: JournalEntry) -> str:
        created = self._format_entry_date(entry.created_at)
        label = ENTRY_LABELS.get(entry.entry_type, entry.entry_type)
        source_suffix = " | по рассылке" if entry.source == "subscription" else ""
        return f"{created} — {label}: {entry.title}{source_suffix}"

    @staticmethod
    def _format_journal_source_label(source: str) -> str:
        if source == "subscription":
            return "По рассылке"
        return "Вручную"

    def _format_history_entry(self, entry: TarotHistoryEntry) -> str:
        created = self._format_entry_date(entry.created_at)
        cards = ", ".join(card["name_ru"] for card in entry.cards[:3])
        label = SPREAD_LABELS.get(entry.spread_type, entry.spread_type)
        if entry.question:
            return f"{created} — {label}: {cards} | Вопрос: {entry.question}"
        return f"{created} — {label}: {cards}"

    def _get_bot_username(self) -> str:
        if self._bot_username:
            return self._bot_username

        try:
            me = self.api.get_me()
        except TelegramAPIError:
            LOGGER.exception("Не удалось получить username бота через getMe")
            self._bot_username = "@tarot_bot"
            return self._bot_username

        username = str(me.get("username", "")).strip()
        self._bot_username = f"@{username}" if username else "@tarot_bot"
        return self._bot_username

    def _build_share_keyboard(self, text: str, button_text: str) -> dict[str, Any]:
        share_url = self._build_share_url(text)
        return {
            "inline_keyboard": [
                [
                    {
                        "text": button_text,
                        "url": share_url,
                    }
                ]
            ]
        }

    def _build_share_url(self, text: str) -> str:
        bot_username = self._get_bot_username().lstrip("@")
        bot_link = f"https://t.me/{bot_username}" if bot_username else "https://t.me"
        encoded_url = quote(bot_link, safe="")
        encoded_text = quote(text[:900], safe="")
        return f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"

    @staticmethod
    def _format_birth_date(raw_value: str | None) -> str:
        if not raw_value:
            return "пока не задана"
        parsed = parse_birth_date(raw_value)
        if parsed is None:
            return raw_value
        return parsed.strftime("%d.%m.%Y")

    @staticmethod
    def _parse_subscription_cadence(text: str) -> str | None:
        normalized = TarotHoroscopeBot._normalize_text(text)
        if normalized in {"daily", "день", "ежедневно", "каждый день"}:
            return "daily"
        if normalized in {"weekly", "неделя", "еженедельно", "раз в неделю"}:
            return "weekly"
        return None

    @staticmethod
    def _parse_subscription_time(text: str) -> tuple[int | None, int | None]:
        normalized = TarotHoroscopeBot._normalize_text(text)
        match = TIME_RE.match(normalized)
        if not match:
            return None, None

        hour_local = int(match.group("hour"))
        minute_local = int(match.group("minute"))
        if hour_local > 23 or minute_local > 59:
            return None, None
        return hour_local, minute_local

    @classmethod
    def _parse_subscription_args(cls, raw_text: str) -> tuple[str | None, int | None, int | None]:
        cadence: str | None = None
        hour_local: int | None = None
        minute_local: int | None = None

        for token in raw_text.split():
            parsed_cadence = cls._parse_subscription_cadence(token)
            if parsed_cadence is not None:
                cadence = parsed_cadence
                continue

            parsed_hour, parsed_minute = cls._parse_subscription_time(token)
            if parsed_hour is not None and parsed_minute is not None:
                hour_local = parsed_hour
                minute_local = parsed_minute

        return cadence, hour_local, minute_local

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
