import json
from datetime import datetime

from ..config import DEFAULT_PERIOD_FROM, DEFAULT_PERIOD_TO
from ..db import get_connection
from ..seed_data import (
    DEFAULT_DEPARTMENTS,
    DEFAULT_JOB_LEVELS,
    DEFAULT_NURSES,
    DEFAULT_PROJECT,
    DEFAULT_RULES,
    DEFAULT_SHIFT_CODES,
    DEFAULT_SKILLS,
    DEFAULT_UI_STATE,
    generate_default_assignments,
)
from .dsl_tools import validate_rule_dsl


MASTER_TABLES = {
    "departments": {"table": "departments", "fields": ["id", "name", "description", "active"]},
    "shift_codes": {"table": "shift_codes", "fields": ["id", "name", "start_time", "end_time", "color", "active"]},
    "job_levels": {"table": "job_levels", "fields": ["id", "name", "description", "active"]},
    "skill_codes": {"table": "skill_codes", "fields": ["id", "name", "description", "active"]},
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Repository:
    def _fetchall(self, query: str, params: tuple = ()) -> list[dict]:
        with get_connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _fetchone(self, query: str, params: tuple = ()) -> dict | None:
        with get_connection() as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row) if row else None

    def _execute(self, query: str, params: tuple = ()) -> int:
        with get_connection() as connection:
            cursor = connection.execute(query, params)
            return cursor.lastrowid

    def list_master(self, resource: str) -> list[dict]:
        if resource == "nurses":
            rows = self._fetchall(
                """
                SELECT nurses.*, departments.name AS department_name, job_levels.name AS job_level_name
                FROM nurses
                JOIN departments ON departments.id = nurses.department_id
                JOIN job_levels ON job_levels.id = nurses.job_level_id
                ORDER BY nurses.id
                """
            )
            for row in rows:
                row["skills"] = json.loads(row.pop("skills_json"))
            return rows
        config = MASTER_TABLES[resource]
        return self._fetchall(f"SELECT * FROM {config['table']} ORDER BY id")

    def get_master(self, resource: str, record_id: str) -> dict | None:
        if resource == "nurses":
            row = self._fetchone("SELECT * FROM nurses WHERE id = ?", (record_id,))
            if row:
                row["skills"] = json.loads(row.pop("skills_json"))
            return row
        config = MASTER_TABLES[resource]
        return self._fetchone(f"SELECT * FROM {config['table']} WHERE id = ?", (record_id,))

    def create_master(self, resource: str, payload: dict) -> dict:
        timestamp = now_iso()
        with get_connection() as connection:
            if resource == "nurses":
                connection.execute(
                    """
                    INSERT INTO nurses (id, name, department_id, job_level_id, skills_json, status, notes, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["name"],
                        payload["department_id"],
                        payload["job_level_id"],
                        json.dumps(payload.get("skills", []), ensure_ascii=False),
                        payload.get("status", "在職"),
                        payload.get("notes", ""),
                        int(payload.get("active", 1)),
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                config = MASTER_TABLES[resource]
                fields = config["fields"]
                columns = ", ".join(fields + ["created_at", "updated_at"])
                placeholders = ", ".join(["?"] * (len(fields) + 2))
                values = [payload.get(field) for field in fields] + [timestamp, timestamp]
                connection.execute(
                    f"INSERT INTO {config['table']} ({columns}) VALUES ({placeholders})",
                    tuple(values),
                )
        self.add_audit("create", resource, payload["id"], payload)
        return self.get_master(resource, payload["id"])

    def update_master(self, resource: str, record_id: str, payload: dict) -> dict:
        timestamp = now_iso()
        with get_connection() as connection:
            if resource == "nurses":
                connection.execute(
                    """
                    UPDATE nurses
                    SET name = ?, department_id = ?, job_level_id = ?, skills_json = ?, status = ?, notes = ?, active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload["name"],
                        payload["department_id"],
                        payload["job_level_id"],
                        json.dumps(payload.get("skills", []), ensure_ascii=False),
                        payload.get("status", "在職"),
                        payload.get("notes", ""),
                        int(payload.get("active", 1)),
                        timestamp,
                        record_id,
                    ),
                )
            else:
                config = MASTER_TABLES[resource]
                fields = [field for field in config["fields"] if field != "id"]
                updates = ", ".join([f"{field} = ?" for field in fields] + ["updated_at = ?"])
                values = [payload.get(field) for field in fields] + [timestamp, record_id]
                connection.execute(
                    f"UPDATE {config['table']} SET {updates} WHERE id = ?",
                    tuple(values),
                )
        self.add_audit("update", resource, record_id, payload)
        return self.get_master(resource, record_id)

    def delete_master(self, resource: str, record_id: str) -> None:
        with get_connection() as connection:
            table = "nurses" if resource == "nurses" else MASTER_TABLES[resource]["table"]
            connection.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        self.add_audit("delete", resource, record_id, {})

    def create_project(self, name: str, description: str) -> dict:
        timestamp = now_iso()
        project_id = self._execute(
            "INSERT INTO projects (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (name, description, timestamp, timestamp),
        )
        self.add_audit("create", "projects", str(project_id), {"name": name, "description": description})
        return self.get_project(project_id)

    def get_project(self, project_id: int) -> dict | None:
        project = self._fetchone("SELECT * FROM projects WHERE id = ?", (project_id,))
        if not project:
            return None
        project["active_snapshot"] = self.get_snapshot(project.get("active_snapshot_id")) if project.get("active_snapshot_id") else None
        return project

    def list_projects(self) -> list[dict]:
        return self._fetchall("SELECT * FROM projects ORDER BY id")

    def get_snapshot(self, snapshot_id: int | None) -> dict | None:
        if not snapshot_id:
            return None
        snapshot = self._fetchone("SELECT * FROM project_snapshots WHERE id = ?", (snapshot_id,))
        if snapshot:
            snapshot["assignments"] = json.loads(snapshot["assignments_json"])
            snapshot["selected_rule_ids"] = json.loads(snapshot["selected_rule_ids_json"])
            snapshot["ui_state"] = json.loads(snapshot["ui_state_json"])
        return snapshot

    def list_snapshots(self, project_id: int) -> list[dict]:
        rows = self._fetchall(
            "SELECT * FROM project_snapshots WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        )
        for row in rows:
            row["ui_state"] = json.loads(row["ui_state_json"])
        return rows

    def list_assignments(self, project_id: int, start_text: str, end_text: str, department_id: str | None = None) -> list[dict]:
        query = """
            SELECT assignments.*, nurses.name AS nurse_name, nurses.department_id
            FROM assignments
            JOIN nurses ON nurses.id = assignments.nurse_id
            WHERE assignments.project_id = ?
              AND assignments.date >= ?
              AND assignments.date <= ?
        """
        params: list = [project_id, start_text, end_text]
        if department_id:
            query += " AND nurses.department_id = ?"
            params.append(department_id)
        query += " ORDER BY assignments.date, assignments.nurse_id"
        return self._fetchall(query, tuple(params))

    def replace_assignments(self, project_id: int, assignments: list[dict], source: str = "manual", version_tag: str = "") -> None:
        timestamp = now_iso()
        with get_connection() as connection:
            connection.execute("DELETE FROM assignments WHERE project_id = ?", (project_id,))
            connection.executemany(
                """
                INSERT INTO assignments (project_id, nurse_id, date, shift_code_id, note, source, version_tag, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        project_id,
                        item["nurse_id"],
                        item["date"],
                        item.get("shift_code") or item.get("shift_code_id"),
                        item.get("note", ""),
                        item.get("source", source),
                        item.get("version_tag", version_tag),
                        timestamp,
                        timestamp,
                    )
                    for item in assignments
                ],
            )

    def upsert_assignments(self, project_id: int, changes: list[dict], source: str = "manual") -> list[dict]:
        timestamp = now_iso()
        with get_connection() as connection:
            for item in changes:
                connection.execute(
                    """
                    INSERT INTO assignments (project_id, nurse_id, date, shift_code_id, note, source, version_tag, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(project_id, nurse_id, date)
                    DO UPDATE SET shift_code_id = excluded.shift_code_id, note = excluded.note, source = excluded.source, updated_at = excluded.updated_at
                    """,
                    (
                        project_id,
                        item["nurse_id"],
                        item["date"],
                        item["shift_code"],
                        item.get("note", ""),
                        source,
                        item.get("version_tag", ""),
                        timestamp,
                        timestamp,
                    ),
                )
        self.add_audit("update", "assignments", str(project_id), {"changes": changes})
        return changes

    def create_snapshot(self, project_id: int, title: str, snapshot_type: str = "manual", ui_state: dict | None = None, optimization_job_id: int | None = None) -> dict:
        assignments = self._fetchall("SELECT nurse_id, date, shift_code_id, note, source, version_tag FROM assignments WHERE project_id = ? ORDER BY date, nurse_id", (project_id,))
        rule_ids = [row["id"] for row in self.list_active_rules()]
        ui_state = ui_state or self.get_project_ui_state(project_id)
        snapshot_id = self._execute(
            """
            INSERT INTO project_snapshots (project_id, snapshot_type, title, assignments_json, selected_rule_ids_json, ui_state_json, optimization_job_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                snapshot_type,
                title,
                json.dumps(assignments, ensure_ascii=False),
                json.dumps(rule_ids, ensure_ascii=False),
                json.dumps(ui_state or {}, ensure_ascii=False),
                optimization_job_id,
                now_iso(),
            ),
        )
        self._execute("UPDATE projects SET active_snapshot_id = ?, updated_at = ? WHERE id = ?", (snapshot_id, now_iso(), project_id))
        self.add_audit("snapshot", "projects", str(project_id), {"snapshot_id": snapshot_id, "title": title})
        return self.get_snapshot(snapshot_id)

    def restore_snapshot(self, project_id: int, snapshot_id: int) -> dict | None:
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return None
        self.replace_assignments(project_id, snapshot["assignments"])
        self._execute("UPDATE projects SET active_snapshot_id = ?, updated_at = ? WHERE id = ?", (snapshot_id, now_iso(), project_id))
        self.add_audit("restore_snapshot", "projects", str(project_id), {"snapshot_id": snapshot_id})
        return self.get_project(project_id)

    def list_rules(self, scope_type: str | None = None, scope_id: str | None = None, rule_type: str | None = None, query_text: str | None = None) -> list[dict]:
        query = """
            SELECT rules.*, rule_versions.dsl_text, rule_versions.reverse_text, rule_versions.validation_status, rule_versions.validation_report_json
            FROM rules
            LEFT JOIN rule_versions ON rule_versions.id = rules.active_version_id
            WHERE rules.deleted_at IS NULL
        """
        params: list = []
        if scope_type:
            query += " AND rules.scope_type = ?"
            params.append(scope_type)
        if scope_id:
            query += " AND rules.scope_id = ?"
            params.append(scope_id)
        if rule_type:
            query += " AND rules.rule_type = ?"
            params.append(rule_type)
        if query_text:
            query += " AND rules.title LIKE ?"
            params.append(f"%{query_text}%")
        query += " ORDER BY rules.priority DESC, rules.updated_at DESC"
        rows = self._fetchall(query, tuple(params))
        for row in rows:
            row["validation_report"] = json.loads(row["validation_report_json"]) if row.get("validation_report_json") else {}
        return rows

    def list_active_rules(self) -> list[dict]:
        rows = self._fetchall(
            """
            SELECT rules.*, rule_versions.dsl_text
            FROM rules
            JOIN rule_versions ON rule_versions.id = rules.active_version_id
            WHERE rules.deleted_at IS NULL
            ORDER BY rules.priority DESC
            """
        )
        for row in rows:
            report = validate_rule_dsl(row["dsl_text"])
            row["document"] = report.get("normalized") or {}
            row["weight"] = row["document"].get("weight", 0)
        return rows

    def create_rule(self, payload: dict) -> dict:
        timestamp = now_iso()
        rule_id = self._execute(
            """
            INSERT INTO rules (title, scope_type, scope_id, rule_type, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["title"],
                payload["scope_type"],
                payload.get("scope_id"),
                payload["rule_type"],
                int(payload.get("priority", 100)),
                timestamp,
                timestamp,
            ),
        )
        self.add_audit("create", "rules", str(rule_id), payload)
        return self.get_rule(rule_id)

    def get_rule(self, rule_id: int) -> dict | None:
        return self._fetchone("SELECT * FROM rules WHERE id = ? AND deleted_at IS NULL", (rule_id,))

    def delete_rule(self, rule_id: int) -> None:
        self._execute("UPDATE rules SET deleted_at = ?, updated_at = ? WHERE id = ?", (now_iso(), now_iso(), rule_id))
        self.add_audit("delete", "rules", str(rule_id), {})

    def create_rule_version(self, rule_id: int, source_nl: str, dsl_text: str, reverse_text: str, validation_report: dict) -> dict:
        version_id = self._execute(
            """
            INSERT INTO rule_versions (rule_id, source_nl, dsl_text, reverse_text, validation_status, validation_report_json, dsl_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                source_nl,
                dsl_text,
                reverse_text,
                validation_report["status"],
                json.dumps(validation_report, ensure_ascii=False),
                "1.0",
                now_iso(),
            ),
        )
        self._execute("UPDATE rules SET updated_at = ? WHERE id = ?", (now_iso(), rule_id))
        self.add_audit("create_version", "rules", str(rule_id), {"version_id": version_id})
        return self.get_rule_version(version_id)

    def get_rule_version(self, version_id: int) -> dict | None:
        row = self._fetchone("SELECT * FROM rule_versions WHERE id = ?", (version_id,))
        if row:
            row["validation_report"] = json.loads(row["validation_report_json"])
        return row

    def list_rule_versions(self, rule_id: int) -> list[dict]:
        rows = self._fetchall("SELECT * FROM rule_versions WHERE rule_id = ? ORDER BY id DESC", (rule_id,))
        for row in rows:
            row["validation_report"] = json.loads(row["validation_report_json"])
        return rows

    def activate_rule_version(self, rule_id: int, version_id: int) -> dict:
        self._execute("UPDATE rules SET active_version_id = ?, updated_at = ? WHERE id = ?", (version_id, now_iso(), rule_id))
        self.add_audit("activate_version", "rules", str(rule_id), {"version_id": version_id})
        return self.get_rule(rule_id)

    def create_optimization_job(self, project_id: int, request_payload: dict) -> dict:
        timestamp = now_iso()
        job_id = self._execute(
            """
            INSERT INTO optimization_jobs (project_id, request_json, status, progress, message, log_json, result_assignments_json, result_summary_json, created_at, updated_at)
            VALUES (?, ?, 'QUEUED', 0, '已建立任務', '[]', '[]', '{}', ?, ?)
            """,
            (project_id, json.dumps(request_payload, ensure_ascii=False), timestamp, timestamp),
        )
        self.add_audit("create", "optimization_jobs", str(job_id), request_payload)
        return self.get_optimization_job(job_id)

    def get_optimization_job(self, job_id: int) -> dict | None:
        job = self._fetchone("SELECT * FROM optimization_jobs WHERE id = ?", (job_id,))
        if not job:
            return None
        job["request"] = json.loads(job["request_json"])
        job["logs"] = json.loads(job["log_json"])
        job["result_assignments"] = json.loads(job["result_assignments_json"])
        job["result_summary"] = json.loads(job["result_summary_json"])
        return job

    def update_optimization_job(self, job_id: int, **fields) -> dict:
        if not fields:
            return self.get_optimization_job(job_id)
        timestamp = now_iso()
        serialized_fields = {}
        for key, value in fields.items():
            if key in {"request_json", "log_json", "result_assignments_json", "result_summary_json"}:
                serialized_fields[key] = value
            elif key in {"logs", "result_assignments", "result_summary"}:
                column = {"logs": "log_json", "result_assignments": "result_assignments_json", "result_summary": "result_summary_json"}[key]
                serialized_fields[column] = json.dumps(value, ensure_ascii=False)
            else:
                serialized_fields[key] = value
        serialized_fields["updated_at"] = timestamp
        assignments = ", ".join(f"{column} = ?" for column in serialized_fields)
        values = list(serialized_fields.values()) + [job_id]
        self._execute(f"UPDATE optimization_jobs SET {assignments} WHERE id = ?", tuple(values))
        return self.get_optimization_job(job_id)

    def cancel_optimization_job(self, job_id: int) -> dict:
        return self.update_optimization_job(job_id, cancel_requested=1, message="已要求取消")

    def get_settings(self) -> dict:
        rows = self._fetchall("SELECT key, value_json FROM app_settings")
        settings = {row["key"]: json.loads(row["value_json"]) for row in rows}
        return {
            "llm_mode": settings.get("llm_mode", "fallback"),
            "openai_model": settings.get("openai_model", "gpt-4.1-mini"),
            "openai_api_key": settings.get("openai_api_key", ""),
        }

    def save_settings(self, settings: dict) -> dict:
        timestamp = now_iso()
        with get_connection() as connection:
            for key, value in settings.items():
                connection.execute(
                    """
                    INSERT INTO app_settings (key, value_json, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
                    """,
                    (key, json.dumps(value, ensure_ascii=False), timestamp),
                )
        self.add_audit("update", "app_settings", "settings", settings)
        return self.get_settings()

    def get_project_ui_state(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        if project and project.get("active_snapshot"):
            return project["active_snapshot"].get("ui_state", {})
        return DEFAULT_UI_STATE

    def add_audit(self, action: str, entity_type: str, entity_id: str, payload: dict) -> None:
        self._execute(
            "INSERT INTO audit_log (action, entity_type, entity_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (action, entity_type, entity_id, json.dumps(payload, ensure_ascii=False), now_iso()),
        )

    def list_audit_logs(self, limit: int = 100) -> list[dict]:
        return self._fetchall("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))

    def bootstrap_defaults(self) -> None:
        if self._fetchone("SELECT id FROM departments LIMIT 1") is None:
            for item in DEFAULT_DEPARTMENTS:
                self.create_master("departments", item)
        if self._fetchone("SELECT id FROM shift_codes LIMIT 1") is None:
            for item in DEFAULT_SHIFT_CODES:
                self.create_master("shift_codes", item)
        if self._fetchone("SELECT id FROM job_levels LIMIT 1") is None:
            for item in DEFAULT_JOB_LEVELS:
                self.create_master("job_levels", item)
        if self._fetchone("SELECT id FROM skill_codes LIMIT 1") is None:
            for item in DEFAULT_SKILLS:
                self.create_master("skill_codes", item)
        if self._fetchone("SELECT id FROM nurses LIMIT 1") is None:
            for item in DEFAULT_NURSES:
                self.create_master("nurses", item)

        if self._fetchone("SELECT id FROM projects LIMIT 1") is None:
            project = self.create_project(DEFAULT_PROJECT["name"], DEFAULT_PROJECT["description"])
        else:
            project = self.list_projects()[0]

        if self._fetchone("SELECT id FROM rules LIMIT 1") is None:
            for rule in DEFAULT_RULES:
                created_rule = self.create_rule(rule)
                report = validate_rule_dsl(
                    rule["dsl_text"],
                    lookup={
                        "departments": {item["id"] for item in self.list_master("departments")},
                        "nurses": {item["id"] for item in self.list_master("nurses")},
                    },
                )
                version = self.create_rule_version(
                    created_rule["id"],
                    rule["source_nl"],
                    rule["dsl_text"],
                    rule["source_nl"],
                    report,
                )
                self.activate_rule_version(created_rule["id"], version["id"])

        if self._fetchone("SELECT id FROM assignments LIMIT 1") is None:
            assignments = generate_default_assignments(DEFAULT_PERIOD_FROM, DEFAULT_PERIOD_TO, self.list_master("nurses"))
            self.replace_assignments(project["id"], assignments, source="seed", version_tag="seed-v1")

        if self._fetchone("SELECT id FROM project_snapshots LIMIT 1") is None:
            self.create_snapshot(project["id"], "初始化快照", snapshot_type="seed", ui_state=DEFAULT_UI_STATE)

        if self._fetchone("SELECT key FROM app_settings LIMIT 1") is None:
            self.save_settings({"llm_mode": "fallback", "openai_model": "gpt-4.1-mini", "openai_api_key": ""})
