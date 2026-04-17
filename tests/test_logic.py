from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from app.database import Storage
from app.horoscope import build_daily_horoscope, parse_sign
from app.tarot import (
    TAROT_DECK,
    draw_three_card_spread,
    format_card_guide,
    format_yes_no_caption,
    get_card_by_query,
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
        spread = draw_three_card_spread()
        self.assertEqual(len(spread), 3)
        self.assertEqual(
            [draw.position for draw in spread],
            ["Прошлое", "Настоящее", "Будущее"],
        )

    def test_card_guide_contains_both_orientations(self) -> None:
        guide = format_card_guide(TAROT_DECK[0])
        self.assertIn("Прямое положение:", guide)
        self.assertIn("Перевёрнутое положение:", guide)

    def test_yes_no_caption_contains_answer(self) -> None:
        caption = format_yes_no_caption(draw_three_card_spread()[0], question="Стоит ли начинать?")
        self.assertIn("Ответ:", caption)


class HoroscopeTests(unittest.TestCase):
    def test_parse_sign_supports_cases(self) -> None:
        self.assertEqual(parse_sign("овен").name, "Овен")
        self.assertEqual(parse_sign("Скорпиона").name, "Скорпион")
        self.assertIsNone(parse_sign("не знак"))

    def test_horoscope_is_deterministic_for_same_day(self) -> None:
        sign = parse_sign("дева")
        first = build_daily_horoscope(sign, for_day=date(2026, 4, 13))
        second = build_daily_horoscope(sign, for_day=date(2026, 4, 13))
        self.assertEqual(first, second)


class StorageTests(unittest.TestCase):
    def test_storage_persists_profile_state_and_history(self) -> None:
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
            profile = storage.get_user_profile(1)

            self.assertIsNotNone(profile)
            self.assertEqual(profile.zodiac_sign, "Овен")

            storage.save_conversation_state(100, 1, "await_sign", {"next": "horoscope"})
            state = storage.get_conversation_state(100, 1)
            self.assertEqual(state.state, "await_sign")
            self.assertEqual(state.payload["next"], "horoscope")

            storage.record_tarot_history(
                chat_id=100,
                user_id=1,
                spread_type="daily",
                deck_key="rider-waite",
                cards_payload=[
                    {
                        "position": "Карта дня",
                        "card_id": "major-18",
                        "name_ru": "Луна",
                        "is_reversed": False,
                        "deck_key": "rider-waite",
                    }
                ],
            )

            self.assertEqual(storage.count_tarot_history(1), 1)
            recent_history = storage.get_recent_tarot_history(1, limit=1)
            self.assertEqual(len(recent_history), 1)
            self.assertEqual(recent_history[0].cards[0]["name_ru"], "Луна")


if __name__ == "__main__":
    unittest.main()
