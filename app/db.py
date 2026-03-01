import sqlite3
from contextlib import contextmanager

from .config import DB_PATH


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shift_codes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    color TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_levels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_codes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nurses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department_id TEXT NOT NULL,
    job_level_id TEXT NOT NULL,
    skills_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT '在職',
    notes TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(department_id) REFERENCES departments(id),
    FOREIGN KEY(job_level_id) REFERENCES job_levels(id)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    active_snapshot_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    snapshot_type TEXT NOT NULL DEFAULT 'manual',
    title TEXT NOT NULL,
    assignments_json TEXT NOT NULL DEFAULT '[]',
    selected_rule_ids_json TEXT NOT NULL DEFAULT '[]',
    ui_state_json TEXT NOT NULL DEFAULT '{}',
    optimization_job_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT,
    rule_type TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    active_version_id INTEGER,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    source_nl TEXT NOT NULL DEFAULT '',
    dsl_text TEXT NOT NULL,
    reverse_text TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL,
    validation_report_json TEXT NOT NULL DEFAULT '{}',
    dsl_version TEXT NOT NULL DEFAULT '1.0',
    created_at TEXT NOT NULL,
    FOREIGN KEY(rule_id) REFERENCES rules(id)
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    nurse_id TEXT NOT NULL,
    date TEXT NOT NULL,
    shift_code_id TEXT NOT NULL,
    note TEXT DEFAULT '',
    source TEXT NOT NULL DEFAULT 'manual',
    version_tag TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, nurse_id, date),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(nurse_id) REFERENCES nurses(id),
    FOREIGN KEY(shift_code_id) REFERENCES shift_codes(id)
);

CREATE TABLE IF NOT EXISTS optimization_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    log_json TEXT NOT NULL DEFAULT '[]',
    result_assignments_json TEXT NOT NULL DEFAULT '[]',
    result_summary_json TEXT NOT NULL DEFAULT '{}',
    result_snapshot_id INTEGER,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(SCHEMA_SQL)
