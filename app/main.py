import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import APP_TITLE, DEFAULT_PERIOD_FROM, DEFAULT_PERIOD_TO, LOG_DIR, STATIC_DIR
from .db import init_db
from .services.jobs import JobManager, format_sse
from .services.llm_service import LLMService
from .services.repository import Repository
from .services.rule_engine import evaluate_conflicts


log_path = LOG_DIR / "app.log"
logger = logging.getLogger("nurse-roster")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()
repository = Repository()
repository.bootstrap_defaults()
llm_service = LLMService(repository)
job_manager = JobManager(repository)


def ok(data):
    return {"ok": True, "data": data}


def fail(code: str, message: str, details=None, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"ok": False, "error": {"code": code, "message": message, "details": details}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未處理例外：%s", exc)
    return fail("INTERNAL_ERROR", "系統發生未預期錯誤，請稍後再試。", {"path": str(request.url.path)}, 500)


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""


class SnapshotCreateRequest(BaseModel):
    title: str
    snapshot_type: str = "manual"
    ui_state: dict = Field(default_factory=dict)
    optimization_job_id: int | None = None


class AssignmentChange(BaseModel):
    nurse_id: str
    date: str
    shift_code: str
    note: str = ""


class AssignmentUpdateRequest(BaseModel):
    project_id: int
    changes: list[AssignmentChange]
    snapshot_title: str = "手動調整"
    ui_state: dict = Field(default_factory=dict)


class RuleCreateRequest(BaseModel):
    title: str
    scope_type: str
    scope_id: str | None = None
    rule_type: str
    priority: int = 100


class RuleVersionFromNLRequest(BaseModel):
    text: str
    scope_type: str
    scope_id: str | None = None
    rule_type: str


class RuleVersionFromDSLRequest(BaseModel):
    dsl_text: str
    source_nl: str = ""


class PeriodRequest(BaseModel):
    from_: str = Field(alias="from")
    to: str


class SolverRequest(BaseModel):
    time_limit_sec: int = 30
    seed: int = 7


class OptimizationRequest(BaseModel):
    project_id: int
    period: PeriodRequest
    solver: SolverRequest
    weights: dict = Field(default_factory=lambda: {"multiplier": 1.0})
    coverage: dict
    snapshot_title: str = "最佳化結果"


class SettingRequest(BaseModel):
    llm_mode: str = "fallback"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key: str = ""


class DSLTestRequest(BaseModel):
    text: str = ""
    dsl_text: str = ""
    scope_type: str = "GLOBAL"
    scope_id: str | None = None
    rule_type: str = "HARD"


@app.get("/api/health")
def health():
    return ok({"status": "ok"})


@app.get("/api/bootstrap")
def bootstrap(project_id: int | None = None, from_date: str = Query(DEFAULT_PERIOD_FROM), to_date: str = Query(DEFAULT_PERIOD_TO)):
    project = repository.get_project(project_id or repository.list_projects()[0]["id"])
    nurses = repository.list_master("nurses")
    ui_state = project["active_snapshot"]["ui_state"] if project and project.get("active_snapshot") else {}
    coverage = ui_state.get("coverage", {})
    return ok(
        {
            "project": project,
            "projects": repository.list_projects(),
            "departments": repository.list_master("departments"),
            "shift_codes": repository.list_master("shift_codes"),
            "job_levels": repository.list_master("job_levels"),
            "skill_codes": repository.list_master("skill_codes"),
            "nurses": nurses,
            "rules": repository.list_rules(),
            "assignments": repository.list_assignments(project["id"], from_date, to_date),
            "snapshots": repository.list_snapshots(project["id"]),
            "settings": {**repository.get_settings(), "openai_api_key": ""},
            "conflicts": evaluate_conflicts(nurses, repository.list_assignments(project["id"], from_date, to_date), repository.list_active_rules(), from_date, to_date, coverage),
            "audit_logs": repository.list_audit_logs(50),
        }
    )


@app.post("/api/projects")
def create_project(request_body: ProjectCreateRequest):
    return ok(repository.create_project(request_body.name, request_body.description))


@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="找不到專案")
    return ok(project)


@app.post("/api/projects/{project_id}/snapshots")
def create_snapshot(project_id: int, request_body: SnapshotCreateRequest):
    return ok(repository.create_snapshot(project_id, request_body.title, request_body.snapshot_type, request_body.ui_state, request_body.optimization_job_id))


