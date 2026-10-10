
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, date

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "qfarm.db"

ALLOWED_TASKS = {
    "soil",
    "leaves",
    "pepper",
    "drainage",
    "shade",
    "weeds",
    "mulch",
    "support",
    "disease",
    "flowering",
}

ALLOWED_STATUSES = {"done", "skipped"}


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS farm_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_key TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN ('done', 'skipped')),
                recorded_at TEXT NOT NULL,
                task_date TEXT
            )
        """)

        # Upgrade an existing database without deleting its history.
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(farm_tasks)"
            ).fetchall()
        }

        if "task_date" not in columns:
            connection.execute(
                "ALTER TABLE farm_tasks ADD COLUMN task_date TEXT"
            )

        # Preserve older records by assigning their original UTC date.
        connection.execute("""
            UPDATE farm_tasks
            SET task_date = substr(recorded_at, 1, 10)
            WHERE task_date IS NULL
              AND recorded_at IS NOT NULL
        """)


def record_task(task_key, status):
    if not isinstance(task_key, str) or task_key not in ALLOWED_TASKS:
        raise ValueError("Unknown task.")

    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        raise ValueError("Status must be done or skipped.")

    recorded_at = datetime.now(timezone.utc).isoformat()
    task_date = date.today().isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO farm_tasks
                (task_key, status, recorded_at, task_date)
            VALUES (?, ?, ?, ?)
            """,
            (task_key, status, recorded_at, task_date),
        )

    return {
        "task_key": task_key,
        "status": status,
        "recorded_at": recorded_at,
        "task_date": task_date,
    }


def get_task_history(limit=50):
    limit = max(1, min(int(limit), 200))

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, task_key, status, recorded_at, task_date
            FROM farm_tasks
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_today_task_history():
    today = date.today().isoformat()

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, task_key, status, recorded_at, task_date
            FROM farm_tasks
            WHERE task_date = ?
            ORDER BY id DESC
            """,
            (today,),
        ).fetchall()

    return [dict(row) for row in rows]


initialize_database()