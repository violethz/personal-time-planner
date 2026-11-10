"""SQLite database layer for Tempo.

Time handling: all timestamps are stored as naive ISO 8601 strings in the
machine's LOCAL time (e.g. "2026-11-10T12:48:00"). Dates are "YYYY-MM-DD" and
times are "HH:MM". Explicit timezone handling is planned for a later mission.
"""

import os
import sqlite3
from pathlib import Path

# <project root>/data/tempo.db, computed from this file's location.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "tempo.db"
DB_PATH_ENV_VAR = "TEMPO_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL CHECK (length(trim(title)) > 0),
    description       TEXT,
    category          TEXT,
    priority          TEXT    NOT NULL DEFAULT 'medium'
                              CHECK (priority IN ('low', 'medium', 'high')),
    estimated_minutes INTEGER CHECK (estimated_minutes IS NULL
                                     OR estimated_minutes > 0),
    task_type         TEXT    NOT NULL DEFAULT 'one_time'
                              CHECK (task_type IN ('one_time', 'recurring')),
    recurrence_rule TEXT NOT NULL DEFAULT 'none'
        CHECK (recurrence_rule IN ('none', 'daily', 'weekdays', 'weekly')),
    recurrence_weekday INTEGER
        CHECK (recurrence_weekday IS NULL OR recurrence_weekday BETWEEN 0 AND 6),
    preferred_time    TEXT,   -- HH:MM
    deadline          TEXT,   -- ISO 8601 date or datetime
    created_at        TEXT    NOT NULL
                              DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    is_active         INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS task_occurrences (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        INTEGER NOT NULL,
    scheduled_date TEXT    NOT NULL,   -- YYYY-MM-DD
    start_time     TEXT,               -- planned start (HH:MM)
    end_time       TEXT,               -- planned end (HH:MM)
    status         TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'completed', 'skipped')),
    completed_at   TEXT,               -- ISO 8601 local timestamp
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE,
    UNIQUE (task_id, scheduled_date)   -- at most one occurrence per task per day
);

CREATE TABLE IF NOT EXISTS task_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    occurrence_id  INTEGER NOT NULL UNIQUE,   -- one occurrence -> one record
    actual_start   TEXT,
    actual_end     TEXT,
    actual_minutes INTEGER CHECK (actual_minutes IS NULL OR actual_minutes >= 0),
    notes          TEXT,
    FOREIGN KEY (occurrence_id) REFERENCES task_occurrences (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_occurrences_date
    ON task_occurrences (scheduled_date);
CREATE INDEX IF NOT EXISTS idx_occurrences_task
    ON task_occurrences (task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_active
    ON tasks (is_active);
"""


def resolve_db_path(db_path=None):
    """Pick the database path: argument > TEMPO_DB_PATH env var > default."""
    if db_path is not None:
        return str(db_path)
    env_path = os.environ.get(DB_PATH_ENV_VAR)
    if env_path:
        return env_path
    return str(DEFAULT_DB_PATH)


def get_connection(db_path=None):
    """Return a SQLite connection with foreign keys enabled."""
    path = resolve_db_path(db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row  # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")  # must be set per connection
    return conn


def initialize_database(db_path=None):
    """Create the required tables if they do not exist.
    
    Safe to call repeatedly: it only uses CREATE ... IF NOT EXISTS, so
    existing data is never deleted or duplicated.
    """
    conn = get_connection(db_path)
    try:
        with conn:  # commits on success, rolls back on error
            conn.executescript(SCHEMA)
    finally:
        conn.close()