@app.get("/api/projects/{project_id}/snapshots")
def list_snapshots(project_id: int):
    return ok(repository.list_snapshots(project_id))


@app.post("/api/projects/{project_id}/restore/{snapshot_id}")
def restore_snapshot(project_id: int, snapshot_id: int):
    project = repository.restore_snapshot(project_id, snapshot_id)
    if not project:
        raise HTTPException(status_code=404, detail="找不到快照")
    return ok(project)


@app.get("/api/schedule/assignments")
def list_assignments(project_id: int, from_date: str = Query(alias="from"), to_date: str = Query(alias="to"), department_id: str | None = None):
    return ok(repository.list_assignments(project_id, from_date, to_date, department_id))


@app.put("/api/schedule/assignments")
def update_assignments(request_body: AssignmentUpdateRequest):
    repository.upsert_assignments(request_body.project_id, [item.model_dump() for item in request_body.changes], source="manual")
    snapshot = repository.create_snapshot(request_body.project_id, request_body.snapshot_title, "manual", request_body.ui_state)
    return ok({"changes": [item.model_dump() for item in request_body.changes], "snapshot": snapshot})


@app.get("/api/schedule/conflicts")
def get_conflicts(project_id: int, from_date: str = Query(alias="from"), to_date: str = Query(alias="to")):
    nurses = repository.list_master("nurses")
    assignments = repository.list_assignments(project_id, from_date, to_date)
    coverage = repository.get_project_ui_state(project_id).get("coverage", {})
    return ok(evaluate_conflicts(nurses, assignments, repository.list_active_rules(), from_date, to_date, coverage))


@app.get("/api/{resource}")
def list_resource(resource: str):
    if resource not in {"nurses", "departments", "shift_codes", "job_levels", "skill_codes"}:
        raise HTTPException(status_code=404, detail="找不到資源")
    return ok(repository.list_master(resource))


@app.post("/api/{resource}")
def create_resource(resource: str, request_body: dict):
    if resource not in {"nurses", "departments", "shift_codes", "job_levels", "skill_codes"}:
        raise HTTPException(status_code=404, detail="找不到資源")
    return ok(repository.create_master(resource, request_body))


@app.put("/api/{resource}/{record_id}")
def update_resource(resource: str, record_id: str, request_body: dict):
    if resource not in {"nurses", "departments", "shift_codes", "job_levels", "skill_codes"}:
        raise HTTPException(status_code=404, detail="找不到資源")
    return ok(repository.update_master(resource, record_id, request_body))


@app.delete("/api/{resource}/{record_id}")
def delete_resource(resource: str, record_id: str):
    if resource not in {"nurses", "departments", "shift_codes", "job_levels", "skill_codes"}:
        raise HTTPException(status_code=404, detail="找不到資源")
    repository.delete_master(resource, record_id)
    return ok({"deleted": record_id})


@app.get("/api/rules")
def list_rules(scope_type: str | None = None, scope_id: str | None = None, type: str | None = None, q: str | None = None):
    return ok(repository.list_rules(scope_type, scope_id, type, q))


@app.post("/api/rules")
def create_rule(request_body: RuleCreateRequest):
    return ok(repository.create_rule(request_body.model_dump()))


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: int):
    repository.delete_rule(rule_id)
    return ok({"deleted": rule_id})


@app.post("/api/rules/{rule_id}/versions:from_nl")
def create_rule_version_from_nl(rule_id: int, request_body: RuleVersionFromNLRequest):
    rule = repository.get_rule(rule_id)
    if not rule:
        return fail("RULE_NOT_FOUND", "找不到規則。", status_code=404)

    def generator():
        final_payload = None
        for event in llm_service.translate_rule_events(request_body.text, request_body.scope_type, request_body.scope_id, request_body.rule_type):
            if event["event"] == "result":
                validation_report = event["data"]["validation_report"]
                version = repository.create_rule_version(
                    rule_id,
                    request_body.text,
                    event["data"]["dsl_text"],
                    event["data"]["reverse_text"],
                    validation_report,
                )
                final_payload = {"version": version, "rule_id": rule_id}
                yield format_sse("result", final_payload)
            else:
                yield format_sse(event["event"], event["data"])
        if final_payload is None:
            yield format_sse("error", {"message": "未產生可儲存的版本。"})

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/api/rules/{rule_id}/versions:from_dsl")
def create_rule_version_from_dsl(rule_id: int, request_body: RuleVersionFromDSLRequest):
    rule = repository.get_rule(rule_id)
    if not rule:
        return fail("RULE_NOT_FOUND", "找不到規則。", status_code=404)
    result = llm_service.validate_manual_dsl(request_body.dsl_text)
    version = repository.create_rule_version(
        rule_id,
        request_body.source_nl,
        request_body.dsl_text,
        result["reverse_text"],
        result["validation_report"],
    )
    return ok({"version": version, "reverse_text": result["reverse_text"]})


