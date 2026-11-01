"""Digital reports and exported artifact references; no filesystem assertions."""
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, JsonValue, model_validator

from .base import BoundsMM, ContractModel, Identifier, NonEmpty, Provenance, SHA256, Versioned
from .issues import ISSUE_RULES, IssueCode, Severity, ValidationStage
CheckKind = Literal["file", "dimensions", "hoop", "geometry", "satin", "routing", "visual"]
REQUIRED_DIGITAL_CHECKS = frozenset({"file", "dimensions", "hoop", "geometry", "satin", "routing"})


class Issue(ContractModel):
    code: IssueCode
    severity: Severity
    stage: ValidationStage
    object_ids: tuple[Identifier, ...] = ()
    region_ids: tuple[Identifier, ...] = ()
    description: NonEmpty
    evidence: dict[str, JsonValue]
    suggested_correction: NonEmpty

    @model_validator(mode="after")
    def catalogue_classification(self):
        rule = ISSUE_RULES[self.code]
        if self.severity != rule.severity or self.stage != rule.stage:
            raise ValueError("Issue stage/severity must match the v0.1 catalogue")
        if self.code == IssueCode.SATIN_PAIRED_NODES_VERIFIED and (not self.object_ids or not self.evidence):
            raise ValueError("Verified satin construction requires object-specific evidence")
        return self


class ValidationCheck(ContractModel):
    kind: CheckKind
    outcome: Literal["passed", "failed", "needs_review", "not_run"]
    method: NonEmpty


class RereadMetrics(ContractModel):
    stitch_bounds_mm: BoundsMM
    needle_stitches: Annotated[int, Field(ge=0)]
    thread_blocks: Annotated[int, Field(ge=1)]
    color_changes: Annotated[int, Field(ge=0)]
    raw_jump_commands: Annotated[int, Field(ge=0)]
    displacement_jump_commands: Annotated[int, Field(ge=0)]
    interpreted_trims: Annotated[int, Field(ge=0)]
    max_stitch_length_mm: Annotated[float, Field(ge=0)]
    jump_travel_mm: Annotated[float, Field(ge=0)]
    processing_duration_ms: Annotated[int, Field(ge=0)]
    count_method: NonEmpty
    raw_commands_artifact_id: Identifier
    physical_trim_execution_verified: Literal[False] = False


class ValidationReport(Versioned):
    report_id: Identifier
    job_id: Identifier
    revision_id: Identifier
    provenance: Provenance
    checks: tuple[ValidationCheck, ...]
    issues: tuple[Issue, ...] = ()
    digital_checks_passed: bool
    metrics: RereadMetrics | None = None

    @model_validator(mode="after")
    def passed_report_is_consistent(self):
        if len({check.kind for check in self.checks}) != len(self.checks):
            raise ValueError("Each digital check appears at most once")
        if not self.digital_checks_passed:
            return self
        passed = {check.kind for check in self.checks if check.outcome == "passed"}
        if not REQUIRED_DIGITAL_CHECKS.issubset(passed) or self.metrics is None:
            raise ValueError("Digital acceptance requires all required checks and reread metrics")
        if any(check.outcome in {"failed", "needs_review"} for check in self.checks):
            raise ValueError("Digital acceptance cannot hide failed checks")
        if any(issue.severity != "info" for issue in self.issues):
            raise ValueError("Unresolved blocking/review issues prevent digital acceptance")
        return self


class ArtifactDownload(ContractModel):
    url: AnyHttpUrl
    expires_at: AwareDatetime


class Artifact(ContractModel):
    artifact_id: Identifier
    kind: Literal[
        "jef", "editable_svg", "inkstitch_svg", "preview_png", "validation_json",
        "stitch_plan_json", "raw_commands_json", "provider_raw_json",
    ]
    filename: Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")]
    media_type: NonEmpty
    sha256: SHA256
    byte_size: Annotated[int, Field(gt=0)]
    derived_from: Literal["export", "jef_reread", "document", "validation", "provider"]
    download: ArtifactDownload | None = None


class ArtifactManifest(Versioned):
    manifest_id: Identifier
    job_id: Identifier
    revision_id: Identifier
    provenance: Provenance
    input_sha256: SHA256
    settings_sha256: SHA256
    geometry_sha256: SHA256
    artifacts: tuple[Artifact, ...]
    reread_metrics: RereadMetrics

    @model_validator(mode="after")
    def unique_artifacts(self):
        ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(set(ids)) != len(ids):
            raise ValueError("Artifact identifiers must be unique within a manifest")
        raw_id = self.reread_metrics.raw_commands_artifact_id
        if not any(a.artifact_id == raw_id and a.kind == "raw_commands_json" for a in self.artifacts):
            raise ValueError("Reread metrics must reference raw commands in this manifest")
        return self


class StitchCommand(ContractModel):
    x_mm: float
    y_mm: float
    command: Literal["stitch", "jump", "trim", "color_change", "stop", "end"]
    thread_block: Annotated[int, Field(ge=0)]
    object_id: Identifier | None = None


class ThreadBlock(ContractModel):
    block_index: Annotated[int, Field(ge=0)]
    work_color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    jef_catalog_color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]
    jef_catalog_number: str


class StitchPlan(Versioned):
    plan_id: Identifier
    job_id: Identifier
    revision_id: Identifier
    unit: Literal["mm"] = "mm"
    origin: Literal["design_top_left"] = "design_top_left"
    x_axis: Literal["right"] = "right"
    y_axis: Literal["down"] = "down"
    # Conversion from the engine's frame into this contract frame is explicit.
    engine_to_document_mm: tuple[float, float, float, float, float, float]
    stitch_bounds_mm: BoundsMM
    commands: tuple[StitchCommand, ...]
    thread_blocks: tuple[ThreadBlock, ...]
    provenance: Provenance
