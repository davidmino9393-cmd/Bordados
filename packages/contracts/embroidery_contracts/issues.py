"""Versioned incidence vocabulary. Raw engine diagnostics remain in evidence."""
from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    BLOCKING_ERROR = "blocking_error"
    REVIEW_REQUIRED = "review_required"
    INFO = "info"


class ValidationStage(StrEnum):
    INPUT = "input"
    ANALYSIS = "analysis"
    GEOMETRY = "geometry"
    SATIN = "satin"
    ROUTING = "routing"
    DIMENSIONS = "dimensions"
    HOOP = "hoop"
    FILE = "file"
    VISUAL = "visual"
    WORKER = "worker"
    SEWOUT = "sewout"


class IssueCode(StrEnum):
    INPUT_UNSUPPORTED_FORMAT = "INPUT_UNSUPPORTED_FORMAT"
    INPUT_UNREADABLE = "INPUT_UNREADABLE"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    ANALYSIS_REFUSED = "ANALYSIS_REFUSED"
    ANALYSIS_INCOMPLETE = "ANALYSIS_INCOMPLETE"
    ANALYSIS_SCHEMA_INVALID = "ANALYSIS_SCHEMA_INVALID"
    ANALYSIS_REGION_INCOHERENT = "ANALYSIS_REGION_INCOHERENT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    LOCAL_MODEL_UNAVAILABLE = "LOCAL_MODEL_UNAVAILABLE"
    GEOMETRY_INVALID = "GEOMETRY_INVALID"
    GEOMETRY_REPAIR_AMBIGUOUS = "GEOMETRY_REPAIR_AMBIGUOUS"
    GEOMETRY_HOLES_CHANGED = "GEOMETRY_HOLES_CHANGED"
    SATIN_RAILS_UNVERIFIED = "SATIN_RAILS_UNVERIFIED"
    SATIN_WIDTH_UNSUPPORTED = "SATIN_WIDTH_UNSUPPORTED"
    SATIN_RUNG_WARNING = "SATIN_RUNG_WARNING"
    SATIN_PAIRED_NODES_VERIFIED = "SATIN_PAIRED_NODES_VERIFIED"
    ROUTING_PRECEDENCE_VIOLATION = "ROUTING_PRECEDENCE_VIOLATION"
    ROUTING_VISIBLE_TRAVEL = "ROUTING_VISIBLE_TRAVEL"
    DENSITY_REVIEW_REQUIRED = "DENSITY_REVIEW_REQUIRED"
    DIMENSIONS_EXCEEDED = "DIMENSIONS_EXCEEDED"
    HOOP_INCOMPATIBLE = "HOOP_INCOMPATIBLE"
    JEF_INVALID = "JEF_INVALID"
    JEF_UNKNOWN_COMMAND = "JEF_UNKNOWN_COMMAND"
    ENGINE_DIAGNOSTIC_UNCLASSIFIED = "ENGINE_DIAGNOSTIC_UNCLASSIFIED"
    WORKER_EXPORT_FAILED = "WORKER_EXPORT_FAILED"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    JOB_CANCELLED = "JOB_CANCELLED"
    VISUAL_MISMATCH = "VISUAL_MISMATCH"
    LEGIBILITY_RISK = "LEGIBILITY_RISK"
    PHYSICAL_ADJUSTMENT_REQUIRED = "PHYSICAL_ADJUSTMENT_REQUIRED"


@dataclass(frozen=True)
class IssueRule:
    severity: Severity
    stage: ValidationStage
    meaning: str


