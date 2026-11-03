"""Single-process HTTP adapter around the standalone Ink/Stitch worker."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import base64
import hashlib
import hmac
import io
import json
import logging
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from starlette.exceptions import HTTPException as StarletteHTTPException

from embroidery_contracts import (
    AnalysisDecision, AnalysisSpec, AuthorizedArtifactManifest, CancelRequest, ErrorCode, JobCreate, JobResponse, JobStatus,
    ProjectCreate, ProjectDetail, ProjectList, ProjectResponse,
    RevisionCreate, RevisionList, RevisionRequest, RevisionResponse, SewoutRecord,
    SewoutResponse, SourceAsset,
)
from embroidery_contracts.http import ERROR_STATUS, FieldError, ProblemResponse
from embroidery_contracts.job_views import SewoutProjection

from .analysis import configured_providers, provider_availability
from .config import ApiConfig
from .downloads import ASSET_SCOPE, DownloadSigner
from .errors import ApiProblem
from .profiles import load_profiles, validate_settings
from .runner import JobRunner, continuation_stages, initial_stages, raster_stages, unanalyzed_raster_stages
from .store import Store


LOGGER = logging.getLogger(__name__)
ASSET_PURPOSES = frozenset({"design", "sewout_photo"})
SVG = "{http://www.w3.org/2000/svg}svg"
ACTIVE_SVG = {
    "{http://www.w3.org/2000/svg}script",
    "{http://www.w3.org/2000/svg}foreignObject",
}
ARTIFACT_STATES = frozenset({JobStatus.NEEDS_REVIEW, JobStatus.READY_FOR_SEWOUT})
TERMINAL_STATES = frozenset({JobStatus.NEEDS_REVIEW, JobStatus.READY_FOR_SEWOUT, JobStatus.FAILED, JobStatus.CANCELLED})


def _now():
    return datetime.now(timezone.utc)


def _new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def _safe_filename(filename):
    name = Path(filename or "").name
    name = "".join(char for char in name if char >= " " and char not in "/\\")
    return name[:255] or "upload"


def _validate_upload(data, content_type, limits):
    if len(data) > limits.max_bytes:
        raise ApiProblem("PAYLOAD_TOO_LARGE", "El archivo supera el límite configurado.")
    if content_type not in set(limits.accepted_mime_types):
        raise ApiProblem("UNSUPPORTED_MEDIA_TYPE", "El tipo de archivo no está admitido.")
    digest = hashlib.sha256(data).hexdigest()
    if content_type == "image/svg+xml":
        upper = data.upper()
        if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
            raise ApiProblem("INVALID_REQUEST", "El SVG no admite DTD ni entidades.")
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            raise ApiProblem("INVALID_REQUEST", "El SVG no es XML válido.") from None
        if root.tag != SVG:
            raise ApiProblem("INVALID_REQUEST", "El archivo no tiene una raíz SVG.")
        if any(element.tag in ACTIVE_SVG for element in root.iter()):
            raise ApiProblem("INVALID_REQUEST", "El SVG contiene contenido activo no admitido.")
        return digest, None, None, ".svg"
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            image_format = image.format
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ApiProblem("INVALID_REQUEST", "La imagen no pudo decodificarse.") from None
    expected = {"image/png": "PNG", "image/jpeg": "JPEG"}[content_type]
    if image_format != expected:
        raise ApiProblem("INVALID_REQUEST", "El contenido de la imagen no coincide con el tipo declarado.")
    if width <= 0 or height <= 0 or width * height > limits.max_decoded_pixels:
        raise ApiProblem("PAYLOAD_TOO_LARGE", "La imagen supera el límite de píxeles configurado.")
    return digest, width, height, ".png" if content_type == "image/png" else ".jpg"


def _encode_cursor(sequence):
    return base64.urlsafe_b64encode(str(sequence).encode()).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor):
    if cursor is None:
        return None
    try:
        value = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode("ascii")
        return int(value)
    except (ValueError, TypeError, UnicodeError):
        raise ApiProblem("INVALID_REQUEST", "El cursor de paginación no es válido.") from None


def _page(rows, cursor, limit):
    after = _decode_cursor(cursor)
    if after is not None:
        rows = [row for row in rows if row["sequence"] > after]
    page = rows[:limit]
    next_cursor = _encode_cursor(page[-1]["sequence"]) if len(rows) > limit else None
    return page, next_cursor


def _request_id(request):
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _problem(request, code, detail, errors=(), challenge=None):
    code = ErrorCode(code)
    status = ERROR_STATUS[code]
    path = request.url.path
    request_id = _request_id(request)
    headers = {"Cache-Control": "no-store"}
    if challenge:
        headers["WWW-Authenticate"] = challenge
    if not path.startswith("/api/v1/"):
        return JSONResponse(
            {"code": code.value, "detail": detail, "request_id": request_id},
            status_code=status, headers=headers,
        )
    problem = ProblemResponse(
        type="urn:embroidery:problem:" + code.value.lower().replace("_", "-"),
        title=code.value.replace("_", " ").title(),
        status=status,
        detail=detail or code.value.replace("_", " ").title(),
        instance=path,
        code=code,
        request_id=request_id,
        errors=tuple(errors),
    )
    return JSONResponse(
        problem.model_dump(mode="json"), status_code=status,
        media_type="application/problem+json", headers=headers,
    )


def _download_error(request, code, detail):
    code = ErrorCode(code)
    return JSONResponse(
        {"code": code.value, "detail": detail, "request_id": _request_id(request)},
        status_code=ERROR_STATUS[code], headers={"Cache-Control": "no-store"},
    )


def _original_response(request, store, data_root, grant):
    """Sirve el original subido; el nombre de archivo fuerza `attachment`, así un SVG no se abre como documento."""
    try:
        asset = store.get("asset", grant["artifact_id"], grant["owner"])
    except ApiProblem:
        return _download_error(request, "NOT_FOUND", "El original no está disponible.")
    private = asset["private"]
    if private.get("sha256") != grant["sha256"]:
        return _download_error(request, "NOT_FOUND", "El original no está disponible.")
    assets_dir = (data_root / "assets").resolve()
    try:
        path = Path(private["path"]).resolve(strict=True)
    except OSError:
        return _download_error(request, "NOT_FOUND", "El original no está disponible.")
    if not path.is_relative_to(assets_dir):
        return _download_error(request, "FORBIDDEN", "La autorización de descarga no es válida.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != grant["sha256"]:
        return _download_error(request, "FORBIDDEN", "El original no coincide con su autorización.")
    return FileResponse(path, media_type=private["media_type"], filename=asset["body"]["original_filename"],
                        headers={"X-Content-Type-Options": "nosniff"})


def create_app(config: ApiConfig, analysis_providers=None):
    providers = dict(analysis_providers) if analysis_providers is not None else configured_providers(config)
    # La disponibilidad de proveedores sale de lo realmente configurado, no del archivo de perfiles.
    catalog = load_profiles(config.profiles_path).model_copy(update={"providers": provider_availability(providers)})
    data_root = Path(config.data_root)
    for name in ("assets", "jobs", "runs"):
        (data_root / name).mkdir(parents=True, exist_ok=True)
    store = Store(data_root)
    signer = DownloadSigner(config.signing_key, config.public_base_url)
    runner = JobRunner(config, store, providers)
    owner = config.principal_id

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            runner.shutdown()
            store.close()

    app = FastAPI(
        title="Embroidery H0-04 API", version="0.1",
        docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan,
    )

    def require_auth(request: Request):
        authorization = request.headers.get("authorization", "")
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and config.service_token:
            if hmac.compare_digest(value, config.service_token):
                return owner
        if scheme.lower() == "basic" and config.basic_username and config.basic_password:
            try:
                decoded = base64.b64decode(value, validate=True).decode("utf-8")
            except (ValueError, UnicodeError):
                decoded = ""
            username, separator, password = decoded.partition(":")
            if separator and hmac.compare_digest(username, config.basic_username) and hmac.compare_digest(password, config.basic_password):
                return owner
        raise ApiProblem("UNAUTHENTICATED", "Se requiere autenticación para este servicio.")

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(require_auth)])

    def owned(kind, identifier, project_id=None):
        resource = store.get(kind, identifier, owner)
        if project_id is not None and resource["body"].get("project_id") != project_id:
            raise ApiProblem("NOT_FOUND", "El recurso no está disponible para este usuario.")
        return resource

    def current_sewout(project_id, revision_id):
        rows = [
            row for row in store.rows("sewout", owner, project_id)
            if row["body"].get("revision_id") == revision_id
        ]
        if not rows:
            return None
        body = rows[-1]["body"]
        return SewoutProjection(
            sewout_id=body["sewout_id"], revision_id=body["revision_id"],
            status=body["status"], tested_at=body.get("tested_at"),
            observations=body["observations"], photo_asset_ids=tuple(body.get("photo_asset_ids", ())),
        )

    @api.post("/projects")
    def create_project(payload: ProjectCreate, idempotency_key: str = Header(alias="Idempotency-Key")):
        def action():
            project_id = _new_id("project")
            body = ProjectResponse(project_id=project_id, name=payload.name, created_at=_now())
            store.create("project", project_id, owner, None, body.model_dump(mode="json"))
            return 201, body.model_dump(mode="json")

        status, body = store.idempotent(
            f"createProject:{owner}", idempotency_key, payload.model_dump(mode="json"), action
        )
        return JSONResponse(body, status_code=status)

    def with_original_download(body):
        """El original se descarga con un enlace firmado de 300 s; nunca se guarda en la fila (vencería)."""
        asset = SourceAsset.model_validate({**body, "original_download": None})
        return asset.model_copy(update={"original_download": signer.issue_asset(owner, asset)})

    @api.get("/projects")
    def list_projects(
        cursor: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        rows, next_cursor = _page(store.rows("project", owner), cursor, limit)
        result = ProjectList(
            items=tuple(ProjectResponse.model_validate(row["body"]) for row in rows),
            next_cursor=next_cursor,
        )
        return JSONResponse(result.model_dump(mode="json"))

    @api.get("/projects/{id}")
    def get_project(
        id: str,
        assets_cursor: str | None = Query(default=None),
        jobs_cursor: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        project = owned("project", id)
        asset_rows, assets_next = _page(store.rows("asset", owner, id), assets_cursor, limit)
        job_rows, jobs_next = _page(store.rows("job", owner, id), jobs_cursor, limit)
        result = ProjectDetail(
            project=ProjectResponse.model_validate(project["body"]),
            assets=tuple(with_original_download(row["body"]) for row in asset_rows),
            jobs=tuple(JobResponse.model_validate(row["body"]) for row in job_rows),
            assets_next_cursor=assets_next, jobs_next_cursor=jobs_next,
        )
        return JSONResponse(result.model_dump(mode="json"))

    @api.post("/projects/{id}/assets")
    async def upload_asset(
        id: str,
        file: UploadFile = File(...),
        purpose: str = Form("design"),
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        owned("project", id)
        if purpose not in ASSET_PURPOSES:
            raise ApiProblem("INVALID_REQUEST", "purpose debe ser design o sewout_photo.")
        data = await file.read()
        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        digest, width, height, suffix = _validate_upload(data, content_type, catalog.upload_limits)
        filename = _safe_filename(file.filename)
        if purpose == "sewout_photo" and content_type == "image/svg+xml":
            raise ApiProblem("INVALID_REQUEST", "Una foto de la muestra debe ser PNG o JPEG.")
        logical = {"project_id": id, "sha256": digest, "filename": filename, "content_type": content_type, "purpose": purpose}

        def action():
            asset_id = _new_id("asset")
            path = data_root / "assets" / f"{asset_id}{suffix}"
            path.write_bytes(data)
            body = SourceAsset(
                asset_id=asset_id, project_id=id, sha256=digest, media_type=content_type,
                original_filename=filename, original_width_px=width, original_height_px=height, purpose=purpose,
            )
            store.create(
                "asset", asset_id, owner, id, body.model_dump(mode="json"),
                {"path": str(path), "sha256": digest, "media_type": content_type},
            )
            return 201, body.model_dump(mode="json")

        status, body = store.idempotent(f"uploadAsset:{owner}:{id}", idempotency_key, logical, action)
        return JSONResponse(with_original_download(body).model_dump(mode="json"), status_code=status)

    @api.post("/projects/{id}/revisions")
    def create_revision(
        id: str,
        payload: RevisionRequest,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        owned("project", id)
        request = payload.root
        if not isinstance(request, RevisionCreate):
            raise ApiProblem("INVALID_REQUEST", "H0-04 solo admite revisiones iniciales.")
        validate_settings(request.settings, catalog)

        def action():
            if any(row["body"].get("kind") == "initial" for row in store.rows("revision", owner, id)):
                raise ApiProblem("REVISION_CONFLICT", "El proyecto ya tiene una revisión inicial.")
            revision_id = _new_id("rev")
            body = RevisionResponse(
                revision_id=revision_id, project_id=id, base_revision_id=None,
                reason=request.reason, created_at=_now(), kind="initial",
            )
            private = {
                "settings": request.settings.model_dump(mode="json"),
                "document": request.document.model_dump(mode="json") if request.document else None,
            }
            store.create("revision", revision_id, owner, id, body.model_dump(mode="json"), private)
            return 201, body.model_dump(mode="json")

        status, body = store.idempotent(
            f"createRevision:{owner}:{id}", idempotency_key, payload.model_dump(mode="json"), action
        )
        return JSONResponse(body, status_code=status)

    @api.get("/projects/{id}/revisions")
    def list_revisions(
        id: str,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
    ):
        owned("project", id)
        rows, next_cursor = _page(store.rows("revision", owner, id), cursor, limit)
        result = RevisionList(
            items=tuple(RevisionResponse.model_validate(row["body"]) for row in rows),
            next_cursor=next_cursor,
        )
        return JSONResponse(result.model_dump(mode="json"))

    def enqueue_job(scope, key, logical, build):
        """Crea un job en una transacción idempotente y lo encola. `build()` devuelve (JobResponse, private)."""
        created = {}

        def action():
            runner.reserve()
            try:
                body, private = build()
                store.create("job", body.job_id, owner, body.project_id, body.model_dump(mode="json"), private)
                created["job_id"] = body.job_id
                return 202, body.model_dump(mode="json")
            except BaseException:
                runner.release()
                raise

        try:
            status, body = store.idempotent(scope, key, logical, action)
        except BaseException:
            if created:
                runner.release()
            raise
        if created:
            runner.start_reserved(created["job_id"])
        return JSONResponse(body, status_code=status)

    def new_job(project_id, revision_id, asset, settings, input_kind, stages, parent_job_id=None, extra=None):
        job_id = _new_id("job")
        body = JobResponse(
            job_id=job_id, project_id=project_id, revision_id=revision_id,
            asset_id=asset["body"]["asset_id"], input_kind=input_kind,
            settings_snapshot=settings, status=JobStatus.QUEUED, stages=stages,
            parent_job_id=parent_job_id, sewout_record=current_sewout(project_id, revision_id),
        )
        private = {
            "job_dir": str(data_root / "jobs" / job_id), "run_dir": str(data_root / "runs" / job_id),
            "asset_path": asset["private"]["path"], "artifact_paths": {}, **(extra or {}),
        }
        return body, private

    @api.post("/projects/{id}/jobs")
    def create_job(
        id: str,
        payload: JobCreate,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        owned("project", id)
        validate_settings(payload.settings, catalog)
        asset = owned("asset", payload.asset_id, id)
        if asset["body"].get("purpose", "design") != "design":
            raise ApiProblem("INVALID_REQUEST", "Una foto de muestra no puede usarse como diseño a bordar.")
        revision = owned("revision", payload.revision_id, id)
        if revision["body"].get("kind") != "initial":
            raise ApiProblem("INVALID_REQUEST", "Un trabajo nuevo parte de una revisión inicial.")
        if revision["private"].get("settings") != payload.settings.model_dump(mode="json"):
            raise ApiProblem("REVISION_CONFLICT", "La configuración no coincide con la revisión inmutable.")
        media_type = asset["body"].get("media_type")
        if payload.input_kind == "prepared_svg":
            if media_type != "image/svg+xml":
                raise ApiProblem("INVALID_REQUEST", "La entrada prepared_svg requiere un asset SVG.")
            stages = initial_stages()
        else:
            if media_type not in ("image/png", "image/jpeg"):
                raise ApiProblem("INVALID_REQUEST", "La entrada raster_image requiere un asset PNG o JPEG.")
            stages = unanalyzed_raster_stages() if payload.settings.ai_provider == "none" else raster_stages()
        return enqueue_job(
            f"createJob:{owner}:{id}", idempotency_key, payload.model_dump(mode="json"),
            lambda: new_job(id, payload.revision_id, asset, payload.settings, payload.input_kind, stages),
        )

    @api.get("/jobs/{id}/analysis")
    def get_job_analysis(id: str):
        job = owned("job", id)
        source = job if "analysis" in job["private"] else None
        if source is None and job["private"].get("analysis_from"):
            parent = owned("job", job["private"]["analysis_from"])
            source = parent if "analysis" in parent["private"] else None
        if source is None:
            raise ApiProblem("NOT_FOUND", "Este trabajo no tiene un análisis visual asociado.")
        return JSONResponse(AnalysisSpec.model_validate(source["private"]["analysis"]).model_dump(mode="json"))

    @api.post("/jobs/{id}/analysis-decision")
    def decide_analysis(
        id: str,
        payload: AnalysisDecision,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        job = owned("job", id)
        original = JobResponse.model_validate(job["body"])
        analysis = job["private"].get("analysis")
        awaiting = original.status == JobStatus.NEEDS_REVIEW and analysis is not None and any(
            issue.severity == "review_required" and issue.stage == "analysis" for issue in original.issues
        )
        if not awaiting:
            raise ApiProblem("REVISION_CONFLICT", "Este trabajo no está esperando una decisión sobre el análisis.")
        decision = payload.root
        project_id = original.project_id
        asset = owned("asset", original.asset_id, project_id)
        base = {"parent": id, "decision": payload.model_dump(mode="json")}
        if decision.action == "approve":
            known = {region["region_id"] for region in analysis["regions"]}
            if not set(decision.flagged_region_ids) <= known:
                raise ApiProblem("INVALID_REQUEST", "flagged_region_ids debe pertenecer al análisis.")

            def build():
                return new_job(
                    project_id, original.revision_id, asset, original.settings_snapshot, "raster_image",
                    continuation_stages(id), id,
                    {"analysis_from": id, "flagged_region_ids": list(decision.flagged_region_ids)},
                )
        else:
            available = {item.provider_id for item in catalog.providers if item.available}
            if decision.ai_provider not in available or decision.ai_provider == original.settings_snapshot.ai_provider:
                raise ApiProblem("INVALID_REQUEST", "El proveedor no está disponible o es el mismo que el actual.")
            settings = original.settings_snapshot.model_copy(update={"ai_provider": decision.ai_provider})

            def build():
                # ai_provider es parte de JobSettings y la revisión es inmutable: se crea una revisión nueva.
                revision_id = _new_id("rev")
                body, private = new_job(project_id, revision_id, asset, settings, "raster_image", raster_stages(), id)
                revision = RevisionResponse(
                    revision_id=revision_id, project_id=project_id, base_revision_id=original.revision_id,
                    reason="analysis_retry", created_at=_now(), kind="analysis_retry",
                    parent_job_id=id, job_id=body.job_id,
                )
                store.create(
                    "revision", revision_id, owner, project_id, revision.model_dump(mode="json"),
                    {"settings": settings.model_dump(mode="json"), "document": None},
                )
                return body, private

        return enqueue_job(f"decideAnalysis:{owner}:{id}", idempotency_key, base, build)

    @api.get("/jobs/{id}")
    def get_job(id: str):
        job = owned("job", id)
        return JSONResponse(JobResponse.model_validate(job["body"]).model_dump(mode="json"))

    @api.get("/jobs/{id}/artifacts")
    def get_job_artifacts(id: str):
        job = owned("job", id)
        body = JobResponse.model_validate(job["body"])
        # Artifacts are generated during validating and are immutable per job. They are
        # available only after needs_review/ready_for_sewout; queued, digitizing,
        # validating, failed and cancelled must return 409 even if a stale manifest exists.
        if body.status not in ARTIFACT_STATES or body.artifact_manifest is None:
            raise ApiProblem("ARTIFACTS_UNAVAILABLE", "Los artefactos todavía no están disponibles para este trabajo.")
        artifacts = []
        for artifact in body.artifact_manifest.artifacts:
            item = artifact.model_dump(mode="json")
            item.pop("download_url", None)
            item.pop("expires_at", None)
            item["download"] = signer.issue(owner, body.job_id, artifact).model_dump(mode="json")
            artifacts.append(item)
        document = body.artifact_manifest.model_dump(mode="json")
        document["artifacts"] = artifacts
        manifest = AuthorizedArtifactManifest.model_validate(document)
        return JSONResponse(manifest.model_dump(mode="json"))

    @api.post("/jobs/{id}/cancel")
    def cancel_job(
        id: str,
        payload: CancelRequest,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        job = owned("job", id)
        body = JobResponse.model_validate(job["body"])

        def action():
            if body.status in TERMINAL_STATES:
                return 202, body.model_dump(mode="json")
            data = body.model_dump(mode="json")
            data["cancellation_requested"] = True
            updated = JobResponse.model_validate(data)
            store.update("job", id, updated.model_dump(mode="json"), job["private"])
            runner.cancel(id)
            return 202, updated.model_dump(mode="json")

        status, result = store.idempotent(
            f"cancelJob:{owner}:{id}", idempotency_key, {"job_id": id}, action
        )
        return JSONResponse(result, status_code=status)

    @api.post("/projects/{id}/sewouts")
    def record_sewout(
        id: str,
        payload: SewoutRecord,
        idempotency_key: str = Header(alias="Idempotency-Key"),
    ):
        owned("project", id)
        owned("revision", payload.revision_id, id)
        if payload.fabric_profile not in {fabric.profile_id for fabric in catalog.fabrics}:
            raise ApiProblem("INVALID_REQUEST", "fabric_profile desconocido.")
        for asset_id in payload.photo_asset_ids:
            if owned("asset", asset_id, id)["body"].get("purpose", "design") != "sewout_photo":
                raise ApiProblem("INVALID_REQUEST", "photo_asset_ids solo admite fotos de muestra (purpose sewout_photo).")
        created = {}

        def action():
            sewout_id = _new_id("sewout")
            body = SewoutResponse(
                **payload.model_dump(mode="json"), sewout_id=sewout_id,
                project_id=id, recorded_at=_now(),
            )
            store.create("sewout", sewout_id, owner, id, body.model_dump(mode="json"))
            projection = SewoutProjection(
                sewout_id=sewout_id, revision_id=body.revision_id, status=body.status,
                tested_at=body.tested_at, observations=body.observations,
                photo_asset_ids=body.photo_asset_ids,
            )
            for row in store.rows("job", owner, id):
                if row["body"].get("revision_id") != body.revision_id:
                    continue
                data = dict(row["body"])
                for name in ("failure", "review", "diagnostics", "sewout_status"):
                    data.pop(name, None)
                data["sewout_record"] = projection.model_dump(mode="json")
                updated = JobResponse.model_validate(data)
                store.update("job", row["id"], updated.model_dump(mode="json"), row["private"])
            created["sewout_id"] = sewout_id
            return 201, body.model_dump(mode="json")

        status, body = store.idempotent(
            f"recordSewout:{owner}:{id}", idempotency_key, payload.model_dump(mode="json"), action
        )
        return JSONResponse(body, status_code=status)

    @api.get("/profiles")
    def get_profiles():
        # La lista de proveedores se sondea en vivo (el modelo local puede estar apagado); el resto del catálogo no cambia.
        live = catalog.model_copy(update={"providers": provider_availability(providers, live=True)})
        return JSONResponse(live.model_dump(mode="json"))

    @app.get("/downloads/{token}")
    def download(token: str, request: Request):
        try:
            grant = signer.verify(token)
        except ApiProblem as exc:
            return _download_error(request, exc.code, exc.detail)
        if grant.get("scope") == ASSET_SCOPE:
            return _original_response(request, store, data_root, grant)
        try:
            job = store.get("job", grant["job_id"], grant["owner"])
        except ApiProblem:
            return _download_error(request, "NOT_FOUND", "La autorización de descarga no está disponible.")
        body = JobResponse.model_validate(job["body"])
        artifact = next(
            (item for item in (body.artifact_manifest.artifacts if body.artifact_manifest else ())
             if item.artifact_id == grant["artifact_id"]),
            None,
        )
        if artifact is None or artifact.sha256 != grant["sha256"]:
            return _download_error(request, "NOT_FOUND", "El artefacto no está disponible.")
        path_value = job["private"].get("artifact_paths", {}).get(artifact.artifact_id)
        if not path_value:
            return _download_error(request, "NOT_FOUND", "El artefacto no está disponible.")
        job_dir = Path(job["private"]["job_dir"]).resolve()
        try:
            path = Path(path_value).resolve(strict=True)
        except OSError:
            return _download_error(request, "NOT_FOUND", "El artefacto no está disponible.")
        if not path.is_relative_to(job_dir):
            return _download_error(request, "FORBIDDEN", "La autorización de descarga no es válida.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact.sha256:
            return _download_error(request, "FORBIDDEN", "El artefacto no coincide con su autorización.")
        return FileResponse(path, media_type=artifact.media_type, filename=artifact.filename)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ApiProblem)
    async def api_problem(request: Request, exc: ApiProblem):
        challenge = None
        if exc.code == ErrorCode.UNAUTHENTICATED:
            challenge = "Bearer" if config.service_token else 'Basic realm="embroidery", charset="UTF-8"'
        return _problem(request, exc.code, exc.detail, challenge=challenge)

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, exc: RequestValidationError):
        errors = []
        malformed = False
        for error in exc.errors():
            if error.get("type") in {"json_invalid", "missing"}:
                malformed = True
            location = [str(part) for part in error.get("loc", ()) if part != "body"]
            errors.append(FieldError(field=".".join(location) or "body", message=error.get("msg") or "Valor inválido."))
        code = "MALFORMED_REQUEST" if malformed else "INVALID_REQUEST"
        return _problem(request, code, "La solicitud no cumple el contrato publicado.", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_problem(request: Request, exc: StarletteHTTPException):
        mapping = {
            400: "MALFORMED_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN",
            404: "NOT_FOUND", 413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE",
        }
        code = mapping.get(exc.status_code, "INTERNAL_ERROR" if exc.status_code >= 500 else "MALFORMED_REQUEST")
        return _problem(request, code, str(exc.detail) if exc.detail else "La solicitud no pudo completarse.")

    @app.exception_handler(Exception)
    async def unexpected_problem(request: Request, exc: Exception):
        LOGGER.exception("Unhandled API error")
        return _problem(request, "INTERNAL_ERROR", "El servicio no pudo completar la solicitud.")

    app.include_router(api)
    return app
