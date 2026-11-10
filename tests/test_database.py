import sqlite3
import pytest

from app.database import get_connection, initialize_database


@pytest.fixture
def db_path(tmp_path):
    """A fresh, initialized temporary database (never the real data/tempo.db)."""
    path = tmp_path / "test.db"
    initialize_database(path)
    return path


def test_initialize_twice(db_path):
    conn = get_connection(db_path)
    conn.execute("INSERT INTO tasks (title) VALUES ('keep me')")
    conn.commit()
    conn.close()

    initialize_database(db_path)  # second run must not delete or duplicate

    conn = get_connection(db_path)
    rows = conn.execute("SELECT title FROM tasks").fetchall()
    conn.close()
    assert [r["title"] for r in rows] == ["keep me"]


def test_foreign_keys_enabled(db_path):
    conn = get_connection(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO task_occurrences (task_id, scheduled_date) "
            "VALUES (?, ?)",
            (9999, "2026-11-11"),  # no task with id 9999 exists
        )
    conn.close()


def test_invalid_recurrence(db_path):
    conn = get_connection(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (title, task_type, recurrence_rule) "
            "VALUES (?, ?, ?)",
            ("Bad rule", "recurring", "hourly"),  # unsupported rule
        )
    conn.close()