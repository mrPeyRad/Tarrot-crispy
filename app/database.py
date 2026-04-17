from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_CACHE_SIZE_KIB = 8192
SQLITE_WAL_AUTOCHECKPOINT_PAGES = 1000


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
    birth_date: str | None
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


@dataclass(frozen=True, slots=True)
class JournalEntry:
    entry_id: int
    chat_id: int
    user_id: int
    entry_type: str
    title: str
    summary: str
    source: str
    details: dict[str, Any]
    created_at: str


@dataclass(frozen=True, slots=True)
class DeliverySubscription:
    user_id: int
    chat_id: int
    cadence: str
    hour_local: int
    minute_local: int
    enabled: bool
    last_delivery_key: str | None
    next_delivery_at: str | None
    created_at: str
    updated_at: str


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
            factory=_ManagedConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute(f"PRAGMA cache_size = {-SQLITE_CACHE_SIZE_KIB}")
        connection.execute(f"PRAGMA wal_autocheckpoint = {SQLITE_WAL_AUTOCHECKPOINT_PAGES}")
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
                    birth_date TEXT,
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

                CREATE TABLE IF NOT EXISTS prediction_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    entry_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'manual',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_prediction_journal_user_created
                ON prediction_journal (user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS delivery_subscriptions (
                    user_id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    cadence TEXT NOT NULL,
                    hour_local INTEGER NOT NULL DEFAULT 9,
                    minute_local INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_delivery_key TEXT,
                    next_delivery_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(
                connection,
                table_name="user_profiles",
                column_name="birth_date",
                column_definition="TEXT",
            )
            self._ensure_column(
                connection,
                table_name="delivery_subscriptions",
                column_name="minute_local",
                column_definition="INTEGER NOT NULL DEFAULT 0",
            )
            self._ensure_column(
                connection,
                table_name="delivery_subscriptions",
                column_name="next_delivery_at",
                column_definition="TEXT",
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_subscriptions_due
                ON delivery_subscriptions (enabled, next_delivery_at ASC)
                """
            )

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in columns:
            return
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
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
                    birth_date,
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
            birth_date=row["birth_date"],
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

    def save_birth_date(self, user_id: int, birth_date_iso: str) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE user_profiles
                SET birth_date = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (birth_date_iso, now, user_id),
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

    def get_conversation_state(self, chat_id: int, user_id: int) -> ConversationState | None:
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

    def record_journal_entry(
        self,
        chat_id: int,
        user_id: int,
        entry_type: str,
        title: str,
        summary: str,
        source: str = "manual",
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO prediction_journal (
                    chat_id,
                    user_id,
                    entry_type,
                    title,
                    summary,
                    source,
                    details_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_id,
                    user_id,
                    entry_type,
                    title,
                    summary,
                    source,
                    json.dumps(details or {}, ensure_ascii=False),
                    _utcnow_iso(),
                ),
            )

    def get_recent_journal_entries(
        self,
        user_id: int,
        limit: int = 10,
    ) -> tuple[JournalEntry, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    user_id,
                    entry_type,
                    title,
                    summary,
                    source,
                    details_json,
                    created_at
                FROM prediction_journal
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return tuple(
            JournalEntry(
                entry_id=int(row["id"]),
                chat_id=int(row["chat_id"]),
                user_id=int(row["user_id"]),
                entry_type=row["entry_type"],
                title=row["title"],
                summary=row["summary"],
                source=row["source"],
                details=json.loads(row["details_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def get_journal_stats(
        self,
        user_id: int,
        month_prefix: str | None = None,
    ) -> tuple[tuple[str, int], ...]:
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if month_prefix:
            conditions.append("substr(created_at, 1, 7) = ?")
            params.append(month_prefix)

        query = (
            "SELECT entry_type, COUNT(*) AS total "
            "FROM prediction_journal "
            f"WHERE {' AND '.join(conditions)} "
            "GROUP BY entry_type "
            "ORDER BY total DESC, entry_type ASC"
        )
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return tuple((row["entry_type"], int(row["total"])) for row in rows)

    def get_journal_source_stats(
        self,
        user_id: int,
        month_prefix: str | None = None,
    ) -> tuple[tuple[str, int], ...]:
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if month_prefix:
            conditions.append("substr(created_at, 1, 7) = ?")
            params.append(month_prefix)

        query = (
            "SELECT source, COUNT(*) AS total "
            "FROM prediction_journal "
            f"WHERE {' AND '.join(conditions)} "
            "GROUP BY source "
            "ORDER BY total DESC, source ASC"
        )
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return tuple((row["source"], int(row["total"])) for row in rows)

    def get_tarot_card_stats(
        self,
        user_id: int,
        month_prefix: str | None = None,
        limit: int = 5,
    ) -> tuple[tuple[str, int], ...]:
        conditions = ["user_id = ?"]
        params: list[Any] = [user_id]
        if month_prefix:
            conditions.append("substr(created_at, 1, 7) = ?")
            params.append(month_prefix)

        query = (
            "SELECT cards_json "
            "FROM tarot_history "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY created_at DESC"
        )
        counts: dict[str, int] = {}
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        for row in rows:
            for card in json.loads(row["cards_json"]):
                card_name = str(card.get("name_ru", "")).strip()
                if not card_name:
                    continue
                counts[card_name] = counts.get(card_name, 0) + 1

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return tuple(ranked[:limit])

    def count_journal_entries(self, user_id: int) -> int:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM prediction_journal
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return int(row["total"]) if row else 0

    def save_subscription(
        self,
        user_id: int,
        chat_id: int,
        cadence: str,
        hour_local: int = 9,
        minute_local: int = 0,
        enabled: bool = True,
        next_delivery_at: str | None = None,
    ) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO delivery_subscriptions (
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    enabled,
                    last_delivery_key,
                    next_delivery_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    cadence = excluded.cadence,
                    hour_local = excluded.hour_local,
                    minute_local = excluded.minute_local,
                    enabled = excluded.enabled,
                    next_delivery_at = excluded.next_delivery_at,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    int(enabled),
                    next_delivery_at,
                    now,
                    now,
                ),
            )

    def get_subscription(self, user_id: int) -> DeliverySubscription | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    enabled,
                    last_delivery_key,
                    next_delivery_at,
                    created_at,
                    updated_at
                FROM delivery_subscriptions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return DeliverySubscription(
            user_id=int(row["user_id"]),
            chat_id=int(row["chat_id"]),
            cadence=row["cadence"],
            hour_local=int(row["hour_local"]),
            minute_local=int(row["minute_local"]),
            enabled=bool(row["enabled"]),
            last_delivery_key=row["last_delivery_key"],
            next_delivery_at=row["next_delivery_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_active_subscriptions(self) -> tuple[DeliverySubscription, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    enabled,
                    last_delivery_key,
                    next_delivery_at,
                    created_at,
                    updated_at
                FROM delivery_subscriptions
                WHERE enabled = 1
                ORDER BY next_delivery_at ASC, updated_at ASC
                """
            ).fetchall()

        return tuple(
            DeliverySubscription(
                user_id=int(row["user_id"]),
                chat_id=int(row["chat_id"]),
                cadence=row["cadence"],
                hour_local=int(row["hour_local"]),
                minute_local=int(row["minute_local"]),
                enabled=bool(row["enabled"]),
                last_delivery_key=row["last_delivery_key"],
                next_delivery_at=row["next_delivery_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        )

    def list_due_subscriptions(
        self,
        now_utc_iso: str,
        limit: int = 200,
    ) -> tuple[DeliverySubscription, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    enabled,
                    last_delivery_key,
                    next_delivery_at,
                    created_at,
                    updated_at
                FROM delivery_subscriptions
                WHERE enabled = 1
                  AND next_delivery_at IS NOT NULL
                  AND next_delivery_at <= ?
                ORDER BY next_delivery_at ASC, updated_at ASC
                LIMIT ?
                """,
                (now_utc_iso, limit),
            ).fetchall()

        return tuple(
            DeliverySubscription(
                user_id=int(row["user_id"]),
                chat_id=int(row["chat_id"]),
                cadence=row["cadence"],
                hour_local=int(row["hour_local"]),
                minute_local=int(row["minute_local"]),
                enabled=bool(row["enabled"]),
                last_delivery_key=row["last_delivery_key"],
                next_delivery_at=row["next_delivery_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        )

    def update_subscription_delivery(
        self,
        user_id: int,
        delivery_key: str,
        next_delivery_at: str | None,
    ) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE delivery_subscriptions
                SET last_delivery_key = ?, next_delivery_at = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (delivery_key, next_delivery_at, now, user_id),
            )

    def delete_subscription(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM delivery_subscriptions
                WHERE user_id = ?
                """,
                (user_id,),
            )
