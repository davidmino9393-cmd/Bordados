"""Bounded background execution of the standalone worker for one API process."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
import os
from pathlib import Path
import threading

from embroidery_contracts import AnalysisSpec, ArtifactManifest, IssueCode, JobResponse, JobStatus, SourceAsset, validate_transition
from embroidery_contracts.issues import Severity
from embroidery_contracts.base import Provenance
from embroidery_contracts.results import Artifact
from embroidery_contracts.jobs import StageRecord
from api_adapter import make_issue, result_documents
from process_runner import WorkerFailure, run_logged
from vectorize import VectorizeFailure, stitchable, vectorize
from vectorize.inkstitch import REFERENCE_PULL_COMPENSATION_MM, reference_issues, to_reference_inkstitch_svg

from .analysis import ProviderError, normalize, region_incoherent_issue
from .errors import ApiProblem


LOGGER = logging.getLogger(__name__)
SKIPPED_ANALYSIS = "Prepared SVG: analysis omitted"
SKIPPED_VECTORIZATION = "Prepared SVG: vectorization omitted"
SKIPPED_ANALYSIS_BY_CHOICE = "Sin análisis de IA: la persona eligió continuar sin él"
FINAL_STATES = frozenset({JobStatus.NEEDS_REVIEW, JobStatus.READY_FOR_SEWOUT, JobStatus.FAILED, JobStatus.CANCELLED})
FAILURE_DESCRIPTIONS = {
    IssueCode.INPUT_UNREADABLE: "La entrada no pudo decodificarse.",
    IssueCode.WORKER_TIMEOUT: "El trabajo superó el plazo configurado.",
    IssueCode.WORKER_EXPORT_FAILED: "La exportación del trabajo falló.",
    IssueCode.JOB_CANCELLED: "El trabajo fue cancelado.",
    IssueCode.ANALYSIS_REFUSED: "El proveedor de IA rechazó analizar la imagen.",
    IssueCode.ANALYSIS_INCOMPLETE: "El proveedor de IA devolvió un análisis incompleto.",
    IssueCode.ANALYSIS_SCHEMA_INVALID: "La respuesta del proveedor de IA no tiene el formato esperado.",
    IssueCode.PROVIDER_RATE_LIMITED: "El proveedor de IA alcanzó su límite de uso.",
    IssueCode.PROVIDER_UNAVAILABLE: "El proveedor de IA no está disponible.",
    IssueCode.LOCAL_MODEL_UNAVAILABLE: "El modelo local no está disponible.",
}
VECTORIZATION_REVIEW_UNLOCALIZED = "vectorization_review_unlocalized"
DIGITIZING_BLOCKED = "Bloqueado hasta que H3 valide técnica y parámetros físicos"
MAX_COLOR_LIMIT = 256  # el tope de `JobSettings.color_limit` en el contrato
DEFAULT_JEF_STEM = "bordado"  # si el original no tiene nombre; el JEF descargado se llama como la imagen de origen
NOTHING_STITCHABLE = "No queda geometría que se pueda bordar"
REFERENCE_SVG_FILENAME = "reference-inkstitch.svg"
DIGITIZING_DIRECTORY = "digitizing"  # el worker exige una carpeta de trabajo nueva: la de E1 ya tiene archivos
VECTORIZATION_METHOD = "e1_raster_mask_vectorization"
VECTORIZATION_FILES = {"document": "vectorized-document.json", "svg": "vectorized-editable.svg", "evidence": "vectorized-evidence.json"}
STAGE_ORDER = ("analyzing", "vectorizing", "digitizing", "validating")


def initial_stages():
    return (
        StageRecord(stage="analyzing", outcome="skipped", reason=SKIPPED_ANALYSIS),
        StageRecord(stage="vectorizing", outcome="skipped", reason=SKIPPED_VECTORIZATION),
        StageRecord(stage="digitizing", outcome="pending"),
        StageRecord(stage="validating", outcome="pending"),
    )


def raster_stages():
    return tuple(StageRecord(stage=stage, outcome="pending") for stage in STAGE_ORDER)


def unanalyzed_raster_stages():
    """Imagen enviada con `ai_provider: none`: la persona eligió no analizar; la vectorización parte de los píxeles."""
    return (
        StageRecord(stage="analyzing", outcome="skipped", reason=SKIPPED_ANALYSIS_BY_CHOICE),
        *(StageRecord(stage=stage, outcome="pending") for stage in STAGE_ORDER[1:]),
    )


def continuation_stages(parent_job_id):
    """Job de imagen que continúa tras aprobar el análisis de `parent_job_id`: `analyzing` omitido con motivo."""
    return (
        StageRecord(stage="analyzing", outcome="skipped", reason=f"análisis aprobado en {parent_job_id}"),
        *(StageRecord(stage=stage, outcome="pending") for stage in STAGE_ORDER[1:]),
    )


class JobSuperseded(Exception):
    """Otra escritura ya dejó el job en su estado final (una cancelación aceptada): el runner no sigue."""


class JobRunner:
    def __init__(self, config, store, providers=None):
        self.config = config
        self.store = store
        self.providers = dict(providers or {})
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
        except JobSuperseded as superseded:
            LOGGER.info("Job %s ya quedó en %s por otra escritura (cancelación aceptada); se descarta lo que faltaba", job_id, superseded)
        except BaseException:
            LOGGER.exception("Unexpected failure while running job %s", job_id)
            try:
                self._fail_unexpected(job_id)
            except JobSuperseded:
                pass
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
        if previous.input_kind == "raster_image":
            self._execute_raster(previous, private, event)
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
        self._run_worker(previous, private, event, Path(private["asset_path"]), Path(private["job_dir"]))

    def _worker_finished(self, job_id):
        """El subproceso ya terminó y falta mapear y guardar su resultado. No hace nada: es el punto donde las pruebas
        de cancelación concurrente detienen al runner para cancelar justo en esa ventana."""

    def _run_worker(self, previous, private, event, svg_path, job_dir, extra_issues=(), timeout_s=None, display_names=None):
        """Corre el worker real sobre un SVG de Ink/Stitch y guarda el resultado (needs_review, ready o failed)."""
        job_id = previous.job_id
        timeout_s = timeout_s or self.config.timeout_s
        run_dir = Path(private["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        command = self._command(svg_path, job_dir, timeout_s, previous.settings_snapshot.hoop.jef_hoop_code)
        environment = {}
        if self.config.worker_python_paths:
            environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in self.config.worker_python_paths)
        try:
            _, record = run_logged(
                command, run_dir, "worker", timeout_s + 30, event, environment
            )
        except WorkerFailure as exc:
            self._handle_worker_failure(job_id, previous, private, exc, job_dir)
            return
        self._worker_finished(job_id)
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
                self.config.dimension_tolerance_mm, display_names,
            )
        except Exception:
            LOGGER.exception("Could not map worker result for job %s", job_id)
            self._save_failed(previous, private, "WORKER_EXPORT_FAILED", "result_mapping_failed")
            return
        private["artifact_paths"] = artifact_paths
        issues = tuple(extra_issues) + tuple(report.issues)
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

    def _execute_raster(self, previous, private, event):
        """H2: análisis visual de una imagen. La vectorización todavía no existe (paquete E del plan)."""
        continuation = any(r.stage == "analyzing" and r.outcome == "skipped" for r in previous.stages)
        first = "vectorizing" if continuation else "analyzing"
        if previous.cancellation_requested or event.is_set():
            self._save_transition(
                previous, JobStatus.CANCELLED, private, {first: ("cancelled", None, None)},
                {"cancellation_requested": True},
            )
            return
        status = JobStatus.VECTORIZING if continuation else JobStatus.ANALYZING
        previous = self._save_transition(previous, status, private, {first: ("running", None, None)})
        if continuation:
            self._vectorize(previous, private, event)
            return
        self._analyze(previous, private, event)

    def _analyze(self, previous, private, event):
        asset = self.store.get("asset", previous.asset_id)["body"]
        provider = self.providers.get(previous.settings_snapshot.ai_provider)
        try:
            if provider is None:
                raise ProviderError(IssueCode.PROVIDER_UNAVAILABLE, "provider_not_configured")
            image = Path(private["asset_path"]).read_bytes()
            width, height = asset["original_width_px"], asset["original_height_px"]
            result = provider.analyze(image, asset["media_type"], width, height, event)
            normalized = normalize(result, provider.provider_id, previous.job_id, previous.asset_id, width, height)
        except ProviderError as exc:
            self._save_failed(previous, private, exc.code, exc.detail, stage="analyzing")
            return
        raw_path = Path(private["job_dir"]) / "provider-raw.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(result.raw, ensure_ascii=False), encoding="utf-8")
        private["analysis"] = normalized.spec.model_dump(mode="json")
        private["provider_raw_path"] = str(raw_path)
        latest = JobResponse.model_validate(self.store.get("job", previous.job_id)["body"])
        done = {"analyzing": ("completed", result.duration_ms, None)}
        if latest.cancellation_requested or event.is_set():
            self._save_transition(
                previous, JobStatus.CANCELLED, private, {"analyzing": ("cancelled", result.duration_ms, None)},
                {"cancellation_requested": True},
            )
            return
        issues = [region_incoherent_issue(normalized.spec, rid) for rid in normalized.incoherent_region_ids]
        if issues:
            self._save_transition(
                previous, JobStatus.NEEDS_REVIEW, private, done,
                {"issues": [issue.model_dump(mode="json") for issue in issues]},
            )
            return
        # Sin dudas el análisis no pausa: sigue a la vectorización.
        previous = self._save_transition(
            previous, JobStatus.VECTORIZING, private, {**done, "vectorizing": ("running", None, None)},
        )
        self._vectorize(previous, private, event)

    def _analysis_for(self, private, asset):
        """Análisis de este job o, en una continuación, el del job que lo aprobó. Solo anota; no sustituye geometría.

        Las regiones cuya caja sale del original ya se avisaron como ANALYSIS_REGION_INCOHERENT y la persona las aprobó o
        marcó; E1 las rechaza otra vez, así que no se le pasan (siguen en el análisis guardado y en `GET /analysis`).
        """
        spec = private.get("analysis")
        if spec is None and private.get("analysis_from"):
            spec = self.store.get("job", private["analysis_from"])["private"].get("analysis")
        if spec is None:
            return None
        analysis = AnalysisSpec.model_validate(spec)
        inside = tuple(
            region for region in analysis.regions
            if region.bounds_px.x_px + region.bounds_px.width_px <= asset.original_width_px
            and region.bounds_px.y_px + region.bounds_px.height_px <= asset.original_height_px
        )
        return analysis.model_copy(update={"regions": inside})

    def _vectorize(self, previous, private, event):
        """H2-E1: geometría desde los píxeles. Sin H3 no hay puntadas validadas: el job termina en needs_review."""
        stitching = None
        try:
            asset = SourceAsset.model_validate(self.store.get("asset", previous.asset_id)["body"])
            image, analysis = Path(private["asset_path"]).read_bytes(), self._analysis_for(private, asset)
            if self.config.raster_digitizing:
                result, stitching = self._vectorize_for_stitching(image, asset, analysis, previous, event)
            else:
                result = vectorize(
                    image, asset.media_type, asset, analysis, previous.settings_snapshot,
                    job_id=previous.job_id, revision_id=previous.revision_id, cancel=event,
                )
        except VectorizeFailure as failure:
            self._vectorize_failure(previous, private, failure.issue)
            return
        job_dir = Path(private["job_dir"])
        job_dir.mkdir(parents=True, exist_ok=True)
        files = {name: job_dir / filename for name, filename in VECTORIZATION_FILES.items()}
        files["document"].write_text(result.document.model_dump_json(indent=2), encoding="utf-8")
        files["svg"].write_bytes(result.editable_svg)
        evidence = {**result.evidence, **({"stitching": stitching} if stitching else {})}
        files["evidence"].write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        private["vectorization"] = {name: str(path) for name, path in files.items()}
        manifest = self._vectorization_manifest(previous, asset, files)
        private["artifact_paths"] = {artifact.artifact_id: str(files["svg"]) for artifact in manifest.artifacts}
        issues = tuple(result.issues)
        done = {"vectorizing": ("completed", result.duration_ms, None)}
        if any(issue.severity == Severity.BLOCKING_ERROR for issue in issues):
            self._save_transition(previous, JobStatus.FAILED, private, {"vectorizing": ("failed", result.duration_ms, None)},
                                  {"issues": [issue.model_dump(mode="json") for issue in issues]})
            return
        if self.config.raster_digitizing:
            self._digitize_vectorized(previous, private, event, result, done, asset)
            return
        if not any(issue.severity == Severity.REVIEW_REQUIRED and (issue.object_ids or issue.region_ids) for issue in issues):
            self._save_failed(previous, private, IssueCode.WORKER_EXPORT_FAILED, VECTORIZATION_REVIEW_UNLOCALIZED, stage="vectorizing")
            return
        self._save_transition(
            previous, JobStatus.NEEDS_REVIEW, private,
            {**done, "digitizing": ("skipped", None, DIGITIZING_BLOCKED), "validating": ("skipped", None, DIGITIZING_BLOCKED)},
            {"issues": [issue.model_dump(mode="json") for issue in issues],
             "artifact_manifest": manifest.model_dump(mode="json")},
        )

    def _vectorize_for_stitching(self, image, asset, analysis, previous, event):
        """E1 para un bordado: el destino es el tamaño del bordado y el límite de colores es de hilos.

        La compensación de tracción engorda cada relleno `REFERENCE_PULL_COMPENSATION_MM` por lado, así que se vectoriza
        dentro de un destino más chico para que lo bordado entre en el pedido. Una capa casi blanca (el resplandor del
        fondo) no gasta un hilo: si E1 la produjo, se repite con una capa más.
        """
        settings = previous.settings_snapshot
        inset = 2 * REFERENCE_PULL_COMPENSATION_MM
        target = settings.target
        if min(target.width_mm, target.height_mm) > 2 * inset:
            target = target.model_copy(update={"width_mm": target.width_mm - inset, "height_mm": target.height_mm - inset})

        def run(limit):
            adjusted = settings.model_copy(update={"target": target, "color_limit": limit})
            return vectorize(image, asset.media_type, asset, analysis, adjusted,
                             job_id=previous.job_id, revision_id=previous.revision_id, cancel=event)

        result, limit = run(settings.color_limit), settings.color_limit
        background = sum(1 for item in stitchable.plan(result.document) if item.omitted == stitchable.OMITTED_NEAR_WHITE)
        if background and settings.color_limit + background <= MAX_COLOR_LIMIT:
            limit = settings.color_limit + background
            result = run(limit)
        return result, {
            "target_requested_mm": [settings.target.width_mm, settings.target.height_mm],
            "target_vectorized_mm": [target.width_mm, target.height_mm], "pull_compensation_inset_mm": inset,
            "colour_limit_requested": settings.color_limit, "colour_limit_used": limit,
        }

    def _vectorization_manifest(self, previous, asset, files):
        """Manifiesto sin JEF: solo el SVG editable generado por E1. Sin relectura no hay `reread_metrics`."""
        svg = files["svg"].read_bytes()
        settings = json.dumps(previous.settings_snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        artifact = Artifact(
            artifact_id=f"{previous.job_id}_editable_svg", job_id=previous.job_id, kind="editable_svg", filename="editable.svg",
            media_type="image/svg+xml", sha256=hashlib.sha256(svg).hexdigest(), byte_size=len(svg), derived_from="document",
        )
        return ArtifactManifest(
            manifest_id=f"{previous.job_id}_manifest", job_id=previous.job_id, revision_id=previous.revision_id,
            provenance=Provenance(simulated=False, method=VECTORIZATION_METHOD, engine_version=self.config.engine_version),
            input_sha256=asset.sha256, settings_sha256=hashlib.sha256(settings.encode()).hexdigest(),
            geometry_sha256=hashlib.sha256(files["document"].read_bytes()).hexdigest(),
            artifacts=(artifact,), reread_metrics=None,
        )

    def _vectorize_failure(self, previous, private, issue):
        if issue.code == IssueCode.JOB_CANCELLED:
            self._save_transition(previous, JobStatus.CANCELLED, private, {"vectorizing": ("cancelled", None, None)},
                                  {"cancellation_requested": True})
        elif issue.severity == Severity.BLOCKING_ERROR:
            self._save_transition(
                previous, JobStatus.FAILED, private,
                {"vectorizing": ("failed", None, None), **{name: ("pending", None, None) for name in STAGE_ORDER[2:]}},
                {"issues": [issue.model_dump(mode="json")]},
            )
        elif issue.severity == Severity.REVIEW_REQUIRED and (issue.object_ids or issue.region_ids):
            self._save_transition(previous, JobStatus.NEEDS_REVIEW, private, {"vectorizing": ("completed", None, None)},
                                  {"issues": [issue.model_dump(mode="json")]})
        else:
            # Una incidencia de revisión sin objeto ni región no puede pausar el job ni declararlo fallido por sí sola:
            # falla con el código genérico y conserva el original.
            unlocalized = make_issue(
                IssueCode.WORKER_EXPORT_FAILED, FAILURE_DESCRIPTIONS[IssueCode.WORKER_EXPORT_FAILED],
                {"reason": VECTORIZATION_REVIEW_UNLOCALIZED, "original_code": issue.code.value,
                 "original_severity": issue.severity.value, "original_evidence": issue.evidence},
            )
            self._save_transition(
                previous, JobStatus.FAILED, private,
                {"vectorizing": ("failed", None, None), **{name: ("pending", None, None) for name in STAGE_ORDER[2:]}},
                {"issues": [unlocalized.model_dump(mode="json")]},
            )

    def _digitize_vectorized(self, previous, private, event, result, done, asset):
        """JEF desde la geometría de E1 con los parámetros de referencia, que no están calibrados.

        El trabajo termina en needs_review con el JEF, el SVG de Ink/Stitch y los avisos: `ready_for_sewout` exige
        comprobaciones geométricas que todavía no existen y la aprobación física es de la persona que cose.
        """
        previous = self._save_transition(previous, JobStatus.DIGITIZING, private, {**done, "digitizing": ("running", None, None)})
        try:
            svg = to_reference_inkstitch_svg(result)
        except VectorizeFailure as failure:
            self._save_transition(
                previous, JobStatus.NEEDS_REVIEW, private,
                {"digitizing": ("skipped", None, NOTHING_STITCHABLE), "validating": ("skipped", None, NOTHING_STITCHABLE)},
                {"issues": [failure.issue.model_dump(mode="json")]},
            )
            return
        job_dir = Path(private["job_dir"])
        svg_path = job_dir / REFERENCE_SVG_FILENAME
        svg_path.write_bytes(svg)
        stem = Path(asset.original_filename).stem or DEFAULT_JEF_STEM
        self._run_worker(previous, private, event, svg_path, job_dir / DIGITIZING_DIRECTORY, reference_issues(result),
                         self.config.digitizing_timeout_s, {"jef": f"{stem}.jef"})

    def _command(self, asset_path, job_dir, timeout_s, hoop_code):
        command = [
            str(self.config.python_executable), str(self.config.worker_script),
            "--svg", str(asset_path), "--job-dir", str(job_dir),
            "--inkstitch", str(self.config.inkstitch_executable),
            "--engine-version", self.config.engine_version,
            "--timeout", str(timeout_s), "--jef-hoop-code", str(hoop_code),
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

    def _save_failed(self, previous, private, code, reason, duration_ms=None, stage="digitizing"):
        issue = self._issue_for(code, reason)
        later = STAGE_ORDER[STAGE_ORDER.index(stage) + 1:]
        self._save_transition(
            previous, JobStatus.FAILED, private,
            {stage: ("failed", duration_ms, None), **{name: ("pending", None, None) for name in later}},
            {"issues": [issue.model_dump(mode="json")]},
        )

    def _issue_for(self, code, reason):
        try:
            issue_code = IssueCode(code)
        except (TypeError, ValueError):
            issue_code = IssueCode.WORKER_EXPORT_FAILED
        description = FAILURE_DESCRIPTIONS.get(issue_code, "El worker no pudo completar el trabajo.")
        return make_issue(issue_code, description, {"reason": reason or "worker_failure"})

    def _save_transition(self, previous, status, private, updates, extra=None):
        """Relee, valida y escribe en una sola transacción: una cancelación aceptada (202) no se pierde.

        `previous` solo identifica el job; el estado vigente se lee dentro de la transacción, la misma que usa
        `POST /cancel`. Si ya hay `cancellation_requested` y el resultado no es la cancelación misma, ese resultado se
        descarta (sin manifiesto, informe ni incidencias) y el job queda `cancelled`; después se lanza `JobSuperseded`
        para que quien llamó no siga con trabajo que ya no vale.
        """
        outcome = {}

        def change(stored, stored_private):
            current = JobResponse.model_validate(stored)
            if current.status in FINAL_STATES:
                raise JobSuperseded(current.status)
            cancelling = current.cancellation_requested and status != JobStatus.CANCELLED
            if cancelling:
                following = self._next(current, JobStatus.CANCELLED, self._cancelled_stage(current), {"cancellation_requested": True})
                kept_private = stored_private
            else:
                following = self._next(current, status, updates, extra)
                kept_private = private
            outcome["following"], outcome["cancelled_instead"] = following, cancelling
            return following.model_dump(mode="json"), kept_private

        self.store.mutate("job", previous.job_id, change)
        if outcome["cancelled_instead"]:
            raise JobSuperseded(JobStatus.CANCELLED)
        return outcome["following"]

    def _next(self, current, status, updates, extra):
        data = current.model_dump(mode="json")
        for name in ("failure", "review", "diagnostics", "sewout_status"):
            data.pop(name, None)
        data["status"] = status.value
        data["stages"] = [record.model_dump(mode="json") for record in self._stages(current, updates)]
        if extra:
            data.update(extra)
        following = JobResponse.model_validate(data)
        validate_transition(current, following)
        return following

    @staticmethod
    def _cancelled_stage(current):
        """La etapa que estaba corriendo (o, si nada corría, la primera pendiente) queda cancelada."""
        stage = next((r.stage for r in current.stages if r.outcome == "running"), None) \
            or next((r.stage for r in current.stages if r.outcome == "pending"), None)
        return {stage: ("cancelled", None, None)} if stage else {}

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
