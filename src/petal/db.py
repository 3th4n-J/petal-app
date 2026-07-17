"""SQLite data-access layer for the period tracker.

Single-table schema keyed on period start date. All CRUD goes through the
Database class so the UI never touches SQL directly.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Optional

from .models import PeriodEntry

# Default DB lives next to the app. On mobile, Flet gives each app a private
# writable dir; override via PERIOD_DB env var or the db_path argument.
DEFAULT_DB = os.path.join(os.getcwd(), "period_tracker.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS period_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date  TEXT    NOT NULL UNIQUE,          -- ISO yyyy-mm-dd
    end_date    TEXT,
    flow        TEXT    NOT NULL DEFAULT 'Medium',
    mood        TEXT    NOT NULL DEFAULT '',
    symptoms    TEXT    NOT NULL DEFAULT '',       -- comma-separated
    notes       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    deleted_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_entries_start ON period_entries(start_date DESC);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _parse_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class Database:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("PERIOD_DB", DEFAULT_DB)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(period_entries)")}
        if "deleted_at" not in cols:
            self.conn.execute("ALTER TABLE period_entries ADD COLUMN deleted_at TEXT")

    # ---- mapping helpers -------------------------------------------------
    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> PeriodEntry:
        return PeriodEntry(
            id=row["id"],
            start_date=_parse_date(row["start_date"]),
            end_date=_parse_date(row["end_date"]),
            flow=row["flow"],
            mood=row["mood"],
            symptoms=[s for s in row["symptoms"].split(",") if s],
            notes=row["notes"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
            deleted_at=_parse_dt(row["deleted_at"]) if "deleted_at" in row.keys() else None,
        )

    # ---- CRUD ------------------------------------------------------------
    def add(self, entry: PeriodEntry) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        # a trashed row may still hold this date (UNIQUE start_date) -- clear it
        self.conn.execute(
            "DELETE FROM period_entries WHERE start_date=? AND deleted_at IS NOT NULL",
            (_iso(entry.start_date),))
        cur = self.conn.execute(
            """INSERT INTO period_entries
               (start_date, end_date, flow, mood, symptoms, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (_iso(entry.start_date), _iso(entry.end_date), entry.flow, entry.mood,
             entry.symptoms_csv, entry.notes, now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, entry: PeriodEntry) -> None:
        if entry.id is None:
            raise ValueError("Cannot update an entry without an id")
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """UPDATE period_entries
               SET start_date=?, end_date=?, flow=?, mood=?, symptoms=?, notes=?, updated_at=?
               WHERE id=?""",
            (_iso(entry.start_date), _iso(entry.end_date), entry.flow, entry.mood,
             entry.symptoms_csv, entry.notes, now, entry.id),
        )
        self.conn.commit()

    def delete(self, entry_id: int) -> None:
        """Soft delete -> moves the entry to trash."""
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("UPDATE period_entries SET deleted_at=? WHERE id=?",
                          (now, entry_id))
        self.conn.commit()

    def get(self, entry_id: int) -> Optional[PeriodEntry]:
        row = self.conn.execute(
            "SELECT * FROM period_entries WHERE id=?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def list_all(self) -> List[PeriodEntry]:
        """Newest first."""
        rows = self.conn.execute(
            "SELECT * FROM period_entries WHERE deleted_at IS NULL ORDER BY start_date DESC"
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def clear_entries(self) -> None:
        self.conn.execute("DELETE FROM period_entries")
        self.conn.commit()

    # ---- trash (soft delete, 30-day retention) --------------------------
    def restore(self, entry_id: int) -> None:
        self.conn.execute("UPDATE period_entries SET deleted_at=NULL WHERE id=?",
                          (entry_id,))
        self.conn.commit()

    def hard_delete(self, entry_id: int) -> None:
        self.conn.execute("DELETE FROM period_entries WHERE id=?", (entry_id,))
        self.conn.commit()

    def list_trash(self) -> List[PeriodEntry]:
        rows = self.conn.execute(
            "SELECT * FROM period_entries WHERE deleted_at IS NOT NULL "
            "ORDER BY deleted_at DESC").fetchall()
        return [self._row_to_entry(r) for r in rows]

    def empty_trash(self) -> None:
        self.conn.execute("DELETE FROM period_entries WHERE deleted_at IS NOT NULL")
        self.conn.commit()

    def purge_expired(self, days: int = 30) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        cur = self.conn.execute(
            "DELETE FROM period_entries WHERE deleted_at IS NOT NULL AND deleted_at < ?",
            (cutoff,))
        self.conn.commit()
        return cur.rowcount

    # ---- settings (key-value) -------------------------------------------
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def get_int(self, key: str, default: int) -> int:
        try:
            return int(self.get_setting(key, str(default)))
        except (TypeError, ValueError):
            return default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
        self.conn.commit()

    # ---- app-lock PIN (salted SHA-256, never stored in clear) -----------
    @staticmethod
    def _hash_pin(pin: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()

    def has_pin(self) -> bool:
        return self.get_setting("pin_hash") is not None

    def set_pin(self, pin: str) -> None:
        salt = secrets.token_hex(8)
        self.set_setting("pin_salt", salt)
        self.set_setting("pin_hash", self._hash_pin(pin, salt))

    def check_pin(self, pin: str) -> bool:
        salt = self.get_setting("pin_salt")
        stored = self.get_setting("pin_hash")
        if not salt or not stored:
            return True  # no lock set
        return secrets.compare_digest(self._hash_pin(pin, salt), stored)

    def clear_pin(self) -> None:
        self.conn.execute("DELETE FROM settings WHERE key IN ('pin_hash','pin_salt')")
        self.conn.commit()

    def clear_settings(self) -> None:
        self.conn.execute("DELETE FROM settings")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
