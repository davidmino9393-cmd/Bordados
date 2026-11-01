"""Common types for the proposed embroidery contract 0.1."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1"
Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")]
NonEmpty = Annotated[str, Field(min_length=1, max_length=2000)]
SHA256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
PositiveMM = Annotated[float, Field(gt=0)]
NonNegativeMM = Annotated[float, Field(ge=0)]
ColorHex = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, validate_default=True)


class Versioned(ContractModel):
    schema_version: Literal["0.1"] = SCHEMA_VERSION


class PointMM(ContractModel):
    x_mm: float
    y_mm: float


class BoundsMM(ContractModel):
    min_x_mm: float
    min_y_mm: float
    max_x_mm: float
    max_y_mm: float

    @model_validator(mode="after")
    def ordered(self):
        if self.min_x_mm > self.max_x_mm or self.min_y_mm > self.max_y_mm:
            raise ValueError("Bounds minima must not exceed maxima")
        return self


class BoundsPX(ContractModel):
    x_px: Annotated[float, Field(ge=0)]
    y_px: Annotated[float, Field(ge=0)]
    width_px: Annotated[float, Field(gt=0)]
    height_px: Annotated[float, Field(gt=0)]


class Provenance(ContractModel):
    simulated: bool
    method: NonEmpty
    engine_version: NonEmpty | None = None
    parser_version: NonEmpty | None = None
