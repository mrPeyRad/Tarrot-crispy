from __future__ import annotations

from datetime import date, datetime as real_datetime, timezone
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from app.ai import TarotQuestionInterpreter, build_fallback_question_reading
from app.bot import HOROSCOPE_TRIGGERS, YES_NO_TRIGGERS, TarotHoroscopeBot
from app.biorhythm import build_biorhythm_report, build_biorhythm_snapshot, parse_birth_date
from app.config import (
    DEFAULT_BOT_DESCRIPTION,
    DEFAULT_BOT_SHORT_DESCRIPTION,
    Settings,
)
from app.cosmic import (
    build_compatibility_insight,
    build_compatibility_report,
    build_daily_astro_alert,
    build_lunar_calendar,
    extract_signs,
)
from app.database import Storage
from app.horoscope import build_daily_horoscope, build_weekly_horoscope, parse_sign
from app.mystic import MAGIC_BALL_REPLIES, ask_magic_ball, draw_rune_of_day, format_rune_draw, get_rune_symbol
from app.share_cards import (
    render_biorhythm_share_card,
    render_compatibility_share_card,
    render_rune_share_card,
    render_tarot_share_card,
    render_welcome_card,
)
from app.tarot import (
    CardDraw,
    TAROT_DECK,
    build_card_image_url,
    draw_question_card,
    draw_three_card_spread,
    draw_weekly_card,
    format_card_guide,
    format_question_caption,
    format_weekly_caption,
    format_yes_no_caption,
    get_card_by_query,
    get_deck_info,
    parse_deck,
    search_cards,
)
from app.telegram_api import TelegramAPIError

from PIL import Image


class TarotTests(unittest.TestCase):
    def test_deck_has_full_78_cards(self) -> None:
        self.assertEqual(len(TAROT_DECK), 78)
        self.assertEqual(len({card.card_id for card in TAROT_DECK}), 78)

    def test_card_lookup_supports_russian_names(self) -> None:
        card = get_card_by_query("луна")
        self.assertIsNotNone(card)
        self.assertEqual(card.name_ru, "Луна")

    def test_partial_search_returns_matches(self) -> None:
        matches = search_cards("кубков")
        self.assertGreaterEqual(len(matches), 2)

    def test_three_card_spread_has_distinct_positions(self) -> None:
        spread = draw_three_card_spread(deck_key="minimal")
        self.assertEqual(len(spread), 3)
        self.assertEqual(
            [draw.position for draw in spread],
            ["Прошлое", "Настоящее", "Будущее"],
        )
        self.assertTrue(all(draw.deck_key == "minimal" for draw in spread))

    def test_card_guide_uses_selected_deck_name(self) -> None:
        guide = format_card_guide(TAROT_DECK[0], deck_key="minimal")
        self.assertIn("Минималистичный визуал", guide)
        self.assertIn("Прямое положение:", guide)
        self.assertIn("Перевёрнутое положение:", guide)

    def test_yes_no_caption_contains_answer(self) -> None:
        caption = format_yes_no_caption(draw_three_card_spread()[0], question="Стоит ли начинать?")
        self.assertIn("Ответ:", caption)

    def test_parse_deck_supports_aliases(self) -> None:
        self.assertEqual(parse_deck("минималистичная").key, "minimal")
        self.assertEqual(parse_deck("марсель").key, "marseille")
        self.assertEqual(parse_deck("sola busca").key, "sola-busca")
        self.assertIsNone(parse_deck("тота"))
        self.assertIsNone(parse_deck("неизвестная колода"))

    def test_custom_deck_uses_real_card_image_url(self) -> None:
        url = build_card_image_url(TAROT_DECK[0], "minimal")
        self.assertEqual(url, TAROT_DECK[0].image_url)

    def test_marseille_deck_uses_historical_urls(self) -> None:
        fool = TAROT_DECK[0]
        ace_of_cups = get_card_by_query("Туз Кубков")
        queen_of_cups = get_card_by_query("Королева Кубков")
        self.assertIsNotNone(ace_of_cups)
        self.assertIsNotNone(queen_of_cups)
        self.assertIn("TT%20Tarot.png", build_card_image_url(fool, "marseille"))
        self.assertIn("1C%20Tarot.png", build_card_image_url(ace_of_cups, "marseille"))
        self.assertIn("QC%20Tarot.png", build_card_image_url(queen_of_cups, "marseille"))

    def test_sola_busca_deck_uses_historical_urls(self) -> None:
        fool = TAROT_DECK[0]
        ace_of_cups = get_card_by_query("Туз Кубков")
        queen_of_pentacles = get_card_by_query("Королева Пентаклей")
        self.assertIsNotNone(ace_of_cups)
        self.assertIsNotNone(queen_of_pentacles)
        self.assertIn("Sola%20Busca%20tarot%20card%2000.jpg", build_card_image_url(fool, "sola-busca"))
        self.assertIn("Sola%20Busca%20tarot%20card%2022.jpg", build_card_image_url(ace_of_cups, "sola-busca"))
        self.assertIn(
            "Sola%20Busca%20tarot%20card%2048.jpg",
            build_card_image_url(queen_of_pentacles, "sola-busca"),
        )

    def test_weekly_card_caption_mentions_week(self) -> None:
        caption = format_weekly_caption(draw_weekly_card(deck_key="minimal"))
        self.assertIn("Карта недели", caption)

    def test_question_caption_contains_question_and_card_name(self) -> None:
        draw = CardDraw(position="Вопрос к таро", card=TAROT_DECK[0], is_reversed=False, deck_key="minimal")
        caption = format_question_caption(draw, "Стоит ли менять работу?", "Карта просит не бояться нового.")
        self.assertIn("Стоит ли менять работу?", caption)
        self.assertIn(TAROT_DECK[0].name_ru, caption)


