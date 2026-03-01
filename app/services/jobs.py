import queue
import threading
from datetime import datetime

from .optimizer import optimize_schedule


def format_sse(event: str, data: dict) -> str:
    import json

    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class JobManager:
    def __init__(self, repository):
        self.repository = repository
        self.queues: dict[int, queue.Queue] = {}
        self.threads: dict[int, threading.Thread] = {}
        self.lock = threading.Lock()

    def start(self, job_id: int) -> None:
        thread = threading.Thread(target=self._run, args=(job_id,), daemon=True)
        with self.lock:
            self.queues[job_id] = queue.Queue()
            self.threads[job_id] = thread
        thread.start()

    def emit(self, job_id: int, event: str, data: dict) -> None:
        queue_ref = self.queues.get(job_id)
        if queue_ref:
            queue_ref.put((event, data))

    def stream(self, job_id: int):
        queue_ref = self.queues.setdefault(job_id, queue.Queue())
        while True:
            try:
                event, data = queue_ref.get(timeout=15)
            except queue.Empty:
                job = self.repository.get_optimization_job(job_id)
                if not job:
                    yield format_sse("error", {"message": "找不到任務。"})
                    return
                if job["status"] in {"SUCCEEDED", "FAILED", "CANCELED"}:
                    yield format_sse("result", job)
                    return
                yield format_sse("log", {"message": "任務仍在執行中..."})
                continue
            yield format_sse(event, data)
            if event in {"result", "error"}:
                return

    def _run(self, job_id: int) -> None:
        job = self.repository.get_optimization_job(job_id)
        if not job:
            return
        request = job["request"]
        project_id = job["project_id"]
        nurses = self.repository.list_master("nurses")
        rules = self.repository.list_active_rules()
        self.repository.update_optimization_job(job_id, status="RUNNING", progress=1, started_at=datetime.now().isoformat(timespec="seconds"))
        self.emit(job_id, "progress", {"progress": 1, "message": "開始建立求解模型。", "best_cost": None})

        def on_progress(progress: int, message: str, best_cost: int | None):
            current = self.repository.get_optimization_job(job_id) or {"logs": []}
            logs = current["logs"] + [message]
            self.repository.update_optimization_job(job_id, progress=progress, message=message, logs=logs[-200:])
            self.emit(job_id, "progress", {"progress": progress, "message": message, "best_cost": best_cost})
            self.emit(job_id, "log", {"message": message})

        def should_cancel() -> bool:
            latest = self.repository.get_optimization_job(job_id)
            return bool(latest and latest.get("cancel_requested"))

        result = optimize_schedule(
            nurses=nurses,
            rules=rules,
            period_from=request["period"]["from"],
            period_to=request["period"]["to"],
            coverage=request["coverage"],
            weight_multiplier=float(request.get("weights", {}).get("multiplier", 1.0)),
            seed=int(request.get("solver", {}).get("seed", 7)),
            progress_callback=on_progress,
            cancel_callback=should_cancel,
        )

        if result["status"] == "CANCELED":
            final = self.repository.update_optimization_job(
                job_id,
                status="CANCELED",
                progress=100,
                message="任務已取消",
                logs=result["logs"],
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.emit(job_id, "result", final)
            return

        if result["status"] == "INFEASIBLE":
            final = self.repository.update_optimization_job(
                job_id,
                status="FAILED",
                progress=100,
                message="排班不可行",
                logs=result["logs"],
                result_summary=result["summary"],
                finished_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.emit(job_id, "error", {"message": "排班不可行", "summary": result["summary"]})
            self.emit(job_id, "result", final)
            return

        final = self.repository.update_optimization_job(
            job_id,
            status="SUCCEEDED",
            progress=100,
            message="最佳化完成",
            logs=result["logs"][-200:],
            result_assignments=result["assignments"],
            result_summary=result["summary"],
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.emit(job_id, "result", final)
