
"""Tests for Tempo's task completion and history management."""

from datetime import date

import pytest

from app.database import get_connection, initialize_database
from app.history import (
    complete_occurrence,
    skip_occurrence,
    get_task_history,
)
from app.models import TaskCreate
from app.recurrence import generate_occurrences, get_occurrences
from app.tasks import create_task


@pytest.fixture
def db_path(tmp_path):
    """Create an isolated SQLite database for each test."""

    path = tmp_path / "tempo_test.db"
    initialize_database(path)
    return path


def make_occurrence(db_path, target_date=date(2026, 11, 11)):
    """Create a recurring task and one scheduled occurrence."""

    task = create_task(
        TaskCreate(
            title="Morning stretching",
            task_type="recurring",
            recurrence_rule="daily",
            preferred_time="08:30",
            estimated_minutes=15,
        ),
        db_path=db_path,
    )

    generate_occurrences(target_date, target_date, db_path)

    occurrence = get_occurrences(target_date, db_path)[0]

    return task, occurrence["id"]


def get_status(db_path, occurrence_id):
    """Retrieve the status and completion timestamp."""

    conn = get_connection(db_path)

    try:
        return conn.execute(
            """
            SELECT status, completed_at
            FROM task_occurrences
            WHERE id = ?
            """,
            (occurrence_id,),
        ).fetchone()

    finally:
        conn.close()


def test_complete_occurrence(db_path):
    task, occurrence_id = make_occurrence(db_path)

    complete_occurrence(
        occurrence_id,
        actual_minutes=20,
        notes="Completed successfully",
        db_path=db_path,
    )

    status = get_status(db_path, occurrence_id)

    assert status["status"] == "completed"
    assert status["completed_at"] is not None

    history = get_task_history(task.id, db_path)

    assert len(history) == 1
    assert history[0]["actual_minutes"] == 20
    assert history[0]["notes"] == "Completed successfully"


def test_complete_without_actual_minutes(db_path):
    task, occurrence_id = make_occurrence(db_path)

    complete_occurrence(occurrence_id, db_path=db_path)

    history = get_task_history(task.id, db_path)

    assert len(history) == 1
    assert history[0]["actual_minutes"] is None


def test_complete_with_zero_minutes(db_path):
    task, occurrence_id = make_occurrence(db_path)

    complete_occurrence(
        occurrence_id,
        actual_minutes=0,
        db_path=db_path,
    )

    history = get_task_history(task.id, db_path)

    assert history[0]["actual_minutes"] == 0


@pytest.mark.parametrize(
    "invalid_minutes",
    [-1, -10, 2.5, "20", True],
)
def test_invalid_actual_minutes(db_path, invalid_minutes):
    _, occurrence_id = make_occurrence(db_path)

    with pytest.raises(ValueError):
        complete_occurrence(
            occurrence_id,
            actual_minutes=invalid_minutes,
            db_path=db_path,
        )

    assert get_status(db_path, occurrence_id)["status"] == "pending"


def test_complete_nonexistent_occurrence(db_path):
    with pytest.raises(ValueError, match="does not exist"):
        complete_occurrence(9999, db_path=db_path)


def test_cannot_complete_twice(db_path):
    task, occurrence_id = make_occurrence(db_path)

    complete_occurrence(
        occurrence_id,
        actual_minutes=20,
        db_path=db_path,
    )

    with pytest.raises(ValueError, match="pending"):
        complete_occurrence(
            occurrence_id,
            actual_minutes=30,
            db_path=db_path,
        )

    history = get_task_history(task.id, db_path)

    assert len(history) == 1
    assert history[0]["actual_minutes"] == 20


def test_skip_occurrence(db_path):
    task, occurrence_id = make_occurrence(db_path)

    skip_occurrence(occurrence_id, db_path=db_path)

    status = get_status(db_path, occurrence_id)

    assert status["status"] == "skipped"
    assert status["completed_at"] is None

    assert get_task_history(task.id, db_path) == []


def test_skip_nonexistent_occurrence(db_path):
    with pytest.raises(ValueError, match="does not exist"):
        skip_occurrence(9999, db_path=db_path)


def test_cannot_skip_completed_occurrence(db_path):
    _, occurrence_id = make_occurrence(db_path)

    complete_occurrence(occurrence_id, db_path=db_path)

    with pytest.raises(ValueError, match="pending"):
        skip_occurrence(occurrence_id, db_path=db_path)


def test_cannot_complete_skipped_occurrence(db_path):
    _, occurrence_id = make_occurrence(db_path)

    skip_occurrence(occurrence_id, db_path=db_path)

    with pytest.raises(ValueError, match="pending"):
        complete_occurrence(occurrence_id, db_path=db_path)


def test_history_is_persistent(db_path):
    task, occurrence_id = make_occurrence(db_path)

    complete_occurrence(
        occurrence_id,
        actual_minutes=25,
        db_path=db_path,
    )

    history = get_task_history(task.id, db_path)

    assert len(history) == 1
    assert history[0]["actual_minutes"] == 25


def test_history_for_nonexistent_task(db_path):
    assert get_task_history(9999, db_path) == []


def test_multiple_occurrences_have_separate_history(db_path):
    task, first_id = make_occurrence(
        db_path,
        date(2026, 11, 11),
    )

    generate_occurrences(
        date(2026, 11, 12),
        date(2026, 11, 12),
        db_path,
    )

    second_id = get_occurrences(
        date(2026, 11, 12),
        db_path,
    )[0]["id"]

    complete_occurrence(
        first_id,
        actual_minutes=15,
        db_path=db_path,
    )

    complete_occurrence(
        second_id,
        actual_minutes=25,
        db_path=db_path,
    )

    history = get_task_history(task.id, db_path)

    assert len(history) == 2
    assert history[0]["scheduled_date"] == "2026-11-12"
    assert history[0]["actual_minutes"] == 25
    assert history[1]["scheduled_date"] == "2026-11-11"
    assert history[1]["actual_minutes"] == 15
