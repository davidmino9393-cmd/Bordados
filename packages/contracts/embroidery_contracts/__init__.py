"""Contratos v0.1 concretos: proposal pending human review, not a running API."""
from .base import SCHEMA_VERSION
from .design import AnalysisSpec, EmbroideryDocument
from .jobs import (
    JobCreate, JobResponse, JobStatus, ProjectCreate, ProjectResponse,
    RevisionCreate, RevisionResponse, SewoutRecord, SewoutResponse,
)
from .results import ArtifactManifest, Issue, StitchPlan, ValidationReport
from .settings import JobSettings, SourceAsset
from .states import ALLOWED_TRANSITIONS, validate_transition

__all__ = [
    "SCHEMA_VERSION", "AnalysisSpec", "EmbroideryDocument", "JobCreate", "JobResponse",
    "JobStatus", "ProjectCreate", "ProjectResponse", "RevisionCreate", "RevisionResponse",
    "SewoutRecord", "SewoutResponse", "ArtifactManifest", "Issue", "StitchPlan",
    "ValidationReport", "JobSettings", "SourceAsset", "ALLOWED_TRANSITIONS", "validate_transition",
]