ERROR = Severity.BLOCKING_ERROR
REVIEW = Severity.REVIEW_REQUIRED
INFO = Severity.INFO
ISSUE_RULES = {
    IssueCode.INPUT_UNSUPPORTED_FORMAT: IssueRule(ERROR, ValidationStage.INPUT, "Unsupported input format"),
    IssueCode.INPUT_UNREADABLE: IssueRule(ERROR, ValidationStage.INPUT, "Input cannot be decoded"),
    IssueCode.INPUT_TOO_LARGE: IssueRule(ERROR, ValidationStage.INPUT, "Configured byte/pixel limit exceeded"),
    IssueCode.ANALYSIS_REFUSED: IssueRule(ERROR, ValidationStage.ANALYSIS, "Provider refused the analysis"),
    IssueCode.ANALYSIS_INCOMPLETE: IssueRule(ERROR, ValidationStage.ANALYSIS, "Provider response is incomplete"),
    IssueCode.ANALYSIS_SCHEMA_INVALID: IssueRule(ERROR, ValidationStage.ANALYSIS, "Provider response violates schema"),
    IssueCode.ANALYSIS_REGION_INCOHERENT: IssueRule(REVIEW, ValidationStage.ANALYSIS, "Region inconsistent with image"),
    IssueCode.PROVIDER_RATE_LIMITED: IssueRule(ERROR, ValidationStage.ANALYSIS, "Provider service limit reached"),
    IssueCode.PROVIDER_UNAVAILABLE: IssueRule(ERROR, ValidationStage.ANALYSIS, "Selected provider unavailable"),
    IssueCode.LOCAL_MODEL_UNAVAILABLE: IssueRule(ERROR, ValidationStage.ANALYSIS, "Selected local vision model unavailable"),
    IssueCode.GEOMETRY_INVALID: IssueRule(REVIEW, ValidationStage.GEOMETRY, "Invalid or degenerate geometry"),
    IssueCode.GEOMETRY_REPAIR_AMBIGUOUS: IssueRule(REVIEW, ValidationStage.GEOMETRY, "Repair may change identity"),
    IssueCode.GEOMETRY_HOLES_CHANGED: IssueRule(REVIEW, ValidationStage.GEOMETRY, "Repair changed holes"),
    IssueCode.SATIN_RAILS_UNVERIFIED: IssueRule(REVIEW, ValidationStage.SATIN, "Rail correspondence is unverified"),
    IssueCode.SATIN_WIDTH_UNSUPPORTED: IssueRule(REVIEW, ValidationStage.SATIN, "Physical width outside calibrated profile"),
    IssueCode.SATIN_RUNG_WARNING: IssueRule(REVIEW, ValidationStage.SATIN, "Missing guides require object-level review"),
    IssueCode.SATIN_PAIRED_NODES_VERIFIED: IssueRule(INFO, ValidationStage.SATIN, "Paired-node construction verified for object"),
    IssueCode.ROUTING_PRECEDENCE_VIOLATION: IssueRule(ERROR, ValidationStage.ROUTING, "Required precedence violated"),
    IssueCode.ROUTING_VISIBLE_TRAVEL: IssueRule(REVIEW, ValidationStage.ROUTING, "Visible connecting travel"),
    IssueCode.DENSITY_REVIEW_REQUIRED: IssueRule(REVIEW, ValidationStage.ROUTING, "Local density requires calibrated review"),
    IssueCode.DIMENSIONS_EXCEEDED: IssueRule(ERROR, ValidationStage.DIMENSIONS, "Reread bounds exceed target tolerance"),
    # Excepcion declarada en services/api/embroidery_api/runner.py (hoop_review): en size_variant cuyo unico bloqueante
    # es HOOP_INCOMPATIBLE y con un aviso con objetos o regiones, el trabajo queda en revision en vez de fallar.
    IssueCode.HOOP_INCOMPATIBLE: IssueRule(ERROR, ValidationStage.HOOP, "Hoop dimensions/code incompatible with profile"),
    IssueCode.JEF_INVALID: IssueRule(ERROR, ValidationStage.FILE, "Invalid header/table/records/end marker"),
    IssueCode.JEF_UNKNOWN_COMMAND: IssueRule(ERROR, ValidationStage.FILE, "Unknown binary command"),
    IssueCode.ENGINE_DIAGNOSTIC_UNCLASSIFIED: IssueRule(REVIEW, ValidationStage.GEOMETRY, "Unclassified diagnostic must be inspected"),
    IssueCode.WORKER_EXPORT_FAILED: IssueRule(ERROR, ValidationStage.WORKER, "Export process failed"),
    IssueCode.WORKER_TIMEOUT: IssueRule(ERROR, ValidationStage.WORKER, "Configured processing deadline exceeded"),
    IssueCode.JOB_CANCELLED: IssueRule(INFO, ValidationStage.WORKER, "Associated processes stopped after cancellation"),
    IssueCode.VISUAL_MISMATCH: IssueRule(REVIEW, ValidationStage.VISUAL, "Original/vector/JEF mismatch requires review"),
    IssueCode.LEGIBILITY_RISK: IssueRule(REVIEW, ValidationStage.VISUAL, "Measured thin area may be illegible at the requested size"),
    IssueCode.PHYSICAL_ADJUSTMENT_REQUIRED: IssueRule(REVIEW, ValidationStage.SEWOUT, "Physical sample requires a new revision"),
}
