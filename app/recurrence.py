
"""Recurring task occurrence generation for Tempo."""

import sqlite3
from datetime import date, datetime, timedelta

from app.database import get_connection
from app.models import Task, task_from_row


def occurs_on_date(task: Task, target_date: date) -> bool:
    """Return True if a recurring task occurs on target_date."""

    if not task.is_active or task.task_type != "recurring":
        return False

    if task.recurrence_rule == "daily":
        return True

    if task.recurrence_rule == "weekdays":
        return target_date.weekday() < 5

    if task.recurrence_rule == "weekly":
        return target_date.weekday() == task.recurrence_weekday

    return False


def calculate_end_time(
    start_time: str | None,
    estimated_minutes: int | None,
) -> str | None:
    """Calculate the planned end time in HH:MM format."""

    if start_time is None or estimated_minutes is None:
        return None

    start = datetime.strptime(start_time, "%H:%M")

    end = start + timedelta(minutes=estimated_minutes)

    return end.strftime("%H:%M")


def generate_occurrences(
    start_date: date,
    end_date: date,
    db_path=None,
) -> int:
    """Generate recurring task occurrences for an inclusive date range.

    Existing occurrences are preserved, including their completion status.

    Returns:
        Number of newly inserted occurrences.
    """

    if start_date > end_date:
        raise ValueError("Start date cannot be after end date.")

    conn = get_connection(db_path)

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM tasks
            WHERE is_active = 1
              AND task_type = 'recurring'
            ORDER BY id
            """
        ).fetchall()

        tasks = [task_from_row(row) for row in rows]

        inserted_count = 0

        with conn:
            for task in tasks:
                current_date = start_date

                while current_date <= end_date:
                    if occurs_on_date(task, current_date):
                        end_time = calculate_end_time(
                            task.preferred_time,
                            task.estimated_minutes,
                        )

                        cursor = conn.execute(
                            """
                            INSERT INTO task_occurrences (
                                task_id,
                                scheduled_date,
                                start_time,
                                end_time
                            )
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(task_id, scheduled_date)
                            DO NOTHING
                            """,
                            (
                                task.id,
                                current_date.isoformat(),
                                task.preferred_time,
                                end_time,
                            ),
                        )

                        inserted_count += cursor.rowcount

                    current_date += timedelta(days=1)

        return inserted_count

    finally:
        conn.close()


def get_occurrences(
    target_date: date,
    db_path=None,
) -> list[sqlite3.Row]:
    """Retrieve scheduled occurrences for a given date."""

    conn = get_connection(db_path)

    try:
        rows = conn.execute(
            """
            SELECT
                o.id,
                o.task_id,
                t.title,
                t.category,
                t.priority,
                t.estimated_minutes,
                o.scheduled_date,
                o.start_time,
                o.end_time,
                o.status,
                o.completed_at
            FROM task_occurrences AS o
            JOIN tasks AS t
                ON o.task_id = t.id
            WHERE o.scheduled_date = ?
            ORDER BY
                o.start_time IS NULL,
                o.start_time,
                o.id
            """,
            (target_date.isoformat(),),
        ).fetchall()

        return rows

    finally:
        conn.close()
