from __future__ import annotations

from datetime import date
from pathlib import Path
import random
import tempfile
import unittest

from app.cosmic import (
    build_compatibility_report,
    build_daily_astro_alert,
    build_lunar_calendar,
    extract_signs,
)
from app.database import Storage
from app.horoscope import build_daily_horoscope, build_weekly_horoscope, parse_sign
from app.mystic import MAGIC_BALL_REPLIES, ask_magic_ball, draw_rune_of_day, format_rune_draw
from app.tarot import (
    TAROT_DECK,
    build_card_image_url,
    draw_three_card_spread,
    draw_weekly_card,
    format_card_guide,
    format_weekly_caption,
    format_yes_no_caption,
    get_card_by_query,
    get_deck_info,
    parse_deck,
    search_cards,
)


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
        guide = format_card_guide(TAROT_DECK[0], deck_key="thoth")
        self.assertIn("Стилизованный визуал Тота", guide)
        self.assertIn("Прямое положение:", guide)
        self.assertIn("Перевёрнутое положение:", guide)

    def test_yes_no_caption_contains_answer(self) -> None:
        caption = format_yes_no_caption(draw_three_card_spread()[0], question="Стоит ли начинать?")
        self.assertIn("Ответ:", caption)

    def test_parse_deck_supports_aliases(self) -> None:
        self.assertEqual(parse_deck("тота").key, "thoth")
        self.assertEqual(parse_deck("минималистичная").key, "minimal")
        self.assertIsNone(parse_deck("неизвестная колода"))

    def test_custom_deck_uses_generated_visual_url(self) -> None:
        url = build_card_image_url(TAROT_DECK[0], "minimal")
        self.assertIn("placehold.co", url)

    def test_weekly_card_caption_mentions_week(self) -> None:
        caption = format_weekly_caption(draw_weekly_card(deck_key="thoth"))
        self.assertIn("Карта недели", caption)


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

    def test_magic_ball_returns_known_answer(self) -> None:
        reply = ask_magic_ball("Получится ли?", rng=random.Random(1))
        self.assertIn(reply.answer, {item.answer for item in MAGIC_BALL_REPLIES})


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
            storage.save_preferred_deck(1, "minimal")
            profile = storage.get_user_profile(1)

            self.assertIsNotNone(profile)
            self.assertEqual(profile.zodiac_sign, "Овен")
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
            storage.save_subscription(user_id=1, chat_id=100, cadence="daily", hour_local=9)

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


if __name__ == "__main__":
    unittest.main()
