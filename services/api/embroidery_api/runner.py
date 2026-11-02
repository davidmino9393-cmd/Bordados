"""Bounded background execution of the standalone worker for one API process."""
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import os
from pathlib import Path
import threading

from embroidery_contracts import IssueCode, JobResponse, JobStatus, validate_transition
from embroidery_contracts.issues import Severity
from embroidery_contracts.jobs import StageRecord
from api_adapter import make_issue, result_documents
from process_runner import WorkerFailure, run_logged

from .errors import ApiProblem


LOGGER = logging.getLogger(__name__)
SKIPPED_ANALYSIS = "Prepared SVG: analysis omitted"
SKIPPED_VECTORIZATION = "Prepared SVG: vectorization omitted"
FINAL_STATES = frozenset({JobStatus.NEEDS_REVIEW, JobStatus.READY_FOR_SEWOUT, JobStatus.FAILED, JobStatus.CANCELLED})
FAILURE_DESCRIPTIONS = {
    IssueCode.INPUT_UNREADABLE: "La entrada no pudo decodificarse.",
    IssueCode.WORKER_TIMEOUT: "El trabajo superó el plazo configurado.",
    IssueCode.WORKER_EXPORT_FAILED: "La exportación del trabajo falló.",
    IssueCode.JOB_CANCELLED: "El trabajo fue cancelado.",
}


def initial_stages():
    return (
        StageRecord(stage="analyzing", outcome="skipped", reason=SKIPPED_ANALYSIS),
        StageRecord(stage="vectorizing", outcome="skipped", reason=SKIPPED_VECTORIZATION),
        StageRecord(stage="digitizing", outcome="pending"),
        StageRecord(stage="validating", outcome="pending"),
    )


