
"""Tests for Tempo task CRUD operations."""

import sqlite3

import pytest

from app.database import initialize_database, get_connection
from app.models import Task, TaskCreate
from app.tasks import (
    create_task,
    get_task,
    list_tasks,
    update_task,
    archive_task,
)


@pytest.fixture
def db_path(tmp_path):
    """Create an isolated SQLite database for each test."""
    path = tmp_path / "tempo_test.db"
    initialize_database(path)
    return path


@pytest.fixture
def sample_task(db_path):
    """Create a sample task for testing."""
    return create_task(
        TaskCreate(
            title="AI Quant Lab",
            category="project",
            priority="high",
            estimated_minutes=120,
        ),
        db_path=db_path,
    )


def test_create_valid_task(db_path):
    task = create_task(
        TaskCreate(
            title="Read a book",
            category="routine",
            priority="medium",
            estimated_minutes=30,
        ),
        db_path=db_path,
    )

    assert isinstance(task, Task)
    assert isinstance(task.id, int)
    assert task.id > 0
    assert task.title == "Read a book"
    assert task.category == "routine"
    assert task.priority == "medium"
    assert task.estimated_minutes == 30
    assert task.task_type == "one_time"
    assert task.recurrence_rule == "none"
    assert task.is_active is True
    assert task.created_at is not None


def test_create_task_trims_title(db_path):
    task = create_task(
        TaskCreate(title="  Morning stretching  "),
        db_path=db_path,
    )

    assert task.title == "Morning stretching"


@pytest.mark.parametrize(
    "title",
    ["", " ", "   ", "\t\n"],
)
def test_reject_blank_title(db_path, title):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(title=title),
            db_path=db_path,
        )


@pytest.mark.parametrize(
    "priority",
    ["urgent", "HIGH", "critical", ""],
)
def test_reject_invalid_priority(db_path, priority):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(
                title="Test task",
                priority=priority,
            ),
            db_path=db_path,
        )


@pytest.mark.parametrize(
    "duration",
    [0, -1, -30, 1.5, "30", True],
)
def test_reject_invalid_duration(db_path, duration):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(
                title="Test task",
                estimated_minutes=duration,
            ),
            db_path=db_path,
        )


@pytest.mark.parametrize(
    "preferred_time",
    ["25:00", "12:60", "9:30", "abc", "24:00"],
)
def test_reject_invalid_time(db_path, preferred_time):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(
                title="Test task",
                preferred_time=preferred_time,
            ),
            db_path=db_path,
        )


@pytest.mark.parametrize(
    "deadline",
    ["2026-02-30", "2026-13-01", "invalid"],
)
def test_reject_invalid_deadline(db_path, deadline):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(
                title="Test task",
                deadline=deadline,
            ),
            db_path=db_path,
        )


@pytest.mark.parametrize(
    "task_type,recurrence_rule,weekday",
    [
        ("one_time", "daily", None),
        ("recurring", "none", None),
        ("recurring", "invalid", None),
        ("recurring", "weekly", None),
        ("recurring", "weekly", 7),
        ("recurring", "weekly", -1),
        ("recurring", "weekly", True),
        ("recurring", "daily", 2),
    ],
)
def test_reject_inconsistent_recurrence(
    db_path, task_type, recurrence_rule, weekday
):
    with pytest.raises(ValueError):
        create_task(
            TaskCreate(
                title="Test task",
                task_type=task_type,
                recurrence_rule=recurrence_rule,
                recurrence_weekday=weekday,
            ),
            db_path=db_path,
        )


def test_create_daily_recurring_task(db_path):
    task = create_task(
        TaskCreate(
            title="Write diary",
            task_type="recurring",
            recurrence_rule="daily",
            preferred_time="21:00",
            estimated_minutes=15,
        ),
        db_path=db_path,
    )

    assert task.task_type == "recurring"
    assert task.recurrence_rule == "daily"
    assert task.preferred_time == "21:00"
    assert task.recurrence_weekday is None


def test_create_weekly_recurring_task(db_path):
    task = create_task(
        TaskCreate(
            title="Weekly review",
            task_type="recurring",
            recurrence_rule="weekly",
            recurrence_weekday=0,
        ),
        db_path=db_path,
    )

    assert task.recurrence_weekday == 0
    assert task.recurrence_rule == "weekly"


def test_get_existing_task(sample_task, db_path):
    retrieved = get_task(sample_task.id, db_path=db_path)

    assert isinstance(retrieved, Task)
    assert retrieved.id == sample_task.id
    assert retrieved.title == sample_task.title
    assert retrieved.priority == sample_task.priority


def test_get_nonexistent_task(db_path):
    assert get_task(999999, db_path=db_path) is None


def test_list_tasks(db_path):
    create_task(
        TaskCreate(title="Stretching"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="Reading"),
        db_path=db_path,
    )

    tasks = list_tasks(db_path=db_path)

    assert len(tasks) == 2
    assert all(isinstance(task, Task) for task in tasks)
    assert [task.title for task in tasks] == [
        "Stretching",
        "Reading",
    ]


def test_list_empty_database(db_path):
    assert list_tasks(db_path=db_path) == []


def test_list_active_only(db_path):
    active = create_task(
        TaskCreate(title="Active task"),
        db_path=db_path,
    )
    archived = create_task(
        TaskCreate(title="Archived task"),
        db_path=db_path,
    )

    archive_task(archived.id, db_path=db_path)

    tasks = list_tasks(db_path=db_path)

    assert len(tasks) == 1
    assert tasks[0].id == active.id

    all_tasks = list_tasks(
        db_path=db_path,
        active_only=False,
    )

    assert len(all_tasks) == 2


