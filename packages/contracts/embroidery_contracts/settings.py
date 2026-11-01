"""Input and physical settings. Profile names reference versioned server data."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import BoundsPX, ContractModel, Identifier, NonEmpty, PositiveMM, SHA256, Versioned
from .results import ArtifactDownload


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
    hoop_profile: Identifier
    hoop: HoopSettings
    fabric_profile: Identifier
    fabric_profile_version: Identifier
    thread_profile: Identifier
    color_limit: Annotated[int, Field(ge=1, le=256)]
    ai_provider: Literal["none", "openai", "ollama"]
    ai_model: NonEmpty | None = None

    @model_validator(mode="after")
    def matching_hoop_profile(self):
        if self.hoop_profile != self.hoop.profile_id:
            raise ValueError("hoop_profile must match the immutable hoop profile snapshot")
        return self


class SourceAsset(Versioned):
    asset_id: Identifier
    project_id: Identifier
    sha256: SHA256
    media_type: Literal["image/png", "image/jpeg", "image/svg+xml"]
    original_filename: Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[^/\\\x00-\x1f]+$")]
    original_download: ArtifactDownload | None = Field(default=None, json_schema_extra={"readOnly": True})
    original_width_px: Annotated[int, Field(gt=0)] | None = None
    original_height_px: Annotated[int, Field(gt=0)] | None = None
    crop_px: BoundsPX | None = None
    original_preserved: Literal[True] = True
    # Private storage keys belong to persistence, never to a web response.

    @model_validator(mode="after")
    def pixel_dimensions_and_crop(self):
        width, height = self.original_width_px, self.original_height_px
        if (width is None) != (height is None):
            raise ValueError("Pixel width and height must be provided together")
        if self.media_type != "image/svg+xml" and width is None:
            raise ValueError("Raster uploads require original pixel dimensions")
        crop = self.crop_px
        if crop and (width is None or crop.x_px + crop.width_px > width or crop.y_px + crop.height_px > height):
            raise ValueError("A crop must lie within known original pixel dimensions")
        return self
