from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from screenshot_inbox.schemas import parse_analysis

SCHEMA = """
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'analyzing', 'completed', 'failed')),
    category TEXT,
    confidence REAL,
    title TEXT,
    summary TEXT,
    extracted_text TEXT,
    analysis_json TEXT,
    provider TEXT,
    model TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    deferred_retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    analyzed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_screenshots_detected ON screenshots(detected_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_screenshots_status ON screenshots(status);
CREATE INDEX IF NOT EXISTS idx_screenshots_category ON screenshots(category);
CREATE TABLE IF NOT EXISTS screenshot_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screenshot_id INTEGER NOT NULL REFERENCES screenshots(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_screenshot
    ON screenshot_messages(screenshot_id, id);
CREATE TABLE IF NOT EXISTS dismissed_screenshots (
    file_hash TEXT PRIMARY KEY,
    dismissed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class ScreenshotDatabase:
    def __init__(self, path: Path, lock_retries: int = 4) -> None:
        self.path = path
        self.lock_retries = lock_retries

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(screenshots)").fetchall()
            }
            if "deferred_retry_count" not in columns:
                connection.execute(
                    "ALTER TABLE screenshots ADD COLUMN deferred_retry_count "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            if "next_retry_at" not in columns:
                connection.execute("ALTER TABLE screenshots ADD COLUMN next_retry_at TEXT")
            connection.execute(
                "UPDATE screenshots SET status='pending', error_message="
                "'Recovered after application restart', next_retry_at=NULL "
                "WHERE status='analyzing'"
            )

    def _write(self, sql: str, parameters: tuple[Any, ...]) -> sqlite3.Cursor:
        for attempt in range(self.lock_retries):
            try:
                with self.connect() as connection:
                    return connection.execute(sql, parameters)
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt + 1 >= self.lock_retries:
                    raise
                time.sleep(0.05 * (2**attempt))
        raise RuntimeError("unreachable")

    def insert_screenshot(
        self, file_path: Path, file_hash: str, created_at: str
    ) -> tuple[int, bool]:
        try:
            cursor = self._write(
                "INSERT INTO screenshots(file_path, file_hash, created_at) VALUES (?, ?, ?)",
                (str(file_path.resolve()), file_hash, created_at),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return an inserted row id")
            return cursor.lastrowid, True
        except sqlite3.IntegrityError:
            with self.connect() as connection:
                row = connection.execute(
                    "SELECT id FROM screenshots WHERE file_hash=?", (file_hash,)
                ).fetchone()
            if row is None:
                raise
            return int(row["id"]), False

    def get(self, screenshot_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM screenshots WHERE id=?", (screenshot_id,)
            ).fetchone()
        return self._decode(row) if row else None

    def list_screenshots(
        self, category: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        params: tuple[Any, ...]
        if category == "error":
            sql = (
                "SELECT * FROM screenshots WHERE category='error' OR status='failed' "
                "ORDER BY detected_at DESC, id DESC LIMIT ?"
            )
            params = (limit,)
        elif category:
            sql = (
                "SELECT * FROM screenshots WHERE category=? "
                "ORDER BY detected_at DESC, id DESC LIMIT ?"
            )
            params = (category, limit)
        else:
            sql = "SELECT * FROM screenshots ORDER BY detected_at DESC, id DESC LIMIT ?"
            params = (limit,)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._decode(row) for row in rows]

    def pending_ids(self) -> list[int]:
        return [screenshot_id for screenshot_id, _ in self.pending_jobs()]

    def pending_jobs(self) -> list[tuple[int, float]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT id, MAX(
                    0.0,
                    COALESCE((julianday(next_retry_at) - julianday('now')) * 86400.0, 0.0)
                ) AS delay_seconds
                FROM screenshots WHERE status='pending' ORDER BY id"""
            ).fetchall()
        return [(int(row["id"]), float(row["delay_seconds"])) for row in rows]

    def count_screenshots(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM screenshots").fetchone()
        return int(row["count"])

    def is_dismissed(self, file_hash: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM dismissed_screenshots WHERE file_hash=?", (file_hash,)
            ).fetchone()
        return row is not None

    def get_state(self, key: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_state(self, key: str, value: str) -> None:
        self._write(
            "INSERT INTO app_state(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def mark_analyzing(self, screenshot_id: int, provider: str, model: str | None) -> None:
        self._write(
            "UPDATE screenshots SET status='analyzing', provider=?, model=?, error_message=NULL, "
            "next_retry_at=NULL WHERE id=?",
            (provider, model, screenshot_id),
        )

    def mark_completed(
        self, screenshot_id: int, result: dict[str, Any], model: str | None = None
    ) -> None:
        self._write(
            """UPDATE screenshots SET status='completed', category=?, confidence=?, title=?,
            summary=?, extracted_text=?, analysis_json=?, error_message=NULL,
            model=COALESCE(?, model), next_retry_at=NULL,
            analyzed_at=CURRENT_TIMESTAMP WHERE id=?""",
            (
                result["category"],
                result["confidence"],
                result["title"],
                result["summary"],
                result["extracted_text"],
                json.dumps(result, ensure_ascii=False),
                model,
                screenshot_id,
            ),
        )

    def mark_failed(self, screenshot_id: int, message: str, retry_count: int) -> None:
        self._write(
            "UPDATE screenshots SET status='failed', error_message=?, retry_count=?, "
            "next_retry_at=NULL, analyzed_at=CURRENT_TIMESTAMP WHERE id=?",
            (message[:1000], retry_count, screenshot_id),
        )

    def defer_retry(
        self, screenshot_id: int, message: str, retry_count: int, delay_seconds: float
    ) -> None:
        modifier = f"+{max(0.0, delay_seconds):.3f} seconds"
        self._write(
            """UPDATE screenshots SET status='pending', error_message=?, retry_count=?,
            deferred_retry_count=deferred_retry_count + 1,
            next_retry_at=datetime('now', ?), analyzed_at=CURRENT_TIMESTAMP
            WHERE id=?""",
            (message[:1000], retry_count, modifier, screenshot_id),
        )

    def reset_for_retry(self, screenshot_id: int) -> bool:
        cursor = self._write(
            "UPDATE screenshots SET status='pending', error_message=NULL, retry_count=0, "
            "deferred_retry_count=0, next_retry_at=NULL "
            "WHERE id=? AND status IN ('failed', 'completed')",
            (screenshot_id,),
        )
        return cursor.rowcount == 1

    def delete_screenshot(self, screenshot_id: int) -> bool:
        for attempt in range(self.lock_retries):
            try:
                with self.connect() as connection:
                    row = connection.execute(
                        "SELECT file_hash FROM screenshots WHERE id=?", (screenshot_id,)
                    ).fetchone()
                    if row is None:
                        return False
                    connection.execute(
                        "INSERT OR IGNORE INTO dismissed_screenshots(file_hash) VALUES (?)",
                        (row["file_hash"],),
                    )
                    cursor = connection.execute(
                        "DELETE FROM screenshots WHERE id=?", (screenshot_id,)
                    )
                    return cursor.rowcount == 1
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt + 1 >= self.lock_retries:
                    raise
                time.sleep(0.05 * (2**attempt))
        raise RuntimeError("unreachable")

    def add_chat_message(self, screenshot_id: int, role: str, content: str) -> int:
        if role not in {"user", "assistant"}:
            raise ValueError("Unsupported chat role")
        cursor = self._write(
            "INSERT INTO screenshot_messages(screenshot_id, role, content) VALUES (?, ?, ?)",
            (screenshot_id, role, content),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("SQLite did not return a chat message id")
        return int(cursor.lastrowid)

    def list_chat_messages(self, screenshot_id: int, limit: int = 40) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM screenshot_messages WHERE screenshot_id=? ORDER BY id DESC LIMIT ?",
                (screenshot_id, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        raw = value.get("analysis_json")
        payload = json.loads(raw) if raw else None
        value["analysis"] = parse_analysis(payload).as_dict() if isinstance(payload, dict) else None
        return value