class HoroscopeTests(unittest.TestCase):
    def test_parse_sign_supports_cases(self) -> None:
        self.assertEqual(parse_sign("овен").name, "Овен")
        self.assertEqual(parse_sign("Скорпиона").name, "Скорпион")
        self.assertIsNone(parse_sign("не знак"))

    def test_daily_horoscope_is_deterministic_for_same_day(self) -> None:
        sign = parse_sign("дева")
        first = build_daily_horoscope(sign, for_day=date(2026, 4, 13))
        second = build_daily_horoscope(sign, for_day=date(2026, 4, 13))
        self.assertEqual(first, second)

    def test_weekly_horoscope_is_deterministic_for_same_week(self) -> None:
        sign = parse_sign("дева")
        first = build_weekly_horoscope(sign, for_day=date(2026, 4, 13))
        second = build_weekly_horoscope(sign, for_day=date(2026, 4, 16))
        self.assertEqual(first, second)

    def test_extract_signs_finds_two_signs_in_text(self) -> None:
        signs = extract_signs("совместимость овен и лев")
        self.assertEqual([sign.name for sign in signs], ["Овен", "Лев"])

    def test_lunar_calendar_contains_phase_and_date(self) -> None:
        calendar_text = build_lunar_calendar(for_day=date(2026, 4, 17))
        self.assertIn("Лунный календарь", calendar_text)
        self.assertIn("Фаза:", calendar_text)
        self.assertIn("17 апреля 2026", calendar_text)

    def test_compatibility_report_contains_both_signs_and_percent(self) -> None:
        report = build_compatibility_report(parse_sign("овен"), parse_sign("лев"))
        self.assertIn("Овен + Лев", report)
        self.assertIn("Процент совместимости:", report)

    def test_compatibility_insight_exposes_score_and_summary(self) -> None:
        insight = build_compatibility_insight(parse_sign("овен"), parse_sign("лев"))
        self.assertGreaterEqual(insight.score, 35)
        self.assertTrue(insight.strength)
        self.assertIn("Овен", insight.first.name)
        self.assertTrue(insight.summary)

    def test_astro_alert_is_deterministic_for_same_day(self) -> None:
        first = build_daily_astro_alert(for_day=date(2026, 4, 17))
        second = build_daily_astro_alert(for_day=date(2026, 4, 17))
        self.assertEqual(first, second)


class MysticTests(unittest.TestCase):
    def test_rune_of_day_is_deterministic_for_same_user_and_day(self) -> None:
        first = draw_rune_of_day(user_id=77, for_day=date(2026, 4, 17))
        second = draw_rune_of_day(user_id=77, for_day=date(2026, 4, 17))
        self.assertEqual(first.rune.name, second.rune.name)
        self.assertIn(first.rune.name, format_rune_draw(first))

    def test_get_rune_symbol_returns_elder_futhark_glyph(self) -> None:
        draw = draw_rune_of_day(user_id=77, for_day=date(2026, 4, 17))
        symbol = get_rune_symbol(draw.rune)
        self.assertEqual(len(symbol), 1)
        self.assertIn(symbol, format_rune_draw(draw))

    def test_magic_ball_returns_known_answer(self) -> None:
        reply = ask_magic_ball("Получится ли?", rng=random.Random(1))
        self.assertIn(reply.answer, {item.answer for item in MAGIC_BALL_REPLIES})


