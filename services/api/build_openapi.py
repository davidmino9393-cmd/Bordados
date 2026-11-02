"""Generate the H0 contract specification; this module is not an HTTP server."""
from collections import defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "packages" / "contracts"
sys.path.insert(0, str(CONTRACTS))

from embroidery_contracts import (
    AnalysisSpec, ArtifactManifest, AssetUpload, CancelRequest, EmbroideryDocument,
    JobCreate, JobResponse, JobSettings, ProblemResponse, ProjectCreate, ProjectResponse,
    RevisionCreate, RevisionResponse, SewoutRecord, SewoutResponse, SourceAsset,
    StitchPlan, ValidationReport, ProfileCatalog, ProjectDetail, ProjectList,
    RevisionList, RevisionRequest, SizeVariantRevision, CorrectionRevision, AuthorizedArtifactManifest,
    AnalysisDecision, AnalysisApprove, AnalysisChangeProvider,
)
from embroidery_contracts.http import ERROR_STATUS, ErrorCode
from embroidery_contracts.issues import ISSUE_RULES

MODELS = (
    JobSettings, SourceAsset, AnalysisSpec, EmbroideryDocument, StitchPlan,
    ValidationReport, ArtifactManifest, JobCreate, JobResponse, ProjectCreate,
    ProjectResponse, RevisionCreate, RevisionResponse, SewoutRecord, SewoutResponse,
    AssetUpload, CancelRequest, ProblemResponse,
    ProfileCatalog, ProjectDetail, ProjectList, RevisionList, RevisionRequest,
    SizeVariantRevision, CorrectionRevision,
    AuthorizedArtifactManifest, AnalysisDecision, AnalysisApprove, AnalysisChangeProvider,
)
COMMON_ERRORS = (
    ErrorCode.MALFORMED_REQUEST, ErrorCode.UNAUTHENTICATED, ErrorCode.FORBIDDEN,
    ErrorCode.INVALID_REQUEST, ErrorCode.RATE_LIMITED, ErrorCode.INTERNAL_ERROR,
    ErrorCode.SERVICE_UNAVAILABLE,
)
POST_ERRORS = COMMON_ERRORS + (ErrorCode.IDEMPOTENCY_CONFLICT,)
FIXTURE_MODEL_NAMES = {model.__name__: model for model in MODELS}


def fixture(case):
    data = json.loads((CONTRACTS / "fixtures" / f"{case}.json").read_text(encoding="utf-8"))
    FIXTURE_MODEL_NAMES[data["model"]].model_validate(data["payload"])
    return data["payload"]


def component_schemas():
    schemas = {}
    for model in MODELS:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        definitions = schema.pop("$defs", {})
        for name, definition in {**definitions, model.__name__: schema}.items():
            if name in schemas and schemas[name] != definition:
                raise ValueError(f"Conflicting generated schema: {name}")
            schemas[name] = definition
    return schemas


def example(model, payload, summary="SIMULATED contract example; no worker or physical test"):
    normalized = model.model_validate(payload).model_dump(mode="json")
    return {"summary": summary, "value": normalized}


def job_example(status, cancellation_requested=False):
    payload = deepcopy(fixture("valid-result"))
    payload.update(status=status, cancellation_requested=cancellation_requested,
                   validation_report=None, artifact_manifest=None)
    for record in payload["stages"]:
        if record["stage"] in {"digitizing", "validating"}:
            record["outcome"] = "running" if record["stage"] == status else "pending"
            record.pop("measured_duration_ms", None)
    return payload


def analysis_example():
    def region(number, role, text, colors, uncertainties):
        return {"region_id": f"region_mock_{number}", "bounds_px": {"x_px": 10 * number, "y_px": 10, "width_px": 100, "height_px": 50},
                "representation": "estimated_bbox", "visual_role": role, "observed_text": text,
                "suggested_colors": colors, "uncertainties": uncertainties}
    return {"schema_version": "0.1", "analysis_id": "analysis_mock_1", "asset_id": "asset_mock_image", "provider": "openai",
            "model": "SIMULATED model", "prompt_version": "prompt-mock-0", "original_response_artifact_id": "artifact_mock_provider_raw",
            "regions": [region(1, "SIMULATED main text", "LOGO", ["#1F3A93"], []),
                        region(3, "SIMULATED thin text", "Est. 2019", ["#555555"], ["SIMULATED: text may be lost at this size"])],
            "duration_ms": 4200}


