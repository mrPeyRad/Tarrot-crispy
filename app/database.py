from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class _ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        should_suppress = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return should_suppress


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    zodiac_sign: str | None
    preferred_deck: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ConversationState:
    chat_id: int
    user_id: int
    state: str
    payload: dict[str, Any]
    updated_at: str


@dataclass(frozen=True, slots=True)
class TarotHistoryEntry:
    entry_id: int
    chat_id: int
    user_id: int
    spread_type: str
    deck_key: str
    cards: tuple[dict[str, Any], ...]
    question: str | None
    created_at: str


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, factory=_ManagedConnection)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    zodiac_sign TEXT,
                    preferred_deck TEXT NOT NULL DEFAULT 'rider-waite',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_states (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                );

                CREATE TABLE IF NOT EXISTS tarot_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    spread_type TEXT NOT NULL,
                    deck_key TEXT NOT NULL,
                    cards_json TEXT NOT NULL,
                    question TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_tarot_history_user_created
                ON tarot_history (user_id, created_at DESC);
                """
            )

    def upsert_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_profiles (
                    user_id,
                    username,
                    first_name,
                    last_name,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    updated_at = excluded.updated_at
                """,
                (user_id, username, first_name, last_name, now, now),
            )

    def get_user_profile(self, user_id: int) -> UserProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    username,
                    first_name,
                    last_name,
                    zodiac_sign,
                    preferred_deck,
                    created_at,
                    updated_at
                FROM user_profiles
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return UserProfile(
            user_id=int(row["user_id"]),
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            zodiac_sign=row["zodiac_sign"],
            preferred_deck=row["preferred_deck"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_zodiac_sign(self, user_id: int, sign_name: str) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE user_profiles
                SET zodiac_sign = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (sign_name, now, user_id),
            )

    def save_preferred_deck(self, user_id: int, deck_key: str) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE user_profiles
                SET preferred_deck = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (deck_key, now, user_id),
            )

    def save_conversation_state(
        self,
        chat_id: int,
        user_id: int,
        state: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        now = _utcnow_iso()
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_states (
                    chat_id,
                    user_id,
                    state,
                    payload_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    state = excluded.state,
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (chat_id, user_id, state, payload_json, now),
            )

    def get_conversation_state(
        self,
        chat_id: int,
        user_id: int,
    ) -> ConversationState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    chat_id,
                    user_id,
                    state,
                    payload_json,
                    updated_at
                FROM conversation_states
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            ).fetchone()

        if row is None:
            return None

        return ConversationState(
            chat_id=int(row["chat_id"]),
            user_id=int(row["user_id"]),
            state=row["state"],
            payload=json.loads(row["payload_json"]),
            updated_at=row["updated_at"],
        )

    def clear_conversation_state(self, chat_id: int, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM conversation_states
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            )

    def record_tarot_history(
        self,
        chat_id: int,
        user_id: int,
        spread_type: str,
        deck_key: str,
        cards_payload: list[dict[str, Any]],
        question: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tarot_history (
                    chat_id,
                    user_id,
                    spread_type,
                    deck_key,
                    cards_json,
                    question,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user_id,
                    spread_type,
                    deck_key,
                    json.dumps(cards_payload, ensure_ascii=False),
                    question,
                    _utcnow_iso(),
                ),
            )

    def count_tarot_history(self, user_id: int) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM tarot_history
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def get_recent_tarot_history(
        self,
        user_id: int,
        limit: int = 3,
    ) -> tuple[TarotHistoryEntry, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    user_id,
                    spread_type,
                    deck_key,
                    cards_json,
                    question,
                    created_at
                FROM tarot_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return tuple(
            TarotHistoryEntry(
                entry_id=int(row["id"]),
                chat_id=int(row["chat_id"]),
                user_id=int(row["user_id"]),
                spread_type=row["spread_type"],
                deck_key=row["deck_key"],
                cards=tuple(json.loads(row["cards_json"])),
                question=row["question"],
                created_at=row["created_at"],
            )
            for row in rows
        )
