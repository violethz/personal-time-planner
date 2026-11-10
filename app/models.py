
"""Data models for Tempo's task management system."""

import sqlite3
from dataclasses import dataclass


@dataclass
class TaskCreate:
    """Input data required to create a new task."""

    title: str
    description: str | None = None
    category: str | None = None
    priority: str = "medium"
    estimated_minutes: int | None = None
    task_type: str = "one_time"
    recurrence_rule: str = "none"
    recurrence_weekday: int | None = None
    preferred_time: str | None = None
    deadline: str | None = None


@dataclass
class Task:
    """A task already stored in the SQLite database."""

    id: int
    title: str
    description: str | None
    category: str | None
    priority: str
    estimated_minutes: int | None
    task_type: str
    recurrence_rule: str
    recurrence_weekday: int | None
    preferred_time: str | None
    deadline: str | None
    created_at: str
    is_active: bool


def task_from_row(row: sqlite3.Row) -> Task:
    """Convert a SQLite database row into a Task object."""

    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        priority=row["priority"],
        estimated_minutes=row["estimated_minutes"],
        task_type=row["task_type"],
        recurrence_rule=row["recurrence_rule"],
        recurrence_weekday=row["recurrence_weekday"],
        preferred_time=row["preferred_time"],
        deadline=row["deadline"],
        created_at=row["created_at"],
        is_active=bool(row["is_active"]),
    )
