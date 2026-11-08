"""Pure E1 raster-to-mask geometry. No CLI, storage, provider, or sewout decision."""
import hashlib
import json
import math
from time import perf_counter
from threading import Event
from typing import Callable
from xml.etree import ElementTree as ET

from embroidery_contracts import AnalysisSpec, EmbroideryDocument, IssueCode, JobSettings, SourceAsset
from embroidery_contracts.base import BoundsMM
from embroidery_contracts.design import CoordinateFrame, DesignDecision, EmbroideryObject, StitchParameters

from .contours import contours
from .segmentation import decode, segment
from .thin_features import measure as measure_thin_features
from .types import VectorizeResult, check_cancel, fail, issue
from . import reference_geometry

METHOD_VERSION = "e1-pixel-mask-v4"
TRANSFORM_VERSION = "raster-contain-v1"
PROVISIONAL_STITCH_LENGTH_MM = 2.5
PROVISIONAL_FILL_SPACING_MM = 0.4
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
COORDINATE_DECIMAL_PLACES = 9
MIN_COORDINATE_STEP_MM = 10.0 ** -COORDINATE_DECIMAL_PLACES


def vectorize(image: bytes, media_type: str, asset: SourceAsset, analysis: AnalysisSpec | None,
              settings: JobSettings, *, job_id: str, revision_id: str,
              cancel: Event | Callable[[], bool] | None = None) -> VectorizeResult:
    """Return measured mask geometry; every result still requires H3 validation.

    image is the original encoded PNG/JPEG bytes. cancel may be a threading.Event,
    a zero-argument predicate, or None. The function never mutates its inputs.
    """
    started = perf_counter()
    rgba = decode(image, media_type, asset, cancel)
    _validate_analysis(analysis, asset)
    segmented = segment(rgba, asset, settings.color_limit, cancel)
    traced = contours(segmented, cancel)
    affine = _affine(segmented, settings)
    objects = tuple(_object(mask, affine, segmented, revision_id, cancel) for mask in traced)
    document = _document(objects, affine, asset, settings, job_id, revision_id)
    document, widths = reference_geometry.apply(document, cancel)
    evidence = _evidence(segmented, traced, asset, analysis, settings, affine)
    evidence["stroke_width"] = widths
    evidence["minimum_feature"] = measure_thin_features(segmented, traced, objects, abs(affine[0]), cancel)
    issues = _issues(objects, segmented.evidence, evidence["minimum_feature"]) + reference_geometry.legibility_issues(widths)
    check_cancel(cancel)
    svg = _editable_svg(document, evidence)
    check_cancel(cancel)
    return VectorizeResult(document, issues, svg, evidence, max(0, int((perf_counter() - started) * 1000)))


def _validate_analysis(analysis, asset):
    if analysis is None:
        return
    if analysis.asset_id != asset.asset_id:
        fail(IssueCode.ANALYSIS_SCHEMA_INVALID, "El análisis pertenece a otro asset.", "analysis_asset_mismatch")
    for region in analysis.regions:
        bounds = region.bounds_px
        if bounds.x_px + bounds.width_px > asset.original_width_px or bounds.y_px + bounds.height_px > asset.original_height_px:
            fail(IssueCode.ANALYSIS_REGION_INCOHERENT, "Una región estimada está fuera de la imagen.", "analysis_bounds_outside_image", region_id=region.region_id, region_ids=(region.region_id,))


def _affine(segmented, settings):
    scale = min(settings.target.width_mm / segmented.width, settings.target.height_mm / segmented.height)
    maximum_coordinate = max(settings.target.width_mm, settings.target.height_mm)
    if scale < MIN_COORDINATE_STEP_MM or scale <= math.ulp(maximum_coordinate):
        fail(IssueCode.GEOMETRY_INVALID, "La escala no permite conservar los píxeles con la precisión de salida.", "output_coordinate_precision", scale_mm_per_px=scale)
    offset_x = (settings.target.width_mm - segmented.width * scale) / 2
    offset_y = (settings.target.height_mm - segmented.height * scale) / 2
    affine = (scale, 0.0, 0.0, scale, offset_x - segmented.origin_x * scale, offset_y - segmented.origin_y * scale)
    if any(not math.isfinite(value) for value in affine):
        fail(IssueCode.GEOMETRY_INVALID, "La transformación supera la precisión numérica disponible.", "non_finite_transform")
    return affine


