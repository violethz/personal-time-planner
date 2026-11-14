
"""Task occurrence completion and history management for Tempo."""

import sqlite3
from datetime import datetime

from app.database import get_connection


def complete_occurrence(
    occurrence_id: int,
    actual_minutes: int | None = None,
    notes: str | None = None,
    db_path=None,
) -> None:
    """Mark an occurrence as completed and record its history."""

    if actual_minutes is not None:
        if type(actual_minutes) is not int or actual_minutes < 0:
            raise ValueError(
                "Actual minutes must be a non-negative integer."
            )

    conn = get_connection(db_path)

    try:
        with conn:
            occurrence = conn.execute(
                """
                SELECT id, status
                FROM task_occurrences
                WHERE id = ?
                """,
                (occurrence_id,),
            ).fetchone()

            if occurrence is None:
                raise ValueError(
                    f"Occurrence {occurrence_id} does not exist."
                )

            if occurrence["status"] != "pending":
                raise ValueError(
                    "Only pending occurrences can be completed."
                )

            completed_at = datetime.now().isoformat(
                timespec="seconds"
            )

            conn.execute(
                """
                UPDATE task_occurrences
                SET status = 'completed',
                    completed_at = ?
                WHERE id = ?
                """,
                (completed_at, occurrence_id),
            )

            conn.execute(
                """
                INSERT INTO task_history (
                    occurrence_id,
                    actual_minutes,
                    notes
                )
                VALUES (?, ?, ?)
                """,
                (occurrence_id, actual_minutes, notes),
            )

    finally:
        conn.close()


def skip_occurrence(
    occurrence_id: int,
    db_path=None,
) -> None:
    """Mark a pending occurrence as skipped."""

    conn = get_connection(db_path)

    try:
        with conn:
            occurrence = conn.execute(
                """
                SELECT id, status
                FROM task_occurrences
                WHERE id = ?
                """,
                (occurrence_id,),
            ).fetchone()

            if occurrence is None:
                raise ValueError(
                    f"Occurrence {occurrence_id} does not exist."
                )

            if occurrence["status"] != "pending":   # status=completed can be 'skipped'
                raise ValueError(
                    "Only pending occurrences can be skipped."
                )

            conn.execute(
                """
                UPDATE task_occurrences
                SET status = 'skipped'
                WHERE id = ?
                """,
                (occurrence_id,),
            )

    finally:
        conn.close()


def get_task_history(
    task_id: int,
    db_path=None,
) -> list[sqlite3.Row]:
    """Retrieve completion history for a task."""

    conn = get_connection(db_path)

    try:
        rows = conn.execute(
            """
            SELECT
                h.id,
                h.occurrence_id,
                o.task_id,
                o.scheduled_date,
                o.status,
                o.completed_at,
                h.actual_start,
                h.actual_end,
                h.actual_minutes,
                h.notes
            FROM task_history AS h
            JOIN task_occurrences AS o
                ON h.occurrence_id = o.id
            WHERE o.task_id = ?
            ORDER BY o.scheduled_date DESC, h.id DESC
            """,
            (task_id,),
        ).fetchall()

        return rows

    finally:
        conn.close()
