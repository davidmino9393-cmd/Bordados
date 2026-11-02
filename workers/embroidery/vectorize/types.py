"""Local E1 results; the versioned web contracts remain unchanged."""
from dataclasses import dataclass
from typing import Any

from embroidery_contracts import EmbroideryDocument, ISSUE_RULES, Issue, IssueCode


@dataclass(frozen=True)
class VectorizeResult:
    document: EmbroideryDocument
    issues: tuple[Issue, ...]
    editable_svg: bytes
    evidence: dict[str, Any]
    duration_ms: int


class VectorizeFailure(Exception):
    """Controlled failure carrying the original catalogue severity and stage."""

    def __init__(self, issue: Issue):
        self.issue = issue
        self.code = issue.code
        super().__init__(issue.description)


def issue(code, description, evidence, object_ids=(), correction=None, *, region_ids=()):
    rule = ISSUE_RULES[code]
    return Issue(
        code=code, severity=rule.severity, stage=rule.stage,
        object_ids=tuple(object_ids), region_ids=tuple(region_ids), description=description, evidence=evidence,
        suggested_correction=correction or "Revisar la entrada y la evidencia antes de continuar.",
    )


def fail(code, description, reason, *, region_ids=(), **evidence):
    raise VectorizeFailure(issue(code, description, {"reason": reason, **evidence}, region_ids=region_ids))


def check_cancel(cancel):
    if cancel is None:
        return
    requested = cancel.is_set() if hasattr(cancel, "is_set") else cancel()
    if requested:
        fail(IssueCode.JOB_CANCELLED, "La vectorización fue cancelada.", "cancellation_requested")
