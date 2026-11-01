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
    StitchPlan, ValidationReport,
)
from embroidery_contracts.http import ERROR_STATUS, ErrorCode
from embroidery_contracts.issues import ISSUE_RULES

MODELS = (
    JobSettings, SourceAsset, AnalysisSpec, EmbroideryDocument, StitchPlan,
    ValidationReport, ArtifactManifest, JobCreate, JobResponse, ProjectCreate,
    ProjectResponse, RevisionCreate, RevisionResponse, SewoutRecord, SewoutResponse,
    AssetUpload, CancelRequest, ProblemResponse,
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
    model.model_validate(payload)
    return {"summary": summary, "value": payload}


def job_example(status, cancellation_requested=False):
    payload = deepcopy(fixture("valid-result"))
    payload.update(status=status, cancellation_requested=cancellation_requested,
                   validation_report=None, artifact_manifest=None)
    for record in payload["stages"]:
        if record["stage"] in {"digitizing", "validating"}:
            record["outcome"] = "running" if record["stage"] == status else "pending"
            record.pop("measured_duration_ms", None)
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
        "headers": {"X-Request-ID": {"schema": {"type": "string"}, "description": "Server correlation identifier"}},
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
        responses["401"]["headers"]["WWW-Authenticate"] = {"schema": {"type": "string"}, "example": "Bearer"}
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
             "sha256": "a" * 64, "media_type": "image/svg+xml", "original_preserved": True}
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
        create_path: {"post": operation(create_path, "post", "createJob", "Enqueue a job using an owned asset and immutable revision/settings snapshot", JobResponse, 202,
                         {"queued": example(JobResponse, job_example("queued"))}, JobCreate, fixture("generation-from-svg"), POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
        get_path: {"get": operation(get_path, "get", "getJob", "Read observed status, diagnostics and stage durations; polling is supported", JobResponse, 200,
                      {case: example(JobResponse, fixture(case)) for case in ("valid-result", "needs-review", "failure", "cancellation")}, errors=existing)},
        artifact_path: {"get": operation(artifact_path, "get", "getJobArtifacts", "Read bounded job manifest and obtain authorized expiring download URLs; 409 if unavailable", ArtifactManifest, 200,
                           {"simulated": example(ArtifactManifest, ready["artifact_manifest"])}, errors=existing + (ErrorCode.ARTIFACTS_UNAVAILABLE,))},
        cancel_path: {"post": operation(cancel_path, "post", "cancelJob", "Request cancellation; 202 retains observed status until processes stop", JobResponse, 202,
                         {"requested": example(JobResponse, job_example("digitizing", True))}, CancelRequest, {"schema_version": "0.1"}, POST_ERRORS + (ErrorCode.NOT_FOUND,))},
    }
    jobs[cancel_path]["post"]["responses"]["200"] = json_response(
        JobResponse, "Already terminal: return the observed terminal status without restarting or changing it",
        {"alreadyCancelled": example(JobResponse, fixture("cancellation"))},
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
    return {
        revisions_path: {"post": operation(revisions_path, "post", "createRevision", "Create immutable initial revision (null base only once), correction or size variant", RevisionResponse, 201,
                            {"initial": example(RevisionResponse, result)}, RevisionCreate, revision, POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
        sewouts_path: {"post": operation(sewouts_path, "post", "recordSewout", "Record the authorized user's physical observation for an owned revision; never changes digital job status", SewoutResponse, 201,
                          {"simulated": example(SewoutResponse, sewout_result)}, SewoutRecord, sewout, POST_ERRORS + (ErrorCode.NOT_FOUND, ErrorCode.REVISION_CONFLICT))},
    }


def build_issue_catalog():
    return {
        "schema_version": "0.1", "review_status": "pending_human_review",
        "issues": {code.value: {"severity": rule.severity.value, "stage": rule.stage.value, "meaning": rule.meaning}
                   for code, rule in ISSUE_RULES.items()},
        "http_errors": {code.value: {"status": status, "type": "urn:embroidery:problem:" + code.lower().replace("_", "-")}
                        for code, status in ERROR_STATUS.items()},
    }


def build_openapi():
    return {
        "openapi": "3.1.1", "jsonSchemaDialect": "https://json-schema.org/draft/2020-12/schema",
        "info": {"title": "Embroidery API — proposed concrete contracts", "version": "0.1",
                 "description": "Human review pending. Contract-only specification; no HTTP handlers/worker implemented. All examples are simulated."},
        "servers": [{"url": "/", "description": "Same-origin deployment; origin configured in H1"}],
        "security": [{"BearerAuth": []}],
        "tags": [{"name": "Projects"}, {"name": "Jobs"}],
        "paths": {**project_operations(), **job_operations(), **revision_operations()},
        "components": {
            "schemas": component_schemas(),
            "securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer", "description": "Opaque authenticated credential; JWT/provider choice is not prescribed"}},
            "parameters": {
                "ResourceId": {"name": "id", "in": "path", "required": True, "description": "Opaque project/job identifier, subject to ownership checks",
                               "schema": {"type": "string", "minLength": 1, "maxLength": 128, "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]*$"}},
                "IdempotencyKey": {"name": "Idempotency-Key", "in": "header", "required": True,
                                   "description": "Scope: authenticated user, project when present, operation. Same logical content replays status/body; changed content returns 409. Retention is deployment-configured.",
                                   "schema": {"type": "string", "minLength": 1, "maxLength": 128}},
            },
        },
        "x-review-status": "pending_human_review", "x-examples-simulated": True,
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
    print("Generated OpenAPI for 8 operations and the v0.1 incidence catalogue")


if __name__ == "__main__":
    write_outputs()
