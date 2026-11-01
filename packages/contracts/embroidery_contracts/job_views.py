"""Server-owned summaries derived from issues or an actual physical record."""
from typing import Literal

from pydantic import AwareDatetime, model_validator

from .base import ContractModel, Identifier, NonEmpty
from .issues import IssueCode
from .results import Issue

SewoutStatus = Literal["untested", "approved", "needs_adjustment"]


class FailureSummary(ContractModel):
    code: IssueCode
    message: NonEmpty
    stage: Literal["queued", "analyzing", "vectorizing", "digitizing", "validating"]


class ReviewSummary(ContractModel):
    cause: NonEmpty
    issues: tuple[Issue, ...]
    object_ids: tuple[Identifier, ...]
    region_ids: tuple[Identifier, ...]


class SewoutProjection(ContractModel):
    sewout_id: Identifier
    revision_id: Identifier
    status: SewoutStatus
    tested_at: AwareDatetime | None
    observations: NonEmpty
    photo_asset_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def physical_time(self):
        if (self.status == "untested") != (self.tested_at is None):
            raise ValueError("Physical approval/adjustment needs a test time; untested has none")
        return self
