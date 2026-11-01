"""Web request/response documents. Digital job status never encodes sewout approval."""
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from .base import ContractModel, Identifier, NonEmpty, Versioned
from .design import EmbroideryDocument
from .issues import Severity
from .results import ArtifactManifest, Issue, ValidationReport
from .settings import JobSettings


class JobStatus(StrEnum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    VECTORIZING = "vectorizing"
    DIGITIZING = "digitizing"
    VALIDATING = "validating"
    READY_FOR_SEWOUT = "ready_for_sewout"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageRecord(ContractModel):
    stage: Literal["analyzing", "vectorizing", "digitizing", "validating"]
    outcome: Literal["pending", "running", "completed", "skipped", "failed", "cancelled"]
    reason: NonEmpty | None = None
    measured_duration_ms: Annotated[int, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def skipped_reason(self):
        if self.outcome == "skipped" and self.reason is None:
            raise ValueError("Skipped stages need an explicit reason")
        return self


class JobCreate(Versioned):
    asset_id: Identifier
    revision_id: Identifier
    input_kind: Literal["prepared_svg", "raster_image"]
    settings: JobSettings

    @model_validator(mode="after")
    def image_requires_provider(self):
        if self.input_kind == "raster_image" and self.settings.ai_provider == "none":
            raise ValueError("Raster analysis requires an explicitly selected provider")
        return self


class JobResponse(Versioned):
    job_id: Identifier
    project_id: Identifier
    revision_id: Identifier
    asset_id: Identifier
    input_kind: Literal["prepared_svg", "raster_image"]
    settings_snapshot: JobSettings
    status: JobStatus
    stages: tuple[StageRecord, ...]
    cancellation_requested: bool = False
    issues: tuple[Issue, ...] = ()
    validation_report: ValidationReport | None = None
    artifact_manifest: ArtifactManifest | None = None

    @model_validator(mode="after")
    def coherent_result(self):
        for document in (self.validation_report, self.artifact_manifest):
            if document and (document.job_id != self.job_id or document.revision_id != self.revision_id):
                raise ValueError("Result documents must belong to this job and immutable revision")
        if len({record.stage for record in self.stages}) != len(self.stages):
            raise ValueError("Stage records must be unique")
        if self.status == JobStatus.FAILED and not any(
            issue.severity == Severity.BLOCKING_ERROR for issue in self.issues
        ):
            raise ValueError("failed requires a controlled blocking diagnostic")
        if self.status == JobStatus.NEEDS_REVIEW and not any(
            issue.severity == "review_required" and (issue.object_ids or issue.region_ids)
            for issue in self.issues
        ):
            raise ValueError("needs_review requires a localized review issue")
        if self.status == JobStatus.READY_FOR_SEWOUT:
            self._require_digital_result()
        return self

    def _require_digital_result(self):
        report, manifest = self.validation_report, self.artifact_manifest
        if report is None or manifest is None or not report.digital_checks_passed:
            raise ValueError("Readiness requires a passed report and artifact manifest")
        if report.metrics != manifest.reread_metrics or report.provenance != manifest.provenance:
            raise ValueError("Report and manifest must agree on reread metrics and provenance")
        if any(issue.severity != "info" for issue in self.issues):
            raise ValueError("Readiness cannot hide outstanding job issues")
        kinds = {artifact.kind for artifact in manifest.artifacts}
        if not {"jef", "preview_png", "validation_json"}.issubset(kinds):
            raise ValueError("Readiness requires JEF, reread preview and report references")
        if not any(a.kind == "preview_png" and a.derived_from == "jef_reread" for a in manifest.artifacts):
            raise ValueError("The ready preview must derive from JEF rereading")
        completed = {r.stage for r in self.stages if r.outcome == "completed"}
        if not {"digitizing", "validating"}.issubset(completed):
            raise ValueError("Readiness requires observed completed generation and validation")


class ProjectCreate(Versioned):
    name: Annotated[str, Field(min_length=1, max_length=200)]


class ProjectResponse(ProjectCreate):
    project_id: Identifier
    created_at: AwareDatetime


class RevisionCreate(Versioned):
    base_revision_id: Identifier | None
    reason: NonEmpty
    settings: JobSettings
    document: EmbroideryDocument | None = None


class RevisionResponse(Versioned):
    revision_id: Identifier
    project_id: Identifier
    base_revision_id: Identifier | None
    reason: NonEmpty
    created_at: AwareDatetime


class SewoutRecord(Versioned):
    revision_id: Identifier
    status: Literal["untested", "approved", "needs_adjustment"]
    tested_at: AwareDatetime | None = None
    fabric_profile: Identifier
    stabilizer: NonEmpty
    thread: NonEmpty
    observations: NonEmpty
    photo_asset_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def physical_evidence(self):
        if self.status != "untested" and self.tested_at is None:
            raise ValueError("Physical approval/adjustment requires the time of the physical test")
        if self.status == "untested" and self.tested_at is not None:
            raise ValueError("An untested sewout cannot have a physical test time")
        return self


class SewoutResponse(SewoutRecord):
    sewout_id: Identifier
    project_id: Identifier
    recorded_at: AwareDatetime