class BiorhythmTests(unittest.TestCase):
    def test_parse_birth_date_supports_multiple_formats(self) -> None:
        self.assertEqual(parse_birth_date("14.08.1996"), date(1996, 8, 14))
        self.assertEqual(parse_birth_date("1996-08-14"), date(1996, 8, 14))
        self.assertIsNone(parse_birth_date("31.31.1996"))

    def test_biorhythm_snapshot_contains_seven_points(self) -> None:
        snapshot = build_biorhythm_snapshot(date(1996, 8, 14), target_date=date(2026, 4, 17))
        self.assertEqual(len(snapshot.points), 7)
        self.assertIn("Биоритмы", build_biorhythm_report(snapshot))


class ShareCardTests(unittest.TestCase):
    def test_tarot_share_card_renders_png(self) -> None:
        draw = CardDraw(position="Карта дня", card=TAROT_DECK[0], is_reversed=False, deck_key="minimal")
        with patch("app.share_cards._load_tarot_art", return_value=Image.new("RGB", (320, 640), "#ffffff")):
            png = render_tarot_share_card(draw, "Карта дня", "Смелее смотри в новое.", "@test_bot")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_compatibility_share_card_renders_png(self) -> None:
        insight = build_compatibility_insight(parse_sign("овен"), parse_sign("лев"))
        png = render_compatibility_share_card(insight, "@test_bot")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_biorhythm_share_card_renders_png(self) -> None:
        snapshot = build_biorhythm_snapshot(date(1996, 8, 14), target_date=date(2026, 4, 17))
        png = render_biorhythm_share_card(snapshot, "@test_bot")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_welcome_card_renders_png(self) -> None:
        png = render_welcome_card("@test_bot")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_rune_share_card_renders_png(self) -> None:
        draw = draw_rune_of_day(user_id=77, for_day=date(2026, 4, 17))
        png = render_rune_share_card(draw, "@test_bot")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


class AITests(unittest.TestCase):
    def test_fallback_question_reading_mentions_card_and_question(self) -> None:
        draw = draw_question_card(deck_key="minimal")
        text = build_fallback_question_reading("Стоит ли менять работу?", draw)
        self.assertIn("Стоит ли менять работу?", text)
        self.assertIn(draw.card.name_ru, text)

    def test_interpreter_falls_back_when_ai_call_raises(self) -> None:
        draw = draw_question_card(deck_key="minimal")
        interpreter = TarotQuestionInterpreter(api_key="test-key", model="gpt-5-mini")

        class FakeResponses:
            def create(self, **_: object) -> object:
                raise RuntimeError("boom")

        class FakeClient:
            responses = FakeResponses()

        with patch.object(interpreter, "_get_client", return_value=FakeClient()):
            result = interpreter.interpret("Стоит ли менять работу?", draw)

        self.assertFalse(result.used_ai)
        self.assertIn(draw.card.name_ru, result.text)
        self.assertEqual(
            result.note,
            "AI временно недоступен, показал базовую трактовку по карте.",
        )


