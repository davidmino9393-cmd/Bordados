"""Input and physical settings. Profile names reference versioned server data."""
from typing import Annotated, Literal

from pydantic import Field

from .base import BoundsPX, ContractModel, Identifier, NonEmpty, PositiveMM, SHA256, Versioned


class TargetSize(ContractModel):
    width_mm: PositiveMM
    height_mm: PositiveMM
    fit: Literal["contain"] = "contain"


class HoopSettings(ContractModel):
    profile_id: Identifier
    profile_version: Identifier
    width_mm: PositiveMM
    height_mm: PositiveMM
    jef_hoop_code: Annotated[int, Field(ge=0)]


class JobSettings(Versioned):
    target: TargetSize
    machine_profile: Identifier
    machine_profile_version: Identifier
    hoop: HoopSettings
    fabric_profile: Identifier
    fabric_profile_version: Identifier
    thread_profile: Identifier
    color_limit: Annotated[int, Field(ge=1, le=256)]
    ai_provider: Literal["none", "openai", "ollama"]
    ai_model: NonEmpty | None = None


class SourceAsset(Versioned):
    asset_id: Identifier
    project_id: Identifier
    sha256: SHA256
    media_type: Literal["image/png", "image/jpeg", "image/svg+xml"]
    original_width_px: Annotated[int, Field(gt=0)] | None = None
    original_height_px: Annotated[int, Field(gt=0)] | None = None
    crop_px: BoundsPX | None = None
    original_preserved: Literal[True] = True
    # Private storage keys belong to persistence, never to a web response.
