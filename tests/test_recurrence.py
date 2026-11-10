
"""Tests for Tempo's recurring task generation."""

from datetime import date

import pytest

from app.database import get_connection, initialize_database
from app.models import TaskCreate
from app.tasks import create_task, archive_task
from app.recurrence import (
    occurs_on_date,
    calculate_end_time,
    generate_occurrences,
    get_occurrences,
)


@pytest.fixture
def db_path(tmp_path):
    """Create a fresh temporary database for each test."""

    path = tmp_path / "tempo_test.db"
    initialize_database(path)
    return path


def make_recurring_task(
    db_path,
    title="Test task",
    rule="daily",
    weekday=None,
    preferred_time="08:30",
    duration=15,
):
    """Create a recurring task for testing."""

    return create_task(
        TaskCreate(
            title=title,
            task_type="recurring",
            recurrence_rule=rule,
            recurrence_weekday=weekday,
            preferred_time=preferred_time,
            estimated_minutes=duration,
        ),
        db_path=db_path,
    )


def test_daily_task_generates_seven_occurrences(db_path):
    make_recurring_task(db_path)

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert count == 7

    conn = get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM task_occurrences"
        ).fetchone()[0]
        assert total == 7
    finally:
        conn.close()


def test_weekdays_task_generates_five_occurrences(db_path):
    make_recurring_task(db_path, rule="weekdays")

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert count == 5

    assert get_occurrences(date(2026, 11, 14), db_path) == []
    assert get_occurrences(date(2026, 11, 15), db_path) == []


def test_weekly_task_generates_on_selected_weekday(db_path):
    task = make_recurring_task(
        db_path,
        rule="weekly",
        weekday=2,  # Wednesday
    )

    assert occurs_on_date(task, date(2026, 11, 11))
    assert not occurs_on_date(task, date(2026, 11, 12))

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 22),
        db_path,
    )

    assert count == 2

    assert len(get_occurrences(date(2026, 11, 11), db_path)) == 1
    assert len(get_occurrences(date(2026, 11, 18), db_path)) == 1


def test_inactive_task_generates_no_occurrences(db_path):
    task = make_recurring_task(db_path)

    archive_task(task.id, db_path)

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert count == 0


def test_generation_is_idempotent(db_path):
    make_recurring_task(db_path)

    first_count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    second_count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert first_count == 7
    assert second_count == 0

    conn = get_connection(db_path)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM task_occurrences"
        ).fetchone()[0]

        assert total == 7
    finally:
        conn.close()


def test_invalid_date_range_raises_error(db_path):
    with pytest.raises(ValueError):
        generate_occurrences(
            date(2026, 11, 15),
            date(2026, 11, 9),
            db_path,
        )


def test_occurrence_start_and_end_times(db_path):
    make_recurring_task(
        db_path,
        preferred_time="08:30",
        duration=45,
    )

    generate_occurrences(
        date(2026, 11, 11),
        date(2026, 11, 11),
        db_path,
    )

    occurrences = get_occurrences(
        date(2026, 11, 11),
        db_path,
    )

    assert len(occurrences) == 1
    assert occurrences[0]["start_time"] == "08:30"
    assert occurrences[0]["end_time"] == "09:15"
    assert occurrences[0]["status"] == "pending"


def test_completed_occurrence_is_not_reset(db_path):
    make_recurring_task(db_path)

    target = date(2026, 11, 11)

    generate_occurrences(target, target, db_path)

    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                UPDATE task_occurrences
                SET status = 'completed',
                    completed_at = '2026-11-11T08:45:00'
                WHERE scheduled_date = ?
                """,
                (target.isoformat(),),
            )
    finally:
        conn.close()

    count = generate_occurrences(target, target, db_path)

    occurrences = get_occurrences(target, db_path)

    assert count == 0
    assert len(occurrences) == 1
    assert occurrences[0]["status"] == "completed"
    assert (
        occurrences[0]["completed_at"]
        == "2026-11-11T08:45:00"
    )


def test_task_without_preferred_time(db_path):
    make_recurring_task(
        db_path,
        preferred_time=None,
        duration=30,
    )

    generate_occurrences(
        date(2026, 11, 11),
        date(2026, 11, 11),
        db_path,
    )

    occurrences = get_occurrences(
        date(2026, 11, 11),
        db_path,
    )

    assert len(occurrences) == 1
    assert occurrences[0]["start_time"] is None
    assert occurrences[0]["end_time"] is None


def test_calculate_end_time():
    assert calculate_end_time("08:30", 15) == "08:45"
    assert calculate_end_time("09:45", 30) == "10:15"
    assert calculate_end_time("23:30", 60) == "00:30"
    assert calculate_end_time(None, 30) is None
    assert calculate_end_time("08:30", None) is None


def test_multiple_recurring_tasks(db_path):
    make_recurring_task(
        db_path,
        title="Morning stretching",
        rule="daily",
    )

    make_recurring_task(
        db_path,
        title="Read news",
        rule="weekdays",
    )

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert count == 12


def test_one_time_task_is_not_generated(db_path):
    create_task(
        TaskCreate(
            title="Finish AI Quant Lab",
            task_type="one_time",
            recurrence_rule="none",
            deadline="2026-11-13",
        ),
        db_path=db_path,
    )

    count = generate_occurrences(
        date(2026, 11, 9),
        date(2026, 11, 15),
        db_path,
    )

    assert count == 0
