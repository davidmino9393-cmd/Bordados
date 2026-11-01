"""Contratos v0.1 concretos: proposal pending human review, not a running API."""
from .base import SCHEMA_VERSION
from .http import AssetUpload, CancelRequest, ErrorCode, ProblemResponse
from .issues import ISSUE_RULES, IssueCode, Severity, ValidationStage
from .design import AnalysisSpec, EmbroideryDocument
from .jobs import (
    JobCreate, JobResponse, JobStatus, ProjectCreate, ProjectResponse,
    RevisionCreate, RevisionResponse, SewoutRecord, SewoutResponse,
)
from .results import ArtifactManifest, AuthorizedArtifactManifest, Issue, StitchPlan, ValidationReport
from .settings import JobSettings, SourceAsset
from .states import ALLOWED_TRANSITIONS, validate_transition
from .profiles import ProfileCatalog
from .queries import ProjectDetail, ProjectList, RevisionList
from .revisions import CorrectionRevision, RevisionRequest, SizeVariantRevision

__all__ = [
    "SCHEMA_VERSION", "AnalysisSpec", "EmbroideryDocument", "JobCreate", "JobResponse",
    "JobStatus", "ProjectCreate", "ProjectResponse", "RevisionCreate", "RevisionResponse",
    "SewoutRecord", "SewoutResponse", "ArtifactManifest", "Issue", "StitchPlan",
    "ValidationReport", "JobSettings", "SourceAsset", "ALLOWED_TRANSITIONS", "validate_transition",
    "AssetUpload", "CancelRequest", "ErrorCode", "ProblemResponse", "ISSUE_RULES", "IssueCode",
    "Severity", "ValidationStage",
    "ProfileCatalog", "ProjectDetail", "ProjectList", "RevisionList", "RevisionRequest",
    "SizeVariantRevision", "CorrectionRevision",
    "AuthorizedArtifactManifest",
]
