
"""Task management operations for Tempo."""

from dataclasses import asdict
from datetime import date, datetime

from app.database import get_connection
from app.models import Task, TaskCreate, task_from_row


PRIORITIES = {"low", "medium", "high"}
TASK_TYPES = {"one_time", "recurring"}
RECURRENCE_RULES = {"none", "daily", "weekdays", "weekly"}

EDITABLE_FIELDS = {
    "title",
    "description",
    "category",
    "priority",
    "estimated_minutes",
    "task_type",
    "recurrence_rule",
    "recurrence_weekday",
    "preferred_time",
    "deadline",
}


def validate_task(data: TaskCreate) -> None:
    """Validate task fields and recurrence consistency."""

    if not isinstance(data.title, str) or not data.title.strip():
        raise ValueError("Task title cannot be empty.")

    if data.priority not in PRIORITIES:
        raise ValueError(
            f"Invalid priority: {data.priority}"
        )

    if (
        data.estimated_minutes is not None
        and (
            type(data.estimated_minutes) is not int
            or data.estimated_minutes <= 0
        )
    ):
        raise ValueError(
            "Estimated duration must be a positive integer."
        )

    if data.task_type not in TASK_TYPES:
        raise ValueError(
            f"Invalid task type: {data.task_type}"
        )

    if data.recurrence_rule not in RECURRENCE_RULES:
        raise ValueError(
            f"Invalid recurrence rule: {data.recurrence_rule}"
        )

    if data.task_type == "one_time":
        if data.recurrence_rule != "none":
            raise ValueError(
                "One-time tasks cannot have recurrence rules."
            )

    if data.task_type == "recurring":
        if data.recurrence_rule == "none":
            raise ValueError(
                "Recurring tasks require a recurrence rule."
            )

    if data.recurrence_rule == "weekly":
        if (
            type(data.recurrence_weekday) is not int
            or not 0 <= data.recurrence_weekday <= 6
        ):
            raise ValueError(
                "Weekly tasks require a weekday from 0 to 6."
            )
    elif data.recurrence_weekday is not None:
        raise ValueError(
            "Only weekly tasks can specify a recurrence weekday."
        )

    if data.preferred_time is not None:
        try:
            parsed = datetime.strptime(
                data.preferred_time, "%H:%M"
            )
            if parsed.strftime("%H:%M") != data.preferred_time:
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError(
                "Preferred time must use HH:MM format."
            ) from None

    if data.deadline is not None:
        try:
            if "T" in data.deadline:
                datetime.fromisoformat(data.deadline)
            else:
                date.fromisoformat(data.deadline)
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "Deadline must be a valid ISO date or datetime."
            ) from None


def get_task(
    task_id: int,
    db_path=None,
) -> Task | None:
    """Retrieve a task by its ID."""

    conn = get_connection(db_path)

    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            return None

        return task_from_row(row)

    finally:
        conn.close()


def create_task(
    data: TaskCreate,
    db_path=None,
) -> Task:
    """Validate, insert, and return a new task."""

    validate_task(data)

    conn = get_connection(db_path)

    try:
        with conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    title,
                    description,
                    category,
                    priority,
                    estimated_minutes,
                    task_type,
                    recurrence_rule,
                    recurrence_weekday,
                    preferred_time,
                    deadline
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.title.strip(),
                    data.description,
                    data.category,
                    data.priority,
                    data.estimated_minutes,
                    data.task_type,
                    data.recurrence_rule,
                    data.recurrence_weekday,
                    data.preferred_time,
                    data.deadline,
                ),
            )

            task_id = cursor.lastrowid

        return get_task(task_id, db_path)

    finally:
        conn.close()


def list_tasks(
    db_path=None,
    active_only: bool = True,
    priority: str | None = None,
    category: str | None = None,
) -> list[Task]:
    """List tasks with optional filters."""

    if priority is not None and priority not in PRIORITIES:
        raise ValueError("Invalid priority filter.")

    conn = get_connection(db_path)

    try:
        query = "SELECT * FROM tasks WHERE 1 = 1"
        parameters = []

        if active_only:
            query += " AND is_active = ?"
            parameters.append(1)

        if priority is not None:
            query += " AND priority = ?"
            parameters.append(priority)

        if category is not None:
            query += " AND category = ?"
            parameters.append(category)

        query += " ORDER BY id"

        rows = conn.execute(
            query, parameters
        ).fetchall()

        return [task_from_row(row) for row in rows]

    finally:
        conn.close()


def update_task(
    task_id: int,
    changes: dict,
    db_path=None,
) -> Task:
    """Update selected fields of an existing task."""

    if not changes:
        raise ValueError("No changes provided.")

    unknown = set(changes) - EDITABLE_FIELDS

    if unknown:
        raise ValueError(
            f"Unknown or non-editable fields: {sorted(unknown)}"
        )

    existing = get_task(task_id, db_path)

    if existing is None:
        raise ValueError(f"Task {task_id} does not exist.")

    # Build the complete proposed task state.
    current_data = {
        field: getattr(existing, field)
        for field in EDITABLE_FIELDS
    }

    current_data.update(changes)

    proposed = TaskCreate(**current_data)
    validate_task(proposed)

    # Store normalized title, just as create_task does.
    if "title" in changes:
        changes = {
            **changes,
            "title": proposed.title.strip(),
        }

    columns = ", ".join(
        f"{field} = ?" for field in changes
    )

    values = list(changes.values())
    values.append(task_id)

    conn = get_connection(db_path)

    try:
        with conn:
            conn.execute(
                f"UPDATE tasks SET {columns} WHERE id = ?",
                values,
            )

        return get_task(task_id, db_path)

    finally:
        conn.close()


def archive_task(
    task_id: int,
    db_path=None,
) -> None:
    """Archive a task without deleting its history."""

    conn = get_connection(db_path)

    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE tasks
                SET is_active = 0
                WHERE id = ?
                """,
                (task_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    f"Task {task_id} does not exist."
                )

    finally:
        conn.close()