def continuation_example():
    """Job nuevo tras aprobar un análisis: misma revisión, `analyzing` omitido con motivo."""
    payload = job_example("queued")
    payload.update(job_id="job_mock_2", parent_job_id="job_mock_1", input_kind="raster_image")
    payload["settings_snapshot"]["ai_provider"] = "openai"
    for record in payload["stages"]:
        if record["stage"] == "analyzing":
            record.update(outcome="skipped", reason="análisis aprobado en job_mock_1")
        elif record["stage"] == "vectorizing":
            record.update(outcome="pending", reason=None)
    return payload


def problem_example(code, path):
    payload = {
        "schema_version": "0.1", "type": "urn:embroidery:problem:" + code.lower().replace("_", "-"),
        "title": code.replace("_", " ").title(), "status": ERROR_STATUS[code],
        "detail": "SIMULATED error example; inspect code and field diagnostics.",
        "instance": path.replace("{id}", "resource_mock_1"), "code": code,
        "request_id": "request_mock_1", "errors": [],
    }
    if code == ErrorCode.INVALID_REQUEST:
        payload["errors"] = [{"field": "body", "message": "Request violates the published schema or semantic guard."}]
    return example(ProblemResponse, payload)


def json_response(model, description, examples, media_type="application/json"):
    return {
        "description": description,
        "headers": {
            "X-Request-ID": {"schema": {"type": "string"}, "description": "Server correlation identifier"},
            "Cache-Control": {"schema": {"type": "string", "const": "no-store"}, "example": "no-store"},
        },
        "content": {media_type: {"schema": {"$ref": f"#/components/schemas/{model.__name__}"}, "examples": examples}},
    }


def error_responses(codes, path):
    grouped = defaultdict(dict)
    for code in codes:
        grouped[str(ERROR_STATUS[code])][code.value] = problem_example(code, path)
    responses = {
        status: json_response(ProblemResponse, "Controlled error; no storage paths or credentials", examples, "application/problem+json")
        for status, examples in grouped.items()
    }
    if "401" in responses:
        responses["401"]["headers"]["WWW-Authenticate"] = {
            "schema": {"type": "string"}, "description": "Challenge for the enabled authentication mechanism",
            "examples": {"basic": {"value": 'Basic realm="embroidery", charset="UTF-8"'}, "serviceBearer": {"value": "Bearer"}},
        }
    for status in ("429", "503"):
        if status in responses:
            responses[status]["headers"]["Retry-After"] = {"schema": {"type": "string"}, "description": "Optional retry delay in seconds"}
    return responses


def operation(path, method, operation_id, description, output, success_status, responses, request=None, request_value=None, errors=COMMON_ERRORS):
    body = {
        "operationId": operation_id, "summary": description, "description": description,
        "responses": {str(success_status): json_response(output, description, responses), **error_responses(errors, path)},
        "tags": ["Jobs" if "/jobs" in path else "Projects"],
    }
    parameters = []
    if "{id}" in path:
        parameters.append({"$ref": "#/components/parameters/ResourceId"})
    if method == "post":
        parameters.append({"$ref": "#/components/parameters/IdempotencyKey"})
    if parameters:
        body["parameters"] = parameters
    if request is not None:
        body["requestBody"] = request_body(request, request_value)
    return body


def request_body(model, payload):
    media_type = "multipart/form-data" if model is AssetUpload else "application/json"
    content = {"schema": {"$ref": f"#/components/schemas/{model.__name__}"}, "examples": {"simulated": example(model, payload)}}
    if model is AssetUpload:
        content["encoding"] = {"file": {"contentType": "image/png, image/jpeg, image/svg+xml"}}
    return {"required": True, "content": {media_type: content}}


