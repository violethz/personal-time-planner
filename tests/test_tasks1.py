"""Tests for Tempo task CRUD operations."""

import pytest

from app.database import initialize_database
from app.models import TaskCreate
from app.tasks import (
    archive_task,
    create_task,
    get_task,
    list_tasks,
    update_task,
    validate_task,
)


@pytest.fixture
def db_path(tmp_path):
    """A fresh, initialized temporary database for testing tasks."""
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def test_create_task(db_path):
    task = create_task(
        TaskCreate(
            title="AI Quant Lab",
            category="project",
            priority="high",
            estimated_minutes=120,
        ),
        db_path=db_path,
    )
    assert task.id is not None
    assert task.title == "AI Quant Lab"
    assert task.category == "project"
    assert task.priority == "high"
    assert task.estimated_minutes == 120
    assert task.task_type == "one_time"
    assert task.recurrence_rule == "none"
    assert task.recurrence_weekday is None
    assert task.is_active is True


def test_create_task_strips_title(db_path):
    task = create_task(
        TaskCreate(title="  Spaced Title  "),
        db_path=db_path,
    )
    assert task.title == "Spaced Title"


def test_create_recurring_task(db_path):
    task = create_task(
        TaskCreate(
            title="Weekly Review",
            task_type="recurring",
            recurrence_rule="weekly",
            recurrence_weekday=1,
            preferred_time="09:00",
        ),
        db_path=db_path,
    )
    assert task.task_type == "recurring"
    assert task.recurrence_rule == "weekly"
    assert task.recurrence_weekday == 1
    assert task.preferred_time == "09:00"


def test_get_task(db_path):
    created = create_task(TaskCreate(title="Read paper"), db_path=db_path)
    fetched = get_task(created.id, db_path=db_path)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.title == "Read paper"

    # Non-existent ID returns None
    assert get_task(9999, db_path=db_path) is None


def test_update_task(db_path):
    task = create_task(
        TaskCreate(title="Initial", estimated_minutes=30),
        db_path=db_path,
    )
    updated = update_task(
        task.id,
        {"estimated_minutes": 45, "title": "  Updated Title  "},
        db_path=db_path,
    )
    assert updated.estimated_minutes == 45
    assert updated.title == "Updated Title"

    refetched = get_task(task.id, db_path=db_path)
    assert refetched.estimated_minutes == 45
    assert refetched.title == "Updated Title"


def test_update_task_invalid_inputs(db_path):
    task = create_task(TaskCreate(title="Valid task"), db_path=db_path)

    # Empty changes dictionary
    with pytest.raises(ValueError, match="No changes provided"):
        update_task(task.id, {}, db_path=db_path)

    # Non-existent task
    with pytest.raises(ValueError, match="does not exist"):
        update_task(9999, {"title": "New"}, db_path=db_path)

    # Unknown or non-editable field
    with pytest.raises(ValueError, match="Unknown or non-editable fields"):
        update_task(task.id, {"is_active": False}, db_path=db_path)

    # Validation failure on proposed state
    with pytest.raises(ValueError, match="Invalid priority"):
        update_task(task.id, {"priority": "urgent"}, db_path=db_path)


def test_list_tasks(db_path):
    create_task(
        TaskCreate(title="Task 1", category="work", priority="high"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="Task 2", category="work", priority="low"),
        db_path=db_path,
    )
    create_task(
        TaskCreate(title="Task 3", category="personal", priority="high"),
        db_path=db_path,
    )

    all_tasks = list_tasks(db_path=db_path)
    assert len(all_tasks) == 3

    work_tasks = list_tasks(db_path=db_path, category="work")
    assert len(work_tasks) == 2
    assert {t.title for t in work_tasks} == {"Task 1", "Task 2"}

    high_tasks = list_tasks(db_path=db_path, priority="high")
    assert len(high_tasks) == 2
    assert {t.title for t in high_tasks} == {"Task 1", "Task 3"}

    work_high = list_tasks(db_path=db_path, category="work", priority="high")
    assert len(work_high) == 1
    assert work_high[0].title == "Task 1"

    with pytest.raises(ValueError, match="Invalid priority filter"):
        list_tasks(db_path=db_path, priority="urgent")


def test_archive_task(db_path):
    task = create_task(TaskCreate(title="To be archived"), db_path=db_path)
    assert task.is_active is True

    archive_task(task.id, db_path=db_path)

    fetched = get_task(task.id, db_path=db_path)
    assert fetched.is_active is False

    active_tasks = list_tasks(db_path=db_path, active_only=True)
    assert task.id not in [t.id for t in active_tasks]

    all_tasks = list_tasks(db_path=db_path, active_only=False)
    assert task.id in [t.id for t in all_tasks]

    with pytest.raises(ValueError, match="does not exist"):
        archive_task(9999, db_path=db_path)


def test_validation_rules():
    # Empty title
    with pytest.raises(ValueError, match="Task title cannot be empty"):
        validate_task(TaskCreate(title="   "))

    # Invalid priority
    with pytest.raises(ValueError, match="Invalid priority"):
        validate_task(TaskCreate(title="Task", priority="critical"))

    # Non-positive or non-int estimated_minutes
    with pytest.raises(ValueError, match="Estimated duration must be a positive integer"):
        validate_task(TaskCreate(title="Task", estimated_minutes=0))
    with pytest.raises(ValueError, match="Estimated duration must be a positive integer"):
        validate_task(TaskCreate(title="Task", estimated_minutes=-10))

    # Invalid task_type
    with pytest.raises(ValueError, match="Invalid task type"):
        validate_task(TaskCreate(title="Task", task_type="habit"))

    # Invalid recurrence_rule
    with pytest.raises(ValueError, match="Invalid recurrence rule"):
        validate_task(TaskCreate(title="Task", recurrence_rule="monthly"))

    # One-time task with recurrence rule
    with pytest.raises(ValueError, match="One-time tasks cannot have recurrence rules"):
        validate_task(TaskCreate(title="Task", task_type="one_time", recurrence_rule="daily"))

    # Recurring task without recurrence rule
    with pytest.raises(ValueError, match="Recurring tasks require a recurrence rule"):
        validate_task(TaskCreate(title="Task", task_type="recurring", recurrence_rule="none"))

    # Weekly task without valid weekday
    with pytest.raises(ValueError, match="Weekly tasks require a weekday from 0 to 6"):
        validate_task(TaskCreate(title="Task", task_type="recurring", recurrence_rule="weekly"))
    with pytest.raises(ValueError, match="Weekly tasks require a weekday from 0 to 6"):
        validate_task(TaskCreate(title="Task", task_type="recurring", recurrence_rule="weekly", recurrence_weekday=7))

    # Non-weekly task with recurrence_weekday
    with pytest.raises(ValueError, match="Only weekly tasks can specify a recurrence weekday"):
        validate_task(TaskCreate(title="Task", task_type="recurring", recurrence_rule="daily", recurrence_weekday=1))

    # Invalid preferred_time format
    with pytest.raises(ValueError, match="Preferred time must use HH:MM format"):
        validate_task(TaskCreate(title="Task", preferred_time="9:00"))
    with pytest.raises(ValueError, match="Preferred time must use HH:MM format"):
        validate_task(TaskCreate(title="Task", preferred_time="25:00"))

    # Invalid deadline format
    with pytest.raises(ValueError, match="Deadline must be a valid ISO date or datetime"):
        validate_task(TaskCreate(title="Task", deadline="11-10-2026"))