class JobRunner:
    def __init__(self, config, store):
        self.config = config
        self.store = store
        self._executor = ThreadPoolExecutor(max_workers=config.max_workers, thread_name_prefix="embroidery-worker")
        self._lock = threading.RLock()
        self._reserved = 0
        self._active = 0
        self._events = {}
        self._closed = False

    def reserve(self):
        with self._lock:
            if self._closed:
                raise ApiProblem("SERVICE_UNAVAILABLE", "El servicio se está deteniendo.")
            if self._reserved + self._active >= self.config.max_queued_jobs:
                raise ApiProblem("SERVICE_UNAVAILABLE", "La cola de trabajos está llena.")
            self._reserved += 1

    def release(self):
        with self._lock:
            if self._reserved:
                self._reserved -= 1

    def start_reserved(self, job_id):
        event = threading.Event()
        with self._lock:
            if self._reserved <= 0:
                raise RuntimeError("No reserved worker slot")
            self._reserved -= 1
            self._active += 1
            self._events[job_id] = event
            if self._closed:
                self._active -= 1
                self._events.pop(job_id, None)
                raise ApiProblem("SERVICE_UNAVAILABLE", "El servicio se está deteniendo.")
        try:
            self._executor.submit(self._run, job_id, event)
        except RuntimeError:
            with self._lock:
                self._active -= 1
                self._events.pop(job_id, None)
            raise

    def cancel(self, job_id):
        with self._lock:
            event = self._events.get(job_id)
        if event is not None:
            event.set()

    def shutdown(self):
        with self._lock:
            self._closed = True
            events = tuple(self._events.values())
        for event in events:
            event.set()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(self, job_id, event):
        try:
            self._execute(job_id, event)
        except BaseException:
            LOGGER.exception("Unexpected failure while running job %s", job_id)
            try:
                self._fail_unexpected(job_id)
            except Exception:
                LOGGER.exception("Could not persist failure for job %s", job_id)
        finally:
            with self._lock:
                self._active = max(0, self._active - 1)
                self._events.pop(job_id, None)

    def _execute(self, job_id, event):
        resource = self.store.get("job", job_id)
        previous = JobResponse.model_validate(resource["body"])
        private = dict(resource["private"])
        if previous.status in FINAL_STATES:
            return
        if previous.cancellation_requested or event.is_set():
            self._save_transition(
                previous, JobStatus.CANCELLED, private,
                {"digitizing": ("cancelled", None, None)},
                {"cancellation_requested": True},
            )
            return
        previous = self._save_transition(
            previous, JobStatus.DIGITIZING, private,
            {"digitizing": ("running", None, None)},
        )
        job_dir = Path(private["job_dir"])
        run_dir = Path(private["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(Path(private["asset_path"]), job_dir)
        environment = {}
        if self.config.worker_python_paths:
            environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in self.config.worker_python_paths)
        try:
            _, record = run_logged(
                command, run_dir, "worker", self.config.timeout_s + 30, event, environment
            )
        except WorkerFailure as exc:
            self._handle_worker_failure(job_id, previous, private, exc, job_dir)
            return
        try:
            result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._save_failed(previous, private, "WORKER_EXPORT_FAILED", "missing_worker_result")
            return
        if not result.get("ok"):
            issue = result.get("issue") or {}
            self._save_failed(previous, private, issue.get("code"), issue.get("reason"))
            return
        duration_ms = int(record.get("duration_ms") or 0)
        try:
            report, manifest, artifact_paths = result_documents(
                previous.model_dump(mode="json"), result, job_dir, duration_ms,
                self.config.dimension_tolerance_mm,
            )
        except Exception:
            LOGGER.exception("Could not map worker result for job %s", job_id)
            self._save_failed(previous, private, "WORKER_EXPORT_FAILED", "result_mapping_failed")
            return
        private["artifact_paths"] = artifact_paths
        issues = tuple(report.issues)
        blocking = any(issue.severity == Severity.BLOCKING_ERROR for issue in issues)
        review = any(
            issue.severity == Severity.REVIEW_REQUIRED and (issue.object_ids or issue.region_ids)
            for issue in issues
        )
        if blocking:
            self._save_transition(
                previous, JobStatus.FAILED, private,
                {"digitizing": ("failed", duration_ms, None), "validating": ("pending", None, None)},
                {"issues": [issue.model_dump(mode="json") for issue in issues]},
            )
            return
        if not review and not report.digital_checks_passed:
            self._save_failed(previous, private, "WORKER_EXPORT_FAILED", "review_localization_unavailable")
            return
        extra = {
            "issues": [issue.model_dump(mode="json") for issue in issues],
            "validation_report": report.model_dump(mode="json"),
            "artifact_manifest": manifest.model_dump(mode="json"),
        }
        if report.digital_checks_passed and not review:
            validating = self._save_transition(
                previous, JobStatus.VALIDATING, private,
                {"digitizing": ("completed", duration_ms, None), "validating": ("running", None, None)},
            )
            self._save_transition(
                validating, JobStatus.READY_FOR_SEWOUT, private,
                {"validating": ("completed", duration_ms, None)}, extra,
            )
            return
        self._save_transition(
            previous, JobStatus.NEEDS_REVIEW, private,
            {"digitizing": ("completed", duration_ms, None), "validating": ("completed", duration_ms, None)},
            extra,
        )

    def _command(self, asset_path, job_dir):
        command = [
            str(self.config.python_executable), str(self.config.worker_script),
            "--svg", str(asset_path), "--job-dir", str(job_dir),
            "--inkstitch", str(self.config.inkstitch_executable),
            "--engine-version", self.config.engine_version,
            "--timeout", str(self.config.timeout_s),
        ]
        if self.config.inkscape_executable is not None:
            command += ["--inkscape", str(self.config.inkscape_executable)]
        return command

    def _handle_worker_failure(self, job_id, previous, private, exc, job_dir):
        code = exc.issue.get("code")
        reason = exc.issue.get("reason")
        result_file = job_dir / "result.json"
        if result_file.exists():
            try:
                reported = json.loads(result_file.read_text(encoding="utf-8")).get("issue") or {}
                code = reported.get("code") or code
                reason = reported.get("reason") or reason
            except (OSError, ValueError):
                pass
        duration_ms = exc.issue.get("evidence", {}).get("duration_ms")
        duration = int(duration_ms) if isinstance(duration_ms, (int, float)) else None
        if code == "JOB_CANCELLED":
            self._save_transition(
                previous, JobStatus.CANCELLED, private,
                {"digitizing": ("cancelled", duration, None)},
                {"cancellation_requested": True},
            )
            return
        self._save_failed(previous, private, code, reason, duration)

    def _save_failed(self, previous, private, code, reason, duration_ms=None):
        issue = self._issue_for(code, reason)
        self._save_transition(
            previous, JobStatus.FAILED, private,
            {"digitizing": ("failed", duration_ms, None), "validating": ("pending", None, None)},
            {"issues": [issue.model_dump(mode="json")]},
        )

    def _issue_for(self, code, reason):
        try:
            issue_code = IssueCode(code)
        except (TypeError, ValueError):
            issue_code = IssueCode.WORKER_EXPORT_FAILED
        return make_issue(
            issue_code, FAILURE_DESCRIPTIONS.get(issue_code, "El worker no pudo completar el trabajo."),
            {"reason": reason or "worker_failure"},
        )

    def _save_transition(self, previous, status, private, updates, extra=None):
        data = previous.model_dump(mode="json")
        for name in ("failure", "review", "diagnostics", "sewout_status"):
            data.pop(name, None)
        data["status"] = status.value
        data["stages"] = [record.model_dump(mode="json") for record in self._stages(previous, updates)]
        if extra:
            data.update(extra)
        following = JobResponse.model_validate(data)
        validate_transition(previous, following)
        self.store.update("job", previous.job_id, following.model_dump(mode="json"), private)
        return following

    @staticmethod
    def _stages(previous, updates):
        records = []
        for record in previous.stages:
            if record.stage not in updates:
                records.append(record)
                continue
            outcome, duration, reason = updates[record.stage]
            records.append(StageRecord(
                stage=record.stage, outcome=outcome, reason=reason,
                measured_duration_ms=duration,
            ))
        return tuple(records)

    def _fail_unexpected(self, job_id):
        resource = self.store.get("job", job_id)
        previous = JobResponse.model_validate(resource["body"])
        if previous.status in FINAL_STATES:
            return
        self._save_failed(previous, dict(resource["private"]), "WORKER_EXPORT_FAILED", "adapter_failure")