def _mm(point, affine, segmented):
    x, y = point[0] + segmented.origin_x, point[1] + segmented.origin_y
    return (x * affine[0] + affine[4], y * affine[3] + affine[5])


def _number(value):
    rounded = round(value, COORDINATE_DECIMAL_PLACES)
    return f"{rounded:.{COORDINATE_DECIMAL_PLACES}f}".rstrip("0").rstrip(".") or "0"


def _path(mask, affine, segmented, cancel):
    subpaths = []
    for loop in mask.loops:
        points = []
        for index, point in enumerate(loop):
            if index % 1024 == 0:
                check_cancel(cancel)
            points.append(_mm(point, affine, segmented))
        commands = [f"M{_number(points[0][0])},{_number(points[0][1])}"]
        commands.extend(f"L{_number(x)},{_number(y)}" for x, y in points[1:])
        subpaths.append(" ".join(commands) + " Z")
    return " ".join(subpaths)


def _object(mask, affine, segmented, revision_id, cancel):
    path = _path(mask, affine, segmented, cancel)
    digest = hashlib.sha256(f"{revision_id}\0{mask.color}\0{path}".encode()).hexdigest()[:24]
    first = _mm(mask.bounds[:2], affine, segmented)
    last = _mm(mask.bounds[2:], affine, segmented)
    return EmbroideryObject(
        object_id=f"mask_{digest}", source_region_id=None,
        geometry_kind="verified_mask", path_data_mm=path,
        bounds_mm=BoundsMM(min_x_mm=first[0], min_y_mm=first[1], max_x_mm=last[0], max_y_mm=last[1]),
        role="pixel_colour_mask", work_color=mask.color,
        proposed_technique="fill", effective_technique="fill",
        parameters=StitchParameters(stitch_length_mm=PROVISIONAL_STITCH_LENGTH_MM,
                                   spacing_mm=PROVISIONAL_FILL_SPACING_MM, underlay="none"),
    )


def _document(objects, affine, asset, settings, job_id, revision_id):
    digest = hashlib.sha256(f"{job_id}\0{revision_id}\0{asset.sha256}\0{settings.model_dump_json()}".encode()).hexdigest()[:24]
    return EmbroideryDocument(
        document_id=f"doc_{digest}", revision_id=revision_id, asset_id=asset.asset_id,
        coordinates=CoordinateFrame(transform_version=TRANSFORM_VERSION, source_px_to_mm=affine),
        page_bounds_mm=BoundsMM(min_x_mm=0, min_y_mm=0, max_x_mm=settings.target.width_mm, max_y_mm=settings.target.height_mm),
        object_bounds_mm=BoundsMM(min_x_mm=min(item.bounds_mm.min_x_mm for item in objects),
                                  min_y_mm=min(item.bounds_mm.min_y_mm for item in objects),
                                  max_x_mm=max(item.bounds_mm.max_x_mm for item in objects),
                                  max_y_mm=max(item.bounds_mm.max_y_mm for item in objects)),
        objects=objects,
        decisions=tuple(DesignDecision(
            object_id=obj.object_id, field="parameters", origin="rule", previous_value=None,
            new_value={"parameters": obj.parameters.model_dump(mode="json"),
                       "effective_technique": obj.effective_technique, "h3_validation_required": True},
            reason="Valores provisionales de E1 para representar geometría; H3 debe validar técnica y parámetros físicos antes de digitalizar.",
        ) for obj in objects),
    )


