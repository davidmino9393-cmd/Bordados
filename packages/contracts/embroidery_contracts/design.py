"""Editable geometry and semantic annotations, without geometry algorithms."""
from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from .base import (
    BoundsMM, BoundsPX, ColorHex, ContractModel, Identifier, NonEmpty,
    NonNegativeMM, PointMM, PositiveMM, Versioned,
)

Technique = Literal["running", "bean", "satin", "fill"]


class AnalysisRegion(ContractModel):
    region_id: Identifier
    bounds_px: BoundsPX
    representation: Literal["estimated_bbox"] = "estimated_bbox"
    visual_role: NonEmpty
    observed_text: str | None = None
    suggested_colors: tuple[ColorHex, ...] = ()
    uncertainties: tuple[NonEmpty, ...] = ()


class AnalysisSpec(Versioned):
    analysis_id: Identifier
    asset_id: Identifier
    provider: Literal["openai", "ollama"]
    model: NonEmpty
    prompt_version: Identifier
    original_response_artifact_id: Identifier
    regions: tuple[AnalysisRegion, ...]
    duration_ms: Annotated[int, Field(ge=0)]
    input_tokens: Annotated[int, Field(ge=0)] | None = None
    output_tokens: Annotated[int, Field(ge=0)] | None = None


class CoordinateFrame(ContractModel):
    unit: Literal["mm"] = "mm"
    origin: Literal["design_top_left"] = "design_top_left"
    x_axis: Literal["right"] = "right"
    y_axis: Literal["down"] = "down"
    transform_version: Identifier
    # SVG affine convention: x_mm=a*x_px+c*y_px+e, y_mm=b*x_px+d*y_px+f.
    source_px_to_mm: tuple[float, float, float, float, float, float] | None = None


class SatinRails(ContractModel):
    correspondence: Literal["paired_nodes", "guides"]
    left_rail_mm: Annotated[tuple[PointMM, ...], Field(min_length=2)]
    right_rail_mm: Annotated[tuple[PointMM, ...], Field(min_length=2)]
    guides_mm: tuple[tuple[PointMM, PointMM], ...] = ()

    @model_validator(mode="after")
    def correspondence_data(self):
        if self.correspondence == "paired_nodes" and len(self.left_rail_mm) != len(self.right_rail_mm):
            raise ValueError("Paired-node satin rails require equal node counts")
        if self.correspondence == "guides" and not self.guides_mm:
            raise ValueError("Guide-based satin requires guides")
        return self


class StitchParameters(ContractModel):
    stitch_length_mm: PositiveMM
    spacing_mm: PositiveMM | None = None
    pull_compensation_mm: NonNegativeMM = 0
    underlay: Literal["none", "center_walk", "contour", "zigzag", "fill"] = "none"
    underlay_spacing_mm: PositiveMM | None = None
    direction_deg: Annotated[float, Field(ge=0, lt=360)] | None = None


class EmbroideryObject(ContractModel):
    object_id: Identifier
    source_region_id: Identifier | None = None
    geometry_kind: Literal["verified_curve", "verified_mask", "prepared_svg_path"]
    path_data_mm: Annotated[str, Field(min_length=1)]
    bounds_mm: BoundsMM
    role: NonEmpty
    work_color: ColorHex
    proposed_technique: Technique
    effective_technique: Technique
    parameters: StitchParameters
    satin: SatinRails | None = None

    @model_validator(mode="after")
    def satin_data(self):
        if self.effective_technique == "satin" and self.satin is None:
            raise ValueError("Effective satin requires rail/correspondence data")
        return self


class Precedence(ContractModel):
    before_object_id: Identifier
    after_object_id: Identifier
    reason: NonEmpty


class DesignDecision(ContractModel):
    object_id: Identifier
    reason: NonEmpty
    field: NonEmpty
    previous_value: JsonValue
    new_value: JsonValue
    origin: Literal["user", "rule", "ai_proposal"]


class EmbroideryDocument(Versioned):
    document_id: Identifier
    revision_id: Identifier
    asset_id: Identifier
    coordinates: CoordinateFrame
    page_bounds_mm: BoundsMM
    object_bounds_mm: BoundsMM
    objects: tuple[EmbroideryObject, ...]
    precedences: tuple[Precedence, ...] = ()
    decisions: tuple[DesignDecision, ...] = ()
