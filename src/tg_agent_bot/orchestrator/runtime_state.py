from __future__ import annotations

import json
import pickle
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol


class PendingWorkflow(Protocol):
    user_chat_id: int


@dataclass(frozen=True)
class PendingRecord:
    request_id: str
    workflow: PendingWorkflow
    created_at: datetime
    expires_at: datetime
    status: str = "pending"

    @property
    def expired(self) -> bool:
        return utc_now() >= self.expires_at


class OrchestratorStateStore:
    def __init__(
        self,
        db_path: Path,
        *,
        pending_ttl: timedelta = timedelta(minutes=15),
        slot_ttl: timedelta = timedelta(minutes=30),
        seen_ttl: timedelta = timedelta(hours=24),
        context_limit: int = 8,
    ) -> None:
        self.db_path = db_path
        self.pending_ttl = pending_ttl
        self.slot_ttl = slot_ttl
        self.seen_ttl = seen_ttl
        self.context_limit = context_limit
        self._pending: dict[str, PendingRecord] = {}
        self._pending_slots: dict[int, dict[str, Any]] = {}
        self._context_by_chat: dict[int, list[dict[str, Any]]] = {}
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.restore()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestrator_pending (
                    request_id TEXT PRIMARY KEY,
                    workflow_blob BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_orchestrator_pending_status_expires
                ON orchestrator_pending(status, expires_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestrator_pending_slots (
                    chat_id INTEGER PRIMARY KEY,
                    slot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orchestrator_context (
                    chat_id INTEGER PRIMARY KEY,
                    context_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS b2b_seen_messages (
                    message_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_b2b_seen_messages_expires
                ON b2b_seen_messages(expires_at)
                """
            )

    def restore(self) -> None:
        self.cleanup_expired()
        now_iso = utc_now().isoformat()
        with self._connect() as conn:
            pending_rows = conn.execute(
                """
                SELECT request_id, workflow_blob, created_at, expires_at, status
                FROM orchestrator_pending
                WHERE status = 'pending' AND expires_at > ?
                """,
                (now_iso,),
            ).fetchall()
            slot_rows = conn.execute(
                """
                SELECT chat_id, slot_json
                FROM orchestrator_pending_slots
                WHERE expires_at > ?
                """,
                (now_iso,),
            ).fetchall()
            context_rows = conn.execute(
                "SELECT chat_id, context_json FROM orchestrator_context"
            ).fetchall()

        self._pending.clear()
        for request_id, workflow_blob, created_at, expires_at, status in pending_rows:
            try:
                workflow = pickle.loads(workflow_blob)
            except Exception:
                self.mark_pending_failed(str(request_id))
                continue
            self._pending[str(request_id)] = PendingRecord(
                request_id=str(request_id),
                workflow=workflow,
                created_at=datetime.fromisoformat(str(created_at)),
                expires_at=datetime.fromisoformat(str(expires_at)),
                status=str(status),
            )

        self._pending_slots = {
            int(chat_id): slot
            for chat_id, slot_json in slot_rows
            if isinstance(slot := json.loads(str(slot_json)), dict)
        }
        self._context_by_chat = {
            int(chat_id): items
            for chat_id, context_json in context_rows
            if isinstance(items := json.loads(str(context_json)), list)
        }

    def cleanup_expired(self) -> None:
        now = utc_now()
        now_iso = now.isoformat()
        expired_pending = [
            request_id
            for request_id, record in self._pending.items()
            if record.expires_at <= now
        ]
        for request_id in expired_pending:
            self._pending.pop(request_id, None)

        expired_slots = [
            chat_id
            for chat_id, slot in self._pending_slots.items()
            if _parse_iso(str(slot.get("expires_at", ""))) <= now
        ]
        for chat_id in expired_slots:
            self._pending_slots.pop(chat_id, None)

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orchestrator_pending
                SET status = 'expired'
                WHERE status = 'pending' AND expires_at <= ?
                """,
                (now_iso,),
            )
            conn.execute(
                "DELETE FROM orchestrator_pending_slots WHERE expires_at <= ?",
                (now_iso,),
            )
            conn.execute(
                "DELETE FROM b2b_seen_messages WHERE expires_at <= ?",
                (now_iso,),
            )

    def put_pending(self, request_id: str, workflow: PendingWorkflow) -> None:
        now = utc_now()
        expires_at = now + self.pending_ttl
        record = PendingRecord(request_id, workflow, now, expires_at)
        self._pending[request_id] = record
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orchestrator_pending(
                    request_id, workflow_blob, created_at, expires_at, status
                )
                VALUES (?, ?, ?, ?, 'pending')
                ON CONFLICT(request_id) DO UPDATE SET
                    workflow_blob = excluded.workflow_blob,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    status = 'pending'
                """,
                (
                    request_id,
                    pickle.dumps(workflow),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )

    def pop_pending(self, request_id: str) -> PendingWorkflow | None:
        self.cleanup_expired()
        record = self._pending.pop(request_id, None)
        if record is None:
            return None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orchestrator_pending
                SET status = 'completed'
                WHERE request_id = ?
                """,
                (request_id,),
            )
        return record.workflow

    def mark_pending_failed(self, request_id: str) -> None:
        self._pending.pop(request_id, None)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orchestrator_pending
                SET status = 'failed'
                WHERE request_id = ?
                """,
                (request_id,),
            )

    def pending_count(self) -> int:
        self.cleanup_expired()
        return len(self._pending)

    def get_pending_slot(self, chat_id: int) -> dict[str, Any] | None:
        self.cleanup_expired()
        slot = self._pending_slots.get(chat_id)
        return dict(slot) if slot is not None else None

    def put_pending_slot(self, chat_id: int, slot: dict[str, Any]) -> None:
        now = utc_now()
        expires_at = now + self.slot_ttl
        stored = dict(slot)
        stored["created_at"] = now.isoformat()
        stored["expires_at"] = expires_at.isoformat()
        self._pending_slots[chat_id] = stored
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orchestrator_pending_slots(
                    chat_id, slot_json, created_at, expires_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    slot_json = excluded.slot_json,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    chat_id,
                    json.dumps(stored, ensure_ascii=False, sort_keys=True),
                    now.isoformat(),
                    expires_at.isoformat(),
                ),
            )

    def pop_pending_slot(self, chat_id: int) -> dict[str, Any] | None:
        slot = self._pending_slots.pop(chat_id, None)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM orchestrator_pending_slots WHERE chat_id = ?",
                (chat_id,),
            )
        return slot

    def get_context(self, chat_id: int) -> list[dict[str, Any]]:
        return list(self._context_by_chat.get(chat_id, []))

    def append_context(self, chat_id: int, item: dict[str, Any]) -> None:
        items = list(self._context_by_chat.get(chat_id, []))
        items.append(item)
        items = items[-self.context_limit:]
        self._context_by_chat[chat_id] = items
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orchestrator_context(chat_id, context_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    context_json = excluded.context_json,
                    updated_at = excluded.updated_at
                """,
                (
                    chat_id,
                    json.dumps(items, ensure_ascii=False, sort_keys=True),
                    utc_now().isoformat(),
                ),
            )

    def mark_seen(self, message_id: str) -> bool:
        self.cleanup_expired()
        if self.has_seen(message_id):
            return True
        now = utc_now()
        expires_at = now + self.seen_ttl
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO b2b_seen_messages(message_id, created_at, expires_at)
                VALUES (?, ?, ?)
                """,
                (message_id, now.isoformat(), expires_at.isoformat()),
            )
        return False

    def has_seen(self, message_id: str) -> bool:
        now_iso = utc_now().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM b2b_seen_messages
                WHERE message_id = ? AND expires_at > ?
                """,
                (message_id, now_iso),
            ).fetchone()
        return row is not None

    def seen_count(self) -> int:
        self.cleanup_expired()
        now_iso = utc_now().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM b2b_seen_messages WHERE expires_at > ?",
                (now_iso,),
            ).fetchone()
        return int(row[0]) if row else 0


def state_store_from_context(context: Any) -> Any:
    bot_data = context.application.bot_data
    store = bot_data.get("orchestrator_state")
    if store is None:
        raise RuntimeError(
            "orchestrator_state is not configured. Build the bot through "
            "build_application() or inject a state store explicitly."
        )
    return store


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