@app.post("/api/rules/{rule_id}/activate/{version_id}")
def activate_rule_version(rule_id: int, version_id: int):
    repository.activate_rule_version(rule_id, version_id)
    return ok({"rule_id": rule_id, "version_id": version_id})


@app.get("/api/rules/{rule_id}/versions")
def list_rule_versions(rule_id: int):
    return ok(repository.list_rule_versions(rule_id))


@app.get("/api/dsl/reverse_translate")
def reverse_translate(dsl_text: str):
    return ok(llm_service.validate_manual_dsl(dsl_text))


@app.post("/api/dsl/test")
def dsl_test(request_body: DSLTestRequest):
    def generator():
        if request_body.text.strip():
            for event in llm_service.translate_rule_events(
                request_body.text,
                request_body.scope_type,
                request_body.scope_id,
                request_body.rule_type,
            ):
                yield format_sse(event["event"], event["data"])
            return
        result = llm_service.validate_manual_dsl(request_body.dsl_text)
        yield format_sse("validation", result["validation_report"])
        yield format_sse("reverse", {"text": result["reverse_text"]})
        yield format_sse("result", result)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.post("/api/optimization/jobs")
def create_optimization_job(request_body: OptimizationRequest):
    payload = request_body.model_dump(by_alias=True)
    payload["period"] = {"from": payload["period"]["from"], "to": payload["period"]["to"]}
    job = repository.create_optimization_job(request_body.project_id, payload)
    job_manager.start(job["id"])
    return ok(job)


@app.get("/api/optimization/jobs/{job_id}")
def get_optimization_job(job_id: int):
    job = repository.get_optimization_job(job_id)
    if not job:
        return fail("JOB_NOT_FOUND", "找不到最佳化任務。", status_code=404)
    return ok(job)


@app.get("/api/optimization/jobs/{job_id}/stream")
def stream_optimization_job(job_id: int):
    job = repository.get_optimization_job(job_id)
    if not job:
        return fail("JOB_NOT_FOUND", "找不到最佳化任務。", status_code=404)
    return StreamingResponse(job_manager.stream(job_id), media_type="text/event-stream")


@app.post("/api/optimization/jobs/{job_id}/cancel")
def cancel_optimization_job(job_id: int):
    return ok(repository.cancel_optimization_job(job_id))


@app.post("/api/optimization/jobs/{job_id}/apply")
def apply_optimization_job(job_id: int):
    job = repository.get_optimization_job(job_id)
    if not job:
        return fail("JOB_NOT_FOUND", "找不到最佳化任務。", status_code=404)
    if job["status"] != "SUCCEEDED":
        return fail("JOB_NOT_READY", "任務尚未完成，無法套用。")
    repository.replace_assignments(job["project_id"], job["result_assignments"], source="optimizer", version_tag=f"job-{job_id}")
    snapshot = repository.create_snapshot(job["project_id"], f"最佳化結果 #{job_id}", "optimizer", repository.get_project_ui_state(job["project_id"]), job_id)
    repository.update_optimization_job(job_id, result_snapshot_id=snapshot["id"])
    return ok({"snapshot": snapshot})


@app.get("/api/settings")
def get_settings():
    settings = repository.get_settings()
    settings["openai_api_key"] = ""
    return ok(settings)


@app.post("/api/settings")
def save_settings(request_body: SettingRequest):
    settings = repository.save_settings(request_body.model_dump())
    settings["openai_api_key"] = ""
    return ok(settings)


@app.post("/api/seed")
def reseed():
    repository.bootstrap_defaults()
    return ok({"message": "已確認預設資料存在。"})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(Path(STATIC_DIR) / "index.html")
