from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def resolve_database_path() -> Path:
    """
    Choose the SQLite database location.

    Local development:
        paperwatch.db inside the project folder

    Railway with a mounted volume:
        /data/paperwatch.db, or the path supplied through DATABASE_PATH
    """

    configured_path = os.getenv(
        "DATABASE_PATH",
        "",
    ).strip()

    if configured_path:
        database_path = Path(
            configured_path
        ).expanduser()

    else:
        railway_mount_path = os.getenv(
            "RAILWAY_VOLUME_MOUNT_PATH",
            "",
        ).strip()

        if railway_mount_path:
            database_path = (
                Path(railway_mount_path)
                / "paperwatch.db"
            )
        else:
            database_path = Path(
                "paperwatch.db"
            )

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return database_path


DATABASE_NAME = resolve_database_path()


def current_utc_time() -> str:
    """Return the current UTC date and time as text."""

    return datetime.now(
        timezone.utc
    ).isoformat(timespec="seconds")


def connect_database() -> sqlite3.Connection:
    """Connect to the SQLite database."""

    connection = sqlite3.connect(
        DATABASE_NAME,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def initialize_database() -> None:
    """Create every table required by the bot."""

    with connect_database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                research_topic TEXT NOT NULL COLLATE NOCASE,
                created_at TEXT NOT NULL,
                UNIQUE(chat_id, research_topic)
            );

            CREATE TABLE IF NOT EXISTS seen_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                paper_url TEXT NOT NULL,
                paper_title TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,

                FOREIGN KEY(alert_id)
                    REFERENCES subscriptions(id)
                    ON DELETE CASCADE,

                UNIQUE(alert_id, paper_url)
            );

            CREATE TABLE IF NOT EXISTS alert_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                source_name TEXT NOT NULL COLLATE NOCASE,
                initialized_at TEXT NOT NULL,

                FOREIGN KEY(alert_id)
                    REFERENCES subscriptions(id)
                    ON DELETE CASCADE,

                UNIQUE(alert_id, source_name)
            );

            CREATE INDEX IF NOT EXISTS
                idx_subscriptions_chat_id
                ON subscriptions(chat_id);

            CREATE INDEX IF NOT EXISTS
                idx_seen_papers_alert_id
                ON seen_papers(alert_id);

            CREATE INDEX IF NOT EXISTS
                idx_alert_sources_alert_id
                ON alert_sources(alert_id);
            """
        )

    print(
        "SQLite database ready at: "
        f"{DATABASE_NAME.resolve()}"
    )


def add_subscription(
    chat_id: int,
    research_topic: str,
) -> int | None:
    """Save an alert and return its ID, or None if it exists."""

    try:
        with connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO subscriptions (
                    chat_id,
                    research_topic,
                    created_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    chat_id,
                    research_topic.strip(),
                    current_utc_time(),
                ),
            )

            return int(cursor.lastrowid)

    except sqlite3.IntegrityError:
        return None


def get_subscriptions(
    chat_id: int,
) -> list[sqlite3.Row]:
    """Return every alert belonging to one Telegram chat."""

    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                chat_id,
                research_topic,
                created_at
            FROM subscriptions
            WHERE chat_id = ?
            ORDER BY id
            """,
            (chat_id,),
        ).fetchall()

    return list(rows)


def get_all_subscriptions() -> list[sqlite3.Row]:
    """Return every saved alert from all Telegram users."""

    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                chat_id,
                research_topic,
                created_at
            FROM subscriptions
            ORDER BY id
            """
        ).fetchall()

    return list(rows)


def delete_subscription(
    chat_id: int,
    alert_id: int,
) -> bool:
    """Delete one alert belonging to the specified Telegram chat."""

    with connect_database() as connection:
        cursor = connection.execute(
            """
            DELETE FROM subscriptions
            WHERE id = ? AND chat_id = ?
            """,
            (
                alert_id,
                chat_id,
            ),
        )

        return cursor.rowcount > 0


def save_seen_paper(
    alert_id: int,
    paper_url: str,
    paper_title: str,
) -> bool:
    """Record a paper as seen and return True for a new row."""

    with connect_database() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO seen_papers (
                alert_id,
                paper_url,
                paper_title,
                first_seen_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                alert_id,
                paper_url,
                paper_title,
                current_utc_time(),
            ),
        )

        return cursor.rowcount > 0


def save_existing_papers(
    alert_id: int,
    papers: Iterable[dict],
) -> int:
    """Record current papers as the baseline."""

    saved_count = 0

    for paper in papers:
        paper_url = str(
            paper.get("url", "")
        ).strip()

        paper_title = str(
            paper.get("title", "")
        ).strip()

        if not paper_url or not paper_title:
            continue

        if save_seen_paper(
            alert_id=alert_id,
            paper_url=paper_url,
            paper_title=paper_title,
        ):
            saved_count += 1

    return saved_count


def get_seen_paper_count(
    alert_id: int,
) -> int:
    """Return how many paper records are stored for an alert."""

    with connect_database() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM seen_papers
            WHERE alert_id = ?
            """,
            (alert_id,),
        ).fetchone()

    return int(row["total"])


def get_initialized_sources(
    alert_id: int,
) -> set[str]:
    """Return the sources already baselined for an alert."""

    with connect_database() as connection:
        rows = connection.execute(
            """
            SELECT source_name
            FROM alert_sources
            WHERE alert_id = ?
            """,
            (alert_id,),
        ).fetchall()

    return {
        str(row["source_name"]).strip()
        for row in rows
        if str(row["source_name"]).strip()
    }


def mark_sources_initialized(
    alert_id: int,
    source_names: Iterable[str],
) -> int:
    """Mark successful sources as baselined for an alert."""

    inserted_count = 0

    with connect_database() as connection:
        for source_name in source_names:
            clean_source = str(
                source_name
            ).strip()

            if not clean_source:
                continue

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO alert_sources (
                    alert_id,
                    source_name,
                    initialized_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    alert_id,
                    clean_source,
                    current_utc_time(),
                ),
            )

            inserted_count += max(
                cursor.rowcount,
                0,
            )

    return inserted_count