class StorageTests(unittest.TestCase):
    def test_storage_persists_profile_history_journal_and_subscription(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "bot.sqlite3"
            storage = Storage(db_path)

            storage.upsert_user(
                user_id=1,
                username="tester",
                first_name="Test",
                last_name=None,
            )
            storage.save_zodiac_sign(1, "Овен")
            storage.save_birth_date(1, "1996-08-14")
            storage.save_preferred_deck(1, "minimal")
            profile = storage.get_user_profile(1)

            self.assertIsNotNone(profile)
            self.assertEqual(profile.zodiac_sign, "Овен")
            self.assertEqual(profile.birth_date, "1996-08-14")
            self.assertEqual(get_deck_info(profile.preferred_deck).key, "minimal")

            storage.save_conversation_state(100, 1, "await_sign", {"next": "horoscope"})
            state = storage.get_conversation_state(100, 1)
            self.assertEqual(state.state, "await_sign")
            self.assertEqual(state.payload["next"], "horoscope")

            storage.record_tarot_history(
                chat_id=100,
                user_id=1,
                spread_type="daily",
                deck_key="minimal",
                cards_payload=[
                    {
                        "position": "Карта дня",
                        "card_id": "major-18",
                        "name_ru": "Луна",
                        "is_reversed": False,
                        "deck_key": "minimal",
                    }
                ],
            )

            storage.record_journal_entry(
                chat_id=100,
                user_id=1,
                entry_type="horoscope-daily",
                title="Гороскоп на день: Овен",
                summary="Дневной прогноз",
                source="manual",
            )
            storage.save_subscription(
                user_id=1,
                chat_id=100,
                cadence="daily",
                hour_local=9,
                minute_local=30,
            )

            self.assertEqual(storage.count_tarot_history(1), 1)
            recent_history = storage.get_recent_tarot_history(1, limit=1)
            self.assertEqual(len(recent_history), 1)
            self.assertEqual(recent_history[0].cards[0]["name_ru"], "Луна")

            journal_entries = storage.get_recent_journal_entries(1, limit=1)
            self.assertEqual(len(journal_entries), 1)
            self.assertEqual(journal_entries[0].entry_type, "horoscope-daily")

            stats = dict(storage.get_journal_stats(1))
            self.assertEqual(stats["horoscope-daily"], 1)

            subscription = storage.get_subscription(1)
            self.assertIsNotNone(subscription)
            self.assertEqual(subscription.cadence, "daily")
            self.assertEqual(subscription.hour_local, 9)
            self.assertEqual(subscription.minute_local, 30)

            storage.record_tarot_history(
                chat_id=100,
                user_id=1,
                spread_type="weekly",
                deck_key="minimal",
                cards_payload=[
                    {
                        "position": "Карта недели",
                        "card_id": "major-18",
                        "name_ru": "Луна",
                        "is_reversed": False,
                        "deck_key": "minimal",
                    },
                    {
                        "position": "Подсказка",
                        "card_id": "major-19",
                        "name_ru": "Солнце",
                        "is_reversed": False,
                        "deck_key": "minimal",
                    },
                ],
            )
            storage.record_journal_entry(
                chat_id=100,
                user_id=1,
                entry_type="tarot-weekly",
                title="Карта недели: Луна",
                summary="Недельный расклад",
                source="subscription",
            )

            active_subscriptions = storage.list_active_subscriptions()
            self.assertEqual(len(active_subscriptions), 1)
            self.assertEqual(active_subscriptions[0].minute_local, 30)

            source_stats = dict(storage.get_journal_source_stats(1))
            self.assertEqual(source_stats["manual"], 1)
            self.assertEqual(source_stats["subscription"], 1)

            current_month = storage.get_recent_journal_entries(1, limit=1)[0].created_at[:7]
            month_source_stats = dict(storage.get_journal_source_stats(1, month_prefix=current_month))
            self.assertEqual(month_source_stats["manual"], 1)
            self.assertEqual(month_source_stats["subscription"], 1)

            card_stats = dict(storage.get_tarot_card_stats(1))
            self.assertEqual(card_stats["Луна"], 2)
            self.assertEqual(card_stats["Солнце"], 1)
            self.assertEqual(storage.get_tarot_card_stats(1, limit=1), (("Луна", 2),))

    def test_storage_retries_incoming_updates_without_losing_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "bot.sqlite3"
            storage = Storage(db_path)
            update = {"update_id": 42, "message": {"message_id": 1, "text": "/start"}}

            self.assertTrue(storage.enqueue_incoming_update(update))
            self.assertFalse(storage.enqueue_incoming_update(update))

            claimed = storage.claim_next_incoming_update()
            self.assertEqual(claimed["update_id"], 42)
            self.assertIsNone(storage.claim_next_incoming_update())

            storage.release_incoming_update(42, "RuntimeError: boom")
            claimed_again = storage.claim_next_incoming_update()
            self.assertEqual(claimed_again["update_id"], 42)

            storage.mark_incoming_update_done(42)
            self.assertIsNone(storage.claim_next_incoming_update())

    def test_storage_tracks_subscription_delivery_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "bot.sqlite3"
            storage = Storage(db_path)

            first_payload = {
                "position": "Карта дня",
                "card_id": "major-18",
                "name_ru": "Луна",
                "is_reversed": False,
                "deck_key": "minimal",
            }
            second_payload = {
                "position": "Карта дня",
                "card_id": "major-19",
                "name_ru": "Солнце",
                "is_reversed": True,
                "deck_key": "rider-waite",
            }

            delivery = storage.ensure_subscription_delivery(
                user_id=1,
                delivery_key="daily:2026-04-21",
                cadence="daily",
                sign_name="Овен",
                card_payload=first_payload,
            )
            self.assertEqual(delivery.card_payload["card_id"], "major-18")

            same_delivery = storage.ensure_subscription_delivery(
                user_id=1,
                delivery_key="daily:2026-04-21",
                cadence="daily",
                sign_name="Телец",
                card_payload=second_payload,
            )
            self.assertEqual(same_delivery.card_payload["card_id"], "major-18")
            self.assertEqual(same_delivery.sign_name, "Овен")

            partial = storage.mark_subscription_delivery_part(1, "daily:2026-04-21", "horoscope")
            self.assertIsNotNone(partial)
            self.assertTrue(partial.horoscope_sent)
            self.assertFalse(partial.card_sent)
            self.assertFalse(partial.is_complete)

            completed = storage.mark_subscription_delivery_part(1, "daily:2026-04-21", "card")
            self.assertIsNotNone(completed)
            self.assertTrue(completed.horoscope_sent)
            self.assertTrue(completed.card_sent)
            self.assertTrue(completed.is_complete)
            self.assertIsNotNone(completed.completed_at)


class BotParsingTests(unittest.TestCase):
    def test_process_pending_updates_marks_successful_update_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = Storage(Path(tmp_dir) / "bot.sqlite3")
            storage.enqueue_incoming_update(
                {"update_id": 7, "message": {"message_id": 1, "text": "/start"}}
            )

            bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
            bot.storage = storage
            handled: list[int] = []
            bot._handle_update = lambda update: handled.append(update["update_id"])

            processed = bot._process_pending_updates()

            self.assertEqual(processed, 1)
            self.assertEqual(handled, [7])
            self.assertIsNone(storage.claim_next_incoming_update())

    def test_process_pending_updates_requeues_failed_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = Storage(Path(tmp_dir) / "bot.sqlite3")
            storage.enqueue_incoming_update(
                {"update_id": 8, "message": {"message_id": 1, "text": "/ask hi"}}
            )

            bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
            bot.storage = storage

            def broken_handler(update: dict[str, object]) -> None:
                raise RuntimeError(f"failed {update['update_id']}")

            bot._handle_update = broken_handler

            processed = bot._process_pending_updates()

            self.assertEqual(processed, 0)
            claimed_again = storage.claim_next_incoming_update()
            self.assertIsNotNone(claimed_again)
            self.assertEqual(claimed_again["update_id"], 8)

    def test_dispatch_due_subscriptions_resumes_partial_daily_delivery(self) -> None:
        class FakeAPI:
            def __init__(self) -> None:
                self.messages: list[dict[str, object]] = []
                self.photos: list[dict[str, object]] = []
                self.fail_first_photo = True

            def send_message(
                self,
                chat_id: int,
                text: str,
                reply_to_message_id: int | None = None,
                reply_markup: dict[str, object] | None = None,
            ) -> dict[str, object]:
                self.messages.append(
                    {
                        "chat_id": chat_id,
                        "text": text,
                        "reply_to_message_id": reply_to_message_id,
                        "reply_markup": reply_markup,
                    }
                )
                return {"ok": True}

            def send_photo(
                self,
                chat_id: int,
                photo_url: str | None = None,
                caption: str = "",
                reply_to_message_id: int | None = None,
                reply_markup: dict[str, object] | None = None,
                photo_bytes: bytes | None = None,
                filename: str = "card.png",
            ) -> dict[str, object]:
                if self.fail_first_photo:
                    self.fail_first_photo = False
                    raise TelegramAPIError("photo failed")

                self.photos.append(
                    {
                        "chat_id": chat_id,
                        "photo_url": photo_url,
                        "caption": caption,
                        "reply_to_message_id": reply_to_message_id,
                        "reply_markup": reply_markup,
                        "photo_bytes": photo_bytes,
                        "filename": filename,
                    }
                )
                return {"ok": True}

        fake_now = real_datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)
        delivery_key = "daily:2026-04-21"
        fixed_draw = CardDraw(
            position="Карта дня",
            card=TAROT_DECK[18],
            is_reversed=False,
            deck_key="minimal",
        )

        class FrozenDateTime(real_datetime):
            @classmethod
            def now(cls, tz: timezone | None = None) -> real_datetime:
                if tz is not None:
                    return fake_now.astimezone(tz)
                return fake_now

        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = Storage(Path(tmp_dir) / "bot.sqlite3")
            storage.upsert_user(
                user_id=1,
                username="tester",
                first_name="Test",
                last_name="User",
            )
            storage.save_zodiac_sign(1, "Овен")
            storage.save_subscription(
                user_id=1,
                chat_id=100,
                cadence="daily",
                hour_local=9,
                minute_local=0,
            )

            bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
            bot.storage = storage
            bot.api = FakeAPI()
            bot._bot_username = "@wisdom_bot"

            with (
                patch("app.bot.datetime", FrozenDateTime),
                patch("app.bot.draw_daily_card", return_value=fixed_draw) as draw_mock,
                patch("app.bot.render_tarot_share_card", return_value=None),
            ):
                bot._dispatch_due_subscriptions()

                first_delivery = storage.get_subscription_delivery(1, delivery_key)
                self.assertIsNotNone(first_delivery)
                self.assertTrue(first_delivery.horoscope_sent)
                self.assertFalse(first_delivery.card_sent)
                self.assertEqual(first_delivery.card_payload["card_id"], fixed_draw.card.card_id)
                self.assertEqual(len(bot.api.messages), 1)
                self.assertEqual(len(bot.api.photos), 0)
                self.assertIsNone(storage.get_subscription(1).last_delivery_key)

                bot._dispatch_due_subscriptions()

            final_delivery = storage.get_subscription_delivery(1, delivery_key)
            self.assertIsNotNone(final_delivery)
            self.assertTrue(final_delivery.is_complete)
            self.assertEqual(storage.get_subscription(1).last_delivery_key, delivery_key)
            self.assertEqual(len(bot.api.messages), 1)
            self.assertEqual(len(bot.api.photos), 1)
            self.assertEqual(draw_mock.call_count, 1)

            entry_types = [entry.entry_type for entry in storage.get_recent_journal_entries(1, limit=10)]
            self.assertEqual(entry_types.count("horoscope-daily"), 1)
            self.assertEqual(entry_types.count("tarot-daily"), 1)

    def test_configure_public_profile_pushes_descriptions_to_telegram(self) -> None:
        class FakeAPI:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def set_my_name(self, name: str) -> bool:
                self.calls.append(("name", name))
                return True

            def set_my_description(self, description: str) -> bool:
                self.calls.append(("description", description))
                return True

            def set_my_short_description(self, short_description: str) -> bool:
                self.calls.append(("short_description", short_description))
                return True

        bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
        bot.settings = Settings(
            bot_token="123:abc",
            bot_username="@wisdom_bot",
            bot_name="Wisdom Bot",
            bot_description="Описание для пустого чата",
            bot_short_description="Короткое описание для превью ссылки",
            database_path=Path("bot.sqlite3"),
            openai_api_key=None,
            openai_model="gpt-5-mini",
        )
        bot.api = FakeAPI()

        bot._configure_public_profile()

        self.assertEqual(
            bot.api.calls,
            [
                ("name", "Wisdom Bot"),
                ("description", "Описание для пустого чата"),
                ("short_description", "Короткое описание для превью ссылки"),
            ],
        )

    def test_settings_from_env_uses_default_bot_profile_texts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict("os.environ", {}, clear=True):
            project_root = Path(tmp_dir)
            (project_root / ".env").write_text(
                "BOT_TOKEN=123:abc\nBOT_USERNAME=wisdom_bot\n",
                encoding="utf-8",
            )

            settings = Settings.from_env(project_root)

        self.assertIsNone(settings.bot_name)
        self.assertEqual(settings.bot_description, DEFAULT_BOT_DESCRIPTION)
        self.assertEqual(settings.bot_short_description, DEFAULT_BOT_SHORT_DESCRIPTION)

    def test_settings_from_env_detects_webhook_mode_from_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict("os.environ", {}, clear=True):
            project_root = Path(tmp_dir)
            (project_root / ".env").write_text(
                (
                    "BOT_TOKEN=123:abc\n"
                    "WEBHOOK_URL=https://bot.example.com/custom/hook\n"
                ),
                encoding="utf-8",
            )

            settings = Settings.from_env(project_root)

        self.assertEqual(settings.run_mode, "webhook")
        self.assertEqual(settings.webhook_path, "/custom/hook")

    def test_settings_from_env_normalizes_explicit_webhook_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, patch.dict("os.environ", {}, clear=True):
            project_root = Path(tmp_dir)
            (project_root / ".env").write_text(
                (
                    "BOT_TOKEN=123:abc\n"
                    "BOT_MODE=webhook\n"
                    "WEBHOOK_URL=https://bot.example.com\n"
                    "WEBHOOK_PATH=telegram/webhook/\n"
                ),
                encoding="utf-8",
            )

            settings = Settings.from_env(project_root)

        self.assertEqual(settings.run_mode, "webhook")
        self.assertEqual(settings.webhook_path, "/telegram/webhook")

    def test_build_main_menu_keyboard_is_not_persistent(self) -> None:
        bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
        markup = bot._build_main_menu_keyboard()
        self.assertNotIn("is_persistent", markup)

    def test_build_main_menu_keyboard_does_not_append_extra_menu_row(self) -> None:
        bot = TarotHoroscopeBot.__new__(TarotHoroscopeBot)
        markup = bot._build_main_menu_keyboard()
        self.assertNotIn("меню", [button for row in markup["keyboard"] for button in row])
        self.assertEqual(
            markup["keyboard"],
            [
                ["карта дня", "гороскоп на день"],
                ["быстрый ответ", "шар предсказаний"],
            ],
        )

    def test_new_quick_menu_labels_are_supported_by_triggers(self) -> None:
        self.assertIn("гороскоп на день", HOROSCOPE_TRIGGERS)
        self.assertIn("быстрый ответ", YES_NO_TRIGGERS)

    def test_with_menu_button_appends_menu_row(self) -> None:
        self.assertEqual(
            TarotHoroscopeBot._with_menu_button((("Овен", "Телец"),)),
            [["Овен", "Телец"], ["меню"]],
        )

    def test_with_menu_button_does_not_duplicate_menu(self) -> None:
        self.assertEqual(
            TarotHoroscopeBot._with_menu_button((("колода", "меню"),)),
            [["колода", "меню"]],
        )

    def test_build_native_menu_commands_exposes_menu_entry(self) -> None:
        commands = TarotHoroscopeBot._build_native_menu_commands()
        self.assertIn(
            {"command": "menu", "description": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u0433\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e"},
            commands,
        )
        self.assertIn(
            {"command": "deck", "description": "\u0421\u043c\u0435\u043d\u0438\u0442\u044c \u0432\u0438\u0437\u0443\u0430\u043b \u043a\u043e\u043b\u043e\u0434\u044b"},
            commands,
        )

    def test_build_native_menu_button_uses_commands_type(self) -> None:
        self.assertEqual(
            TarotHoroscopeBot._build_native_menu_button(),
            {"type": "commands"},
        )

    def test_build_native_menu_commands_use_readable_russian_descriptions(self) -> None:
        commands = TarotHoroscopeBot._build_native_menu_commands()
        self.assertIn(
            {"command": "menu", "description": "Открыть главное меню"},
            commands,
        )
        self.assertIn(
            {"command": "deck", "description": "Сменить визуал колоды"},
            commands,
        )

    def test_parse_subscription_time_supports_hh_mm(self) -> None:
        self.assertEqual(TarotHoroscopeBot._parse_subscription_time("08:30"), (8, 30))
        self.assertEqual(TarotHoroscopeBot._parse_subscription_time(" 19:00 "), (19, 0))

    def test_parse_subscription_time_rejects_invalid_values(self) -> None:
        self.assertEqual(TarotHoroscopeBot._parse_subscription_time("24:00"), (None, None))
        self.assertEqual(TarotHoroscopeBot._parse_subscription_time("9:7"), (None, None))

    def test_parse_subscription_args_supports_any_order(self) -> None:
        self.assertEqual(
            TarotHoroscopeBot._parse_subscription_args("daily 08:30"),
            ("daily", 8, 30),
        )
        self.assertEqual(
            TarotHoroscopeBot._parse_subscription_args("08:30 weekly"),
            ("weekly", 8, 30),
        )


if __name__ == "__main__":
    unittest.main()
