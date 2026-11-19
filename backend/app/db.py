"""SQLite persistence for run history, diagnostics, and saved snippets.

Local-first, single-file SQLite database with zero external dependencies.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("AUTOPATCH_DB_PATH", Path(__file__).resolve().parents[1] / "autopatch.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize database tables if they do not exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                filename TEXT NOT NULL,
                language TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                code TEXT NOT NULL,
                stdout TEXT DEFAULT '',
                stderr TEXT DEFAULT '',
                exit_code INTEGER,
                repaired_code TEXT DEFAULT '',
                issues_count INTEGER DEFAULT 0,
                ai_used INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snippets (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                code TEXT NOT NULL,
                tests TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (timestamp DESC)")
        conn.commit()


def record_history(
    filename: str,
    language: str,
    action: str,
    status: str,
    code: str,
    stdout: str = "",
    stderr: str = "",
    exit_code: int | None = None,
    repaired_code: str = "",
    issues_count: int = 0,
    ai_used: bool = False,
) -> dict[str, Any]:
    """Record an action (run, repair, analyze, verify) in history."""
    init_db()
    ts = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO history (timestamp, filename, language, action, status, code,
                                 stdout, stderr, exit_code, repaired_code, issues_count, ai_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                filename[:100],
                language[:20],
                action[:30],
                status[:30],
                code[:20000],
                stdout[:12000],
                stderr[:12000],
                exit_code,
                repaired_code[:20000],
                issues_count,
                1 if ai_used else 0,
            ),
        )
        conn.commit()
        record_id = cursor.lastrowid
        return {
            "id": record_id,
            "timestamp": ts,
            "filename": filename,
            "language": language,
            "action": action,
            "status": status,
            "exit_code": exit_code,
            "issues_count": issues_count,
            "ai_used": ai_used,
        }


def get_history(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent history entries, newest first."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, timestamp, filename, language, action, status, code,
                   stdout, stderr, exit_code, repaired_code, issues_count, ai_used
            FROM history
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "filename": row["filename"],
                "language": row["language"],
                "action": row["action"],
                "status": row["status"],
                "code": row["code"],
                "stdout": row["stdout"],
                "stderr": row["stderr"],
                "exit_code": row["exit_code"],
                "repaired_code": row["repaired_code"],
                "issues_count": row["issues_count"],
                "ai_used": bool(row["ai_used"]),
            }
            for row in rows
        ]


def clear_history() -> int:
    """Clear all records from history."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM history")
        conn.commit()
        return cursor.rowcount


def save_snippet(
    snippet_id: str,
    title: str,
    language: str,
    code: str,
    tests: str = "",
    description: str = "",
) -> dict[str, Any]:
    """Save or update a snippet."""
    init_db()
    ts = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO snippets (id, title, language, code, tests, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                language=excluded.language,
                code=excluded.code,
                tests=excluded.tests,
                description=excluded.description,
                created_at=excluded.created_at
            """,
            (
                snippet_id[:50],
                title[:100],
                language[:20],
                code[:20000],
                tests[:12000],
                description[:300],
                ts,
            ),
        )
        conn.commit()
        return {
            "id": snippet_id,
            "title": title,
            "language": language,
            "code": code,
            "tests": tests,
            "description": description,
            "created_at": ts,
        }


def get_snippets() -> list[dict[str, Any]]:
    """Retrieve all saved snippets."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, title, language, code, tests, description, created_at FROM snippets ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "language": row["language"],
                "code": row["code"],
                "tests": row["tests"],
                "description": row["description"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def delete_snippet(snippet_id: str) -> bool:
    """Delete a snippet by id."""
    init_db()
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
        conn.commit()
        return cursor.rowcount > 0