def project_operations():
    project_path = "/api/v1/projects"
    assets_path = "/api/v1/projects/{id}/assets"
    project = {"schema_version": "0.1", "name": "SIMULATED embroidery project"}
    project_result = dict(project, project_id="project_mock_1", created_at="2026-11-01T10:00:00Z")
    asset = {"schema_version": "0.1", "asset_id": "asset_mock_svg", "project_id": "project_mock_1",
             "sha256": "a" * 64, "media_type": "image/svg+xml", "original_preserved": True,
             "original_filename": "mock-original.svg"}
    upload_errors = POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.PAYLOAD_TOO_LARGE, ErrorCode.UNSUPPORTED_MEDIA_TYPE)
    return {
        project_path: {"post": operation(project_path, "post", "createProject", "Create a project owned by the authenticated user", ProjectResponse, 201,
                          {"simulated": example(ProjectResponse, project_result)}, ProjectCreate, project, POST_ERRORS)},
        assets_path: {"post": operation(assets_path, "post", "uploadAsset", "Preserve an admitted image/SVG original; prepared-SVG validity is checked at generation", SourceAsset, 201,
                         {"simulated": example(SourceAsset, asset)}, AssetUpload, {"file": "<svg xmlns='http://www.w3.org/2000/svg'/>"}, upload_errors)},
    }


