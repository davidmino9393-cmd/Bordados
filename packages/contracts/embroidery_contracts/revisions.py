"""Initial revisions and parent-job variants/corrections share one POST route."""
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel, model_validator

from .base import ContractModel, Identifier, Versioned
from .design import Technique
from .jobs import RevisionCreate
from .settings import TargetSize


class SizeVariantRevision(Versioned):
    kind: Literal["size_variant"]
    parent_job_id: Identifier
    target: TargetSize


class ExcludeRegion(ContractModel):
    action: Literal["exclude_region"]
    object_id: Identifier | None = None
    region_id: Identifier | None = None

    @model_validator(mode="after")
    def exactly_one_target(self):
        if (self.object_id is None) == (self.region_id is None):
            raise ValueError("exclude_region requires exactly one object_id or region_id")
        return self


class SetTechnique(ContractModel):
    action: Literal["set_technique"]
    object_id: Identifier
    technique: Technique


Correction = Annotated[ExcludeRegion | SetTechnique, Field(discriminator="action")]


class CorrectionRevision(Versioned):
    kind: Literal["correction"]
    parent_job_id: Identifier
    corrections: Annotated[tuple[Correction, ...], Field(min_length=1)]


class RevisionRequest(RootModel[RevisionCreate | SizeVariantRevision | CorrectionRevision]):
    model_config = ConfigDict(frozen=True)