def test_filter_by_priority(db_path):
    create_task(
        TaskCreate(title="Task A", priority="high"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="Task B", priority="low"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="Task C", priority="high"),
        db_path=db_path,
    )

    tasks = list_tasks(
        db_path=db_path,
        priority="high",
    )

    assert len(tasks) == 2
    assert all(task.priority == "high" for task in tasks)


def test_filter_by_category(db_path):
    create_task(
        TaskCreate(title="Stretch", category="routine"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="AI Quant", category="project"),
        db_path=db_path,
    )

    tasks = list_tasks(
        db_path=db_path,
        category="routine",
    )

    assert len(tasks) == 1
    assert tasks[0].title == "Stretch"


def test_filter_by_priority_and_category(db_path):
    create_task(
        TaskCreate(
            title="Task A",
            priority="high",
            category="project",
        ),
        db_path=db_path,
    )
    create_task(
        TaskCreate(
            title="Task B",
            priority="high",
            category="routine",
        ),
        db_path=db_path,
    )

    tasks = list_tasks(
        db_path=db_path,
        priority="high",
        category="project",
    )

    assert len(tasks) == 1
    assert tasks[0].title == "Task A"


def test_reject_invalid_priority_filter(db_path):
    with pytest.raises(ValueError):
        list_tasks(
            db_path=db_path,
            priority="urgent",
        )


def test_update_selected_fields(sample_task, db_path):
    updated = update_task(
        sample_task.id,
        {
            "priority": "medium",
            "estimated_minutes": 150,
        },
        db_path=db_path,
    )

    assert updated.priority == "medium"
    assert updated.estimated_minutes == 150
    assert updated.title == sample_task.title
    assert updated.category == sample_task.category
    assert updated.created_at == sample_task.created_at


def test_update_title_trims_whitespace(sample_task, db_path):
    updated = update_task(
        sample_task.id,
        {"title": "  Updated title  "},
        db_path=db_path,
    )

    assert updated.title == "Updated title"


def test_update_persists(sample_task, db_path):
    update_task(
        sample_task.id,
        {"priority": "low"},
        db_path=db_path,
    )

    retrieved = get_task(sample_task.id, db_path=db_path)

    assert retrieved.priority == "low"


@pytest.mark.parametrize(
    "field",
    ["id", "created_at", "is_active", "unknown_field"],
)
def test_reject_noneditable_field(sample_task, db_path, field):
    with pytest.raises(ValueError):
        update_task(
            sample_task.id,
            {field: "invalid"},
            db_path=db_path,
        )


def test_reject_empty_update(sample_task, db_path):
    with pytest.raises(ValueError):
        update_task(
            sample_task.id,
            {},
            db_path=db_path,
        )


def test_reject_invalid_final_state(sample_task, db_path):
    with pytest.raises(ValueError):
        update_task(
            sample_task.id,
            {"task_type": "recurring"},
            db_path=db_path,
        )

    unchanged = get_task(sample_task.id, db_path=db_path)

    assert unchanged.task_type == "one_time"
    assert unchanged.recurrence_rule == "none"


def test_update_nonexistent_task(db_path):
    with pytest.raises(ValueError):
        update_task(
            999999,
            {"priority": "high"},
            db_path=db_path,
        )


def test_archive_task(sample_task, db_path):
    archive_task(sample_task.id, db_path=db_path)

    retrieved = get_task(sample_task.id, db_path=db_path)

    assert retrieved is not None
    assert retrieved.is_active is False
    assert list_tasks(db_path=db_path) == []


def test_archive_nonexistent_task(db_path):
    with pytest.raises(ValueError):
        archive_task(999999, db_path=db_path)


def test_archive_preserves_occurrences_and_history(
    sample_task, db_path
):
    conn = get_connection(db_path)

    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO task_occurrences (
                    task_id, scheduled_date
                )
                VALUES (?, ?)
                """,
                (sample_task.id, "2026-11-11"),
            )

            occurrence_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO task_history (
                    occurrence_id, actual_minutes
                )
                VALUES (?, ?)
                """,
                (occurrence_id, 90),
            )
    finally:
        conn.close()

    archive_task(sample_task.id, db_path=db_path)

    conn = get_connection(db_path)

    try:
        occurrence = conn.execute(
            """
            SELECT * FROM task_occurrences
            WHERE id = ?
            """,
            (occurrence_id,),
        ).fetchone()

        history = conn.execute(
            """
            SELECT * FROM task_history
            WHERE occurrence_id = ?
            """,
            (occurrence_id,),
        ).fetchone()

        assert occurrence is not None
        assert history is not None
        assert history["actual_minutes"] == 90
    finally:
        conn.close()


def test_persistence_across_connections(db_path):
    created = create_task(
        TaskCreate(
            title="Persistent task",
            estimated_minutes=45,
        ),
        db_path=db_path,
    )

    retrieved = get_task(
        created.id,
        db_path=db_path,
    )

    assert retrieved is not None
    assert retrieved.title == "Persistent task"
    assert retrieved.estimated_minutes == 45


def test_database_constraints_still_apply(db_path):
    conn = get_connection(db_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        title, priority
                    )
                    VALUES (?, ?)
                    """,
                    ("Invalid task", "urgent"),
                )
    finally:
        conn.close()