def job_operations():
    create_path, get_path = "/api/v1/projects/{id}/jobs", "/api/v1/jobs/{id}"
    artifact_path, cancel_path = get_path + "/artifacts", get_path + "/cancel"
    ready = fixture("valid-result")
    existing = COMMON_ERRORS + (ErrorCode.NOT_FOUND,)
    jobs = {
        create_path: {"post": operation(create_path, "post", "createJob", "Requires revision_id created previously through POST project revisions; never creates an implicit revision. Enqueue using owned asset and matching immutable settings snapshot", JobResponse, 202,
                         {"queued": example(JobResponse, job_example("queued"))}, JobCreate, fixture("generation-from-svg"), POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
        get_path: {"get": operation(get_path, "get", "getJob", "Read observed status, diagnostics and stage durations; polling is supported", JobResponse, 200,
                      {case: example(JobResponse, fixture(case)) for case in ("valid-result", "needs-review", "failure", "cancellation")}, errors=existing)},
        artifact_path: {"get": operation(artifact_path, "get", "getJobArtifacts", "Safe and idempotent for job/artifact identity: 200 requires an authorized URL for every artifact. Always reauthorize and issue fresh UTC URLs with TTL 300 seconds. JSON bytes may vary; no new job/export. Cache-Control: no-store. Requery here after expiry; 409 if unavailable", AuthorizedArtifactManifest, 200,
                           {"simulated": example(AuthorizedArtifactManifest, ready["artifact_manifest"])}, errors=existing + (ErrorCode.ARTIFACTS_UNAVAILABLE,))},
        cancel_path: {"post": operation(cancel_path, "post", "cancelJob", "Always 202 for accepted requests, including terminal jobs. Preserve observed status; cancelled only after processes stop. Never restart a terminal job", JobResponse, 202,
                         {"requested": example(JobResponse, job_example("digitizing", True)), "terminal": example(JobResponse, fixture("cancellation"))}, CancelRequest, {"schema_version": "0.1"}, POST_ERRORS + (ErrorCode.NOT_FOUND,))},
    }
    analysis_path, decision_path = get_path + "/analysis", get_path + "/analysis-decision"
    jobs[analysis_path] = {"get": operation(analysis_path, "get", "getJobAnalysis", "H2: visual analysis associated with the job (its own, or the approved one of its parent in a continuation job). 404 when the job has none: prepared SVG, still analyzing, or failed before producing it. bounds_px are always in the original image frame (top-left origin, x right, y down)", AnalysisSpec, 200,
                                {"simulated": example(AnalysisSpec, analysis_example())}, errors=existing)}
    jobs[decision_path] = {"post": operation(decision_path, "post", "decideJobAnalysis", "H2: decide an analysis in needs_review with a review_required analysis issue. approve keeps the revision and asset and skips analysis; change_provider creates an analysis_retry revision. Both return a NEW queued job whose parent_job_id is the original, which is unchanged. 409 REVISION_CONFLICT if the original is not in that state; 422 for an unavailable or identical provider or flagged_region_ids outside the analysis", JobResponse, 202,
                               {"approve": example(JobResponse, continuation_example())}, AnalysisDecision,
                               {"action": "approve", "flagged_region_ids": ["region_mock_3"]}, POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))}
    jobs[decision_path]["post"]["requestBody"]["content"]["application/json"]["examples"]["change_provider"] = example(
        AnalysisDecision, {"action": "change_provider", "ai_provider": "ollama"})
    jobs[create_path]["post"]["description"] += (
        ". One revision admits N distinct jobs: failure, retry or regeneration may create a new job on the same revision. "
        "Each job preserves its identity, input/settings snapshot and completed artifacts; previous artifacts are never overwritten. "
        "Reusing an Idempotency-Key replays that job, while a new key may create another job"
    )
    return jobs


def revision_operations():
    revisions_path = "/api/v1/projects/{id}/revisions"
    sewouts_path = "/api/v1/projects/{id}/sewouts"
    settings = fixture("generation-from-svg")["settings"]
    revision = {"schema_version": "0.1", "base_revision_id": None, "reason": "Initial revision", "settings": settings}
    result = {"schema_version": "0.1", "revision_id": "rev_mock_1", "project_id": "project_mock_1",
              "base_revision_id": None, "reason": "Initial revision", "created_at": "2026-11-01T10:01:00Z"}
    sewout = fixture("physical-sewout")
    sewout_result = dict(sewout, sewout_id="sewout_mock_1", project_id="project_mock_1", recorded_at="2026-11-01T11:01:00Z")
    operations = {
        revisions_path: {"post": operation(revisions_path, "post", "createRevision", "Initial revision returns 201 (null base only once); size_variant/correction create a distinct immutable revision and queued child job, returning 202. Parent ownership and object IDs must be checked", RevisionResponse, 201,
                            {"initial": example(RevisionResponse, result)}, RevisionRequest, revision, POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
        sewouts_path: {"post": operation(sewouts_path, "post", "recordSewout", "Record the authorized user's physical observation for an owned revision; never changes digital job status", SewoutResponse, 201,
                          {"simulated": example(SewoutResponse, sewout_result)}, SewoutRecord, sewout, POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
    }
    request_examples = operations[revisions_path]["post"]["requestBody"]["content"]["application/json"]["examples"]
    request_examples.update({
        "size_variant": example(RevisionRequest, {"kind": "size_variant", "parent_job_id": "job_mock_1", "target": {"width_mm": 130, "height_mm": 120, "fit": "contain"}}),
        "correction": example(RevisionRequest, {"kind": "correction", "parent_job_id": "job_mock_1", "corrections": [{"action": "exclude_region", "object_id": "object_mock_petals"}, {"action": "set_technique", "object_id": "object_mock_satin", "technique": "running"}]}),
    })
    operations[revisions_path]["post"]["responses"]["202"] = json_response(JobResponse, "New revision and queued child job, never overwriting the parent", {
        "size_variant": example(JobResponse, child_job_example("size_variant")),
        "correction": example(JobResponse, child_job_example("correction")),
    })
    history = {"schema_version": "0.1", "items": [result, dict(result, revision_id="rev_mock_2", base_revision_id="rev_mock_1", kind="size_variant", parent_job_id="job_mock_1", job_id="job_mock_2", reason="Size variant")], "next_cursor": None}
    operations[revisions_path]["get"] = operation(revisions_path, "get", "listProjectRevisions", "Page immutable revision history without losing parent/new-job links", RevisionList, 200, {"simulated": example(RevisionList, history)}, errors=COMMON_ERRORS + (ErrorCode.NOT_FOUND,))
    operations[revisions_path]["get"]["parameters"] += pagination_parameters()
    return operations


def child_job_example(kind):
    child = job_example("queued")
    child.update(job_id="job_mock_2", revision_id="rev_mock_2", parent_job_id="job_mock_1")
    if kind == "size_variant":
        child["settings_snapshot"]["target"] = {"width_mm": 130, "height_mm": 120, "fit": "contain"}
    return child


def pagination_parameters(cursor_names=("cursor",)):
    return [
        {"name": name, "in": "query", "required": False, "schema": {"type": "string", "minLength": 1, "maxLength": 2048}, "description": "Opaque cursor returned by the previous page"}
        for name in cursor_names
    ] + [{"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}]


def query_operations():
    project = {"schema_version": "0.1", "project_id": "project_mock_1", "name": "SIMULATED embroidery project", "created_at": "2026-11-01T10:00:00Z"}
    asset = {"schema_version": "0.1", "asset_id": "asset_mock_svg", "project_id": "project_mock_1", "sha256": "a" * 64, "media_type": "image/svg+xml", "original_filename": "mock-original.svg",
             "original_download": {"url": "https://example.invalid/mock/original.svg", "issued_at": "2026-11-01T11:55:00Z", "expires_at": "2026-11-01T12:00:00Z"}}
    detail = {"schema_version": "0.1", "project": project, "assets": [asset], "jobs": [fixture("valid-result"), child_job_example("size_variant")], "assets_next_cursor": None, "jobs_next_cursor": None}
    list_path, detail_path = "/api/v1/projects", "/api/v1/projects/{id}"
    operations = {
        list_path: {"get": operation(list_path, "get", "listProjects", "Page projects visible to the authenticated principal", ProjectList, 200, {"simulated": example(ProjectList, {"schema_version": "0.1", "items": [project], "next_cursor": None})})},
        detail_path: {"get": operation(detail_path, "get", "getProject", "Reopen owned project with assets/jobs; follow both cursors, never silently truncate history. Original URLs are freshly authorized; inline job manifests are snapshots: GET artifacts renews download URLs", ProjectDetail, 200, {"simulated": example(ProjectDetail, detail)}, errors=COMMON_ERRORS + (ErrorCode.NOT_FOUND,))},
    }
    operations[list_path]["get"]["parameters"] = pagination_parameters()
    operations[detail_path]["get"]["parameters"] += pagination_parameters(("assets_cursor", "jobs_cursor"))
    return operations


def profile_operations():
    path = "/api/v1/profiles"
    catalog = {
        "schema_version": "0.1", "catalog_version": "0.1-B2-mock", "max_colors": 16,
        "machines": [{"profile_id": "janome_mc550e", "profile_version": "0.1", "label": "Janome MC 550E (SIMULATED proposed profile)", "hoop_profile_ids": ["sq20b"], "max_colors": 16, "calibration_status": "proposed"}],
        "hoops": [{"profile_id": "sq20b", "profile_version": "0.1", "label": "SQ20b (proposed)", "width_mm": 200, "height_mm": 200, "jef_hoop_code": 4}],
        "fabrics": [{"profile_id": "gabardina_inicial", "profile_version": "0.1", "label": "Gabardina inicial (uncalibrated)", "calibration_status": "proposed"}],
        "thread_profiles": [{"profile_id": "embroidery_thread_initial", "profile_version": "0.1", "label": "SIMULATED initial embroidery thread profile"}],
        "providers": [{"provider_id": provider, "available": False, "unavailable_reason": "SIMULATED: provider capability/credentials/model not verified in H0 contracts"} for provider in ("openai", "ollama")],
        "upload_limits": {"max_bytes": 10485760, "max_decoded_pixels": 40000000, "accepted_mime_types": ["image/png", "image/jpeg", "image/svg+xml"]},
    }
    body = operation(path, "get", "getProfiles", "Read configured profile IDs/versions, machine-hoop compatibility, color and upload limits, and verified provider availability; no credentials. Example limits are simulated, not deployment defaults", ProfileCatalog, 200, {"simulated": example(ProfileCatalog, catalog)})
    body["tags"] = ["Profiles"]
    return {path: {"get": body}}


def initial_flow(paths):
    sequence = (
        ("/api/v1/projects", "201", ProjectCreate, ProjectResponse),
        ("/api/v1/projects/{id}/assets", "201", AssetUpload, SourceAsset),
        ("/api/v1/projects/{id}/revisions", "201", RevisionRequest, RevisionResponse),
        ("/api/v1/projects/{id}/jobs", "202", JobCreate, JobResponse),
    )
    steps = []
    for index, (path, status, request_model, response_model) in enumerate(sequence, start=1):
        operation = paths[path]["post"]
        media_type, content = next(iter(operation["requestBody"]["content"].items()))
        response = operation["responses"][status]["content"]["application/json"]
        request_value = next(iter(content["examples"].values()))["value"]
        response_value = next(iter(response["examples"].values()))["value"]
        request_model.model_validate(request_value)
        response_model.model_validate(response_value)
        steps.append({"step": index, "method": "POST", "path": path.replace("{id}", "project_mock_1"), "headers": {"Authorization": "Bearer SIMULATED-SERVICE-TOKEN", "Idempotency-Key": f"mock-initial-step-{index}", "Content-Type": media_type}, "request_model": request_model.__name__, "request_body": request_value, "response_status": int(status), "response_model": response_model.__name__, "response_body": response_value})
    return {"schema_version": "0.1", "contract_revision": "B2", "simulated": True, "description": "UI adds initial revision request without a new screen or confirmation; jobs require that existing revision_id", "steps": steps}


def build_issue_catalog():
    return {
        "schema_version": "0.1", "contract_revision": "B2", "review_status": "candidate_for_freeze",
        "issues": {code.value: {"severity": rule.severity.value, "stage": rule.stage.value, "meaning": rule.meaning}
                   for code, rule in ISSUE_RULES.items()},
        "http_errors": {code.value: {"status": status, "type": "urn:embroidery:problem:" + code.lower().replace("_", "-")}
                        for code, status in ERROR_STATUS.items()},
    }


def build_paths():
    paths = {}
    for group in (project_operations(), job_operations(), revision_operations(), query_operations(), profile_operations()):
        for path, methods in group.items():
            paths.setdefault(path, {}).update(methods)
    return paths


def build_openapi():
    paths = build_paths()
    return {
        "openapi": "3.1.1", "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {"title": "Embroidery API — proposed concrete contracts", "version": "0.1",
                 "description": "Contratos v0.1 candidatos a congelar — B2, human review pending, not frozen. Contract-only specification; no HTTP handlers/worker implemented. All examples are simulated."},
        "servers": [{"url": "/", "description": "Same-origin deployment; origin configured in H1"}],
        "security": [{"BasicAuth": []}, {"ServiceBearer": []}],
        "tags": [{"name": "Projects"}, {"name": "Jobs"}, {"name": "Profiles"}],
        "paths": paths,
        "components": {
            "schemas": component_schemas(),
            "securitySchemes": {
                "BasicAuth": {"type": "http", "scheme": "basic", "description": "HTTP Basic for the private service; HTTPS outside a local trusted channel"},
                "ServiceBearer": {"type": "http", "scheme": "bearer", "description": "Simple opaque service token; no OAuth or JWT requirement"},
            },
            "parameters": {
                "ResourceId": {"name": "id", "in": "path", "required": True, "description": "Opaque project/job identifier, subject to ownership checks",
                               "schema": {"type": "string", "minLength": 1, "maxLength": 128, "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]*$"}},
                "IdempotencyKey": {"name": "Idempotency-Key", "in": "header", "required": True,
                                   "description": "Scope: authenticated user, project when present, operation. Same logical content replays status/body; changed content returns 409. Retention is deployment-configured.",
                                   "schema": {"type": "string", "minLength": 1, "maxLength": 128}},
            },
        },
        "x-review-status": "candidate_for_freeze", "x-contract-revision": "B2", "x-examples-simulated": True,
        "x-initial-flow": initial_flow(paths),
        "x-download-policy": {
            "ttl_seconds": 300, "timestamps": "UTC", "refresh_operation": "GET /api/v1/jobs/{id}/artifacts",
            "fresh_authorization_on_every_read": True, "fresh_authorization_on_use": True,
            "cache_control": "no-store", "artifact_identity_includes_urls": False,
            "behavior": "Each GET artifacts issues fresh authorized URLs, expiring at issued_at+300s. It preserves job and artifact identities/bytes and performs no export. Inline GET job manifests are snapshots; requery artifacts before downloading or after expiry. JSON bytes may vary.",
        },
        "x-upload-limits": {"bytes_setting": "MAX_UPLOAD_BYTES", "decoded_pixels_setting": "MAX_IMAGE_PIXELS", "enforcement": "H1 must configure and enforce before parsing/processing"},
        "x-semantic-invariants": [
            "Pydantic validators additionally enforce cross-field references, stage transitions, issue classification and digital/physical separation.",
            "H1 enforces authorization, immutable revisions, profile resolution, idempotency, real artifact existence and worker observations.",
            "No provider switch to cloud after local provider failure; preserve selected provider and diagnostic.",
        ],
    }


def render_json(document):
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_outputs():
    outputs = {"openapi.json": build_openapi(), "issue-catalog.json": build_issue_catalog()}
    for filename, document in outputs.items():
        (CONTRACTS / filename).write_text(render_json(document), encoding="utf-8")
    print("Generated OpenAPI for 14 operations and the v0.1 B2 incidence catalogue")


if __name__ == "__main__":
    write_outputs()
