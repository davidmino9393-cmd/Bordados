"""Allowed digital state transitions; applying a transition validates its payload."""
from .jobs import JobResponse, JobStatus

ACTIVE_STATES = frozenset({
    JobStatus.QUEUED, JobStatus.ANALYZING, JobStatus.VECTORIZING,
    JobStatus.DIGITIZING, JobStatus.VALIDATING,
})
INTERRUPTIONS = frozenset({JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.NEEDS_REVIEW})
ALLOWED_TRANSITIONS = {
    JobStatus.QUEUED: frozenset({JobStatus.ANALYZING, JobStatus.VECTORIZING, JobStatus.DIGITIZING}) | INTERRUPTIONS,
    JobStatus.ANALYZING: frozenset({JobStatus.VECTORIZING}) | INTERRUPTIONS,
    JobStatus.VECTORIZING: frozenset({JobStatus.DIGITIZING}) | INTERRUPTIONS,
    JobStatus.DIGITIZING: frozenset({JobStatus.VALIDATING}) | INTERRUPTIONS,
    JobStatus.VALIDATING: frozenset({JobStatus.READY_FOR_SEWOUT}) | INTERRUPTIONS,
    JobStatus.READY_FOR_SEWOUT: frozenset(),
    JobStatus.NEEDS_REVIEW: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


def validate_transition(previous: JobResponse, following: JobResponse) -> JobResponse:
    """Called by trusted server code, never a public set-status operation."""
    if following.status not in ALLOWED_TRANSITIONS[previous.status]:
        raise ValueError(f"Forbidden transition: {previous.status} -> {following.status}")
    immutable_fields = ("job_id", "project_id", "revision_id", "asset_id", "input_kind", "settings_snapshot", "parent_job_id")
    if any(getattr(previous, name) != getattr(following, name) for name in immutable_fields):
        raise ValueError("A transition cannot mutate job identity or its settings revision")
    if previous.status == JobStatus.QUEUED and following.status == JobStatus.DIGITIZING:
        skipped = {r.stage for r in following.stages if r.outcome == "skipped"}
        if following.input_kind != "prepared_svg" or not {"analyzing", "vectorizing"}.issubset(skipped):
            raise ValueError("Only prepared SVG may skip analysis/vectorization, with recorded reasons")
    if previous.status == JobStatus.QUEUED and following.status == JobStatus.VECTORIZING:
        analysis = next((r for r in following.stages if r.stage == "analyzing"), None)
        if (following.input_kind != "raster_image" or following.parent_job_id is None
                or analysis is None or analysis.outcome != "skipped"):
            raise ValueError("Only a continuation after an approved analysis may skip analysis, with parent job and recorded reason")
    return JobResponse.model_validate(following.model_dump())