def _evidence(segmented, traced, asset, analysis, settings, affine):
    annotations = [] if analysis is None else [
        {"region_id": region.region_id, "estimated_bounds_px": region.bounds_px.model_dump(mode="json"),
         "visual_role": region.visual_role, "observed_text": region.observed_text,
         "uncertainties": list(region.uncertainties), "geometry_source": False}
        for region in analysis.regions
    ]
    return {
        "method": METHOD_VERSION, "simulated": False, "input_sha256": asset.sha256,
        "geometry_source": "decoded_pixels_after_explicit_background_and_palette_rules",
        "geometry_kind": "verified_mask", "curve_fitting": False,
        "verified_mask_means": "closed pixel edges reproduce the explicit segmented mask; not semantic or colour-fidelity approval",
        "fit": "contain", "source_px_to_mm": list(affine),
        "coordinate_rounding_decimal_places": COORDINATE_DECIMAL_PLACES,
        "segmentation": segmented.evidence,
        "masks": [{"colour": mask.color, "pixel_count": mask.pixel_count,
                   "boundary_edges": mask.edge_count, "subpaths": len(mask.loops),
                   "holes": mask.holes, "exact_area_px2": mask.pixel_count,
                   "bounds_crop_px": list(mask.bounds)} for mask in traced],
        "analysis_id": analysis.analysis_id if analysis else None,
        "analysis_regions_are_estimates": True, "annotations": annotations,
        "text_handling": "annotation_only_no_font_substitution",
        "h3_validation_required": True,
        "provisional_fields": ["effective_technique", "proposed_technique", "parameters"],
        "technique_selection": "reference_per_ring_median_square_opening_running_below_0.9mm_scaled_fill_otherwise",
        "settings_sha256": hashlib.sha256(settings.model_dump_json().encode()).hexdigest(),
        "no_sewout_readiness_claim": True,
    }


def _issues(objects, segmentation_evidence, minimum_feature):
    ids = tuple(item.object_id for item in objects)
    output = [issue(
        IssueCode.DENSITY_REVIEW_REQUIRED,
        "La técnica y los parámetros son provisionales; H3 debe validarlos antes de digitalizar.",
        {"h3_validation_required": True, "parameters_calibrated": False,
         "provisional_stitch_length_mm": PROVISIONAL_STITCH_LENGTH_MM,
         "provisional_spacing_mm": PROVISIONAL_FILL_SPACING_MM,
         "minimum_feature_mm": minimum_feature["min_width_mm"], "minimum_feature_is_calibrated": False,
         "thin_feature_fraction_by_object": {key: value["thin_fraction"] for key, value in minimum_feature["objects"].items()}}, ids,
        "Validar técnica, densidad, compensación, base y el ancho mínimo bordable con el perfil físico en H3 (los trazos más finos no se borran ni se engrosan).",
    )]
    if segmentation_evidence["partial_alpha_pixels"]:
        output.append(issue(
            IssueCode.GEOMETRY_REPAIR_AMBIGUOUS,
            "La transparencia parcial se binarizó y requiere comparación visual.",
            {"partial_alpha_pixels": segmentation_evidence["partial_alpha_pixels"],
             "alpha_threshold": segmentation_evidence["alpha_threshold"]}, ids,
        ))
    if segmentation_evidence["background_is_assumption"]:
        output.append(issue(
            IssueCode.GEOMETRY_REPAIR_AMBIGUOUS,
            "La interpretación del fondo opaco es una regla explícita, no una máscara semántica confirmada.",
            {"background_method": segmentation_evidence["background_method"],
             "white_removed_globally": segmentation_evidence["white_removed_globally"]}, ids,
        ))
    if segmentation_evidence["changed_rgb_pixels"]:
        output.append(issue(
            IssueCode.VISUAL_MISMATCH,
            "La cuantización cambió colores medidos; revisar la paleta y los bordes antes de digitalizar.",
            {"changed_rgb_pixels": segmentation_evidence["changed_rgb_pixels"],
             "max_channel_error_rgb": segmentation_evidence["max_channel_error_rgb"],
             "mean_absolute_channel_error_rgb": segmentation_evidence["mean_absolute_channel_error_rgb"],
             "output_colours": segmentation_evidence["output_colours"]}, ids,
            "Comparar la imagen con el SVG y confirmar la paleta y los bordes.",
        ))
    return tuple(output)


def _editable_svg(document, evidence):
    page = document.page_bounds_mm
    root = ET.Element("svg", {"xmlns": SVG_NAMESPACE,
                              "width": f"{_number(page.max_x_mm)}mm", "height": f"{_number(page.max_y_mm)}mm",
                              "viewBox": f"0 0 {_number(page.max_x_mm)} {_number(page.max_y_mm)}"})
    ET.SubElement(root, "metadata").text = json.dumps({"method": METHOD_VERSION, "h3_validation_required": True,
                                                       "text_annotations": evidence["annotations"]}, ensure_ascii=False, sort_keys=True)
    for obj in document.objects:
        ET.SubElement(root, "path", {"id": obj.object_id, "d": obj.path_data_mm, "fill": obj.work_color,
                                    "fill-rule": "evenodd", "stroke": "none"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
