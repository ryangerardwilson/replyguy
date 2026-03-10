from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .paths import db_path, ensure_dirs


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            mode TEXT NOT NULL,
            inbox_snapshot_path TEXT,
            digest_path TEXT,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS post_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            job_id TEXT NOT NULL,
            crux TEXT NOT NULL,
            angle TEXT NOT NULL,
            source_urls_json TEXT NOT NULL,
            linkedin_post_id TEXT,
            x_post_id TEXT,
            linkedin_text TEXT NOT NULL,
            x_text TEXT NOT NULL,
            text_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reply_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            job_id TEXT NOT NULL,
            source_url TEXT,
            source_excerpt TEXT NOT NULL,
            recommended_reply TEXT NOT NULL,
            alt_1 TEXT,
            alt_2 TEXT,
            alt_3 TEXT,
            why_it_works TEXT
        );
        """
    )
    conn.commit()


def create_job(
    conn: sqlite3.Connection,
    job_id: str,
    mode: str,
    inbox_snapshot_path: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO jobs (id, created_at, status, mode, inbox_snapshot_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, _utc_now(), "running", mode, inbox_snapshot_path),
    )
    conn.commit()


def complete_job(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    digest_path: str | None,
    summary: str,
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET completed_at = ?, status = ?, digest_path = ?, summary = ?
        WHERE id = ?
        """,
        (_utc_now(), status, digest_path, summary, job_id),
    )
    conn.commit()


def recent_post_memory(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT created_at, crux, angle, source_urls_json, linkedin_post_id, x_post_id
        FROM post_memory
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "created_at": row["created_at"],
                "crux": row["crux"],
                "angle": row["angle"],
                "source_urls": json.loads(row["source_urls_json"] or "[]"),
                "linkedin_post_id": row["linkedin_post_id"],
                "x_post_id": row["x_post_id"],
            }
        )
    return items


def _normalize_key(text: str) -> str:
    return " ".join((text or "").lower().split())


def has_recent_exact_angle(conn: sqlite3.Connection, crux: str, angle: str) -> bool:
    rows = conn.execute(
        "SELECT crux, angle FROM post_memory ORDER BY id DESC LIMIT 50"
    ).fetchall()
    target = (_normalize_key(crux), _normalize_key(angle))
    return any((_normalize_key(row["crux"]), _normalize_key(row["angle"])) == target for row in rows)


def record_post(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    crux: str,
    angle: str,
    source_urls: list[str],
    linkedin_post_id: str | None,
    x_post_id: str | None,
    linkedin_text: str,
    x_text: str,
) -> None:
    text_hash = hashlib.sha256(f"{linkedin_text}\n{x_text}".encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO post_memory
        (created_at, job_id, crux, angle, source_urls_json, linkedin_post_id, x_post_id, linkedin_text, x_text, text_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_now(),
            job_id,
            crux,
            angle,
            json.dumps(source_urls),
            linkedin_post_id,
            x_post_id,
            linkedin_text,
            x_text,
            text_hash,
        ),
    )
    conn.commit()


def record_reply(
    conn: sqlite3.Connection,
    *,
    job_id: str,
    source_url: str | None,
    source_excerpt: str,
    recommended_reply: str,
    alternates: list[str],
    why_it_works: str,
) -> None:
    alt_values = (alternates + ["", "", ""])[:3]
    conn.execute(
        """
        INSERT INTO reply_suggestions
        (created_at, job_id, source_url, source_excerpt, recommended_reply, alt_1, alt_2, alt_3, why_it_works)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_now(),
            job_id,
            source_url,
            source_excerpt,
            recommended_reply,
            alt_values[0],
            alt_values[1],
            alt_values[2],
            why_it_works,
        ),
    )
    conn.commit()
