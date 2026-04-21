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
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SubscriptionDelivery:
    user_id: int
    delivery_key: str
    cadence: str
    sign_name: str
    card_payload: dict[str, Any]
    horoscope_sent: bool
    card_sent: bool
    completed_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_complete(self) -> bool:
        return self.horoscope_sent and self.card_sent


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, factory=_ManagedConnection)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incoming_updates (
                    update_id INTEGER PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_incoming_updates_status_update
                ON incoming_updates (status, update_id ASC);

                CREATE TABLE IF NOT EXISTS subscription_deliveries (
                    user_id INTEGER NOT NULL,
                    delivery_key TEXT NOT NULL,
                    cadence TEXT NOT NULL,
                    sign_name TEXT NOT NULL,
                    card_json TEXT NOT NULL,
                    horoscope_sent INTEGER NOT NULL DEFAULT 0,
                    card_sent INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, delivery_key)
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
            connection.execute(
                """
                UPDATE incoming_updates
                SET status = 'pending', updated_at = ?
                WHERE status = 'processing'
                """,
                (_utcnow_iso(),),
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

    def enqueue_incoming_update(self, update: dict[str, Any]) -> bool:
        update_id = update.get("update_id")
        if not isinstance(update_id, int):
            return False

        now = _utcnow_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO incoming_updates (
                    update_id,
                    payload_json,
                    status,
                    attempt_count,
                    last_error,
                    created_at,
                    updated_at
                ) VALUES (?, ?, 'pending', 0, NULL, ?, ?)
                ON CONFLICT(update_id) DO NOTHING
                """,
                (
                    update_id,
                    json.dumps(update, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return cursor.rowcount > 0

    def claim_next_incoming_update(self) -> dict[str, Any] | None:
        now = _utcnow_iso()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT update_id, payload_json
                FROM incoming_updates
                WHERE status = 'pending'
                ORDER BY update_id ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None

            cursor = connection.execute(
                """
                UPDATE incoming_updates
                SET status = 'processing',
                    attempt_count = attempt_count + 1,
                    updated_at = ?
                WHERE update_id = ? AND status = 'pending'
                """,
                (now, int(row["update_id"])),
            )
            if cursor.rowcount == 0:
                return None

        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            self.mark_incoming_update_done(int(row["update_id"]))
            return None
        if not isinstance(payload, dict):
            self.mark_incoming_update_done(int(row["update_id"]))
            return None
        payload.setdefault("update_id", int(row["update_id"]))
        return payload

    def mark_incoming_update_done(self, update_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE incoming_updates
                SET status = 'done',
                    last_error = NULL,
                    updated_at = ?
                WHERE update_id = ?
                """,
                (_utcnow_iso(), update_id),
            )

    def release_incoming_update(self, update_id: int, error_message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE incoming_updates
                SET status = 'pending',
                    last_error = ?,
                    updated_at = ?
                WHERE update_id = ?
                """,
                (error_message[:1000], _utcnow_iso(), update_id),
            )

    @staticmethod
    def _row_to_subscription_delivery(row: sqlite3.Row) -> SubscriptionDelivery:
        return SubscriptionDelivery(
            user_id=int(row["user_id"]),
            delivery_key=row["delivery_key"],
            cadence=row["cadence"],
            sign_name=row["sign_name"],
            card_payload=json.loads(row["card_json"]),
            horoscope_sent=bool(row["horoscope_sent"]),
            card_sent=bool(row["card_sent"]),
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_subscription_delivery(
        self,
        user_id: int,
        delivery_key: str,
    ) -> SubscriptionDelivery | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    delivery_key,
                    cadence,
                    sign_name,
                    card_json,
                    horoscope_sent,
                    card_sent,
                    completed_at,
                    created_at,
                    updated_at
                FROM subscription_deliveries
                WHERE user_id = ? AND delivery_key = ?
                """,
                (user_id, delivery_key),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_subscription_delivery(row)

    def ensure_subscription_delivery(
        self,
        user_id: int,
        delivery_key: str,
        cadence: str,
        sign_name: str,
        card_payload: dict[str, Any],
    ) -> SubscriptionDelivery:
        existing = self.get_subscription_delivery(user_id, delivery_key)
        if existing is not None:
            return existing

        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subscription_deliveries (
                    user_id,
                    delivery_key,
                    cadence,
                    sign_name,
                    card_json,
                    horoscope_sent,
                    card_sent,
                    completed_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, 0, NULL, ?, ?)
                ON CONFLICT(user_id, delivery_key) DO NOTHING
                """,
                (
                    user_id,
                    delivery_key,
                    cadence,
                    sign_name,
                    json.dumps(card_payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        delivery = self.get_subscription_delivery(user_id, delivery_key)
        if delivery is None:
            raise RuntimeError("Could not create subscription delivery state.")
        return delivery

    def mark_subscription_delivery_part(
        self,
        user_id: int,
        delivery_key: str,
        part_name: str,
    ) -> SubscriptionDelivery | None:
        delivery = self.get_subscription_delivery(user_id, delivery_key)
        if delivery is None:
            return None

        horoscope_sent = delivery.horoscope_sent or part_name == "horoscope"
        card_sent = delivery.card_sent or part_name == "card"
        now = _utcnow_iso()
        completed_at = now if horoscope_sent and card_sent else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE subscription_deliveries
                SET horoscope_sent = ?,
                    card_sent = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE user_id = ? AND delivery_key = ?
                """,
                (
                    int(horoscope_sent),
                    int(card_sent),
                    completed_at,
                    now,
                    user_id,
                    delivery_key,
                ),
            )
        return self.get_subscription_delivery(user_id, delivery_key)

    def save_subscription(
        self,
        user_id: int,
        chat_id: int,
        cadence: str,
        hour_local: int = 9,
        minute_local: int = 0,
        enabled: bool = True,
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
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    cadence = excluded.cadence,
                    hour_local = excluded.hour_local,
                    minute_local = excluded.minute_local,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    chat_id,
                    cadence,
                    hour_local,
                    minute_local,
                    int(enabled),
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
                    created_at,
                    updated_at
                FROM delivery_subscriptions
                WHERE enabled = 1
                ORDER BY updated_at ASC
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
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        )

    def update_subscription_delivery(self, user_id: int, delivery_key: str) -> None:
        now = _utcnow_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE delivery_subscriptions
                SET last_delivery_key = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (delivery_key, now, user_id),
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
