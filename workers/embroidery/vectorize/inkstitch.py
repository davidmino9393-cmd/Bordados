"""Serialize caller-validated H3 fill settings without changing E1 geometry."""
import json
import xml.etree.ElementTree as ET

from embroidery_contracts import EmbroideryDocument, Issue, IssueCode
from embroidery_contracts.issues import ISSUE_RULES

from .types import VectorizeFailure, VectorizeResult

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
INKSTITCH_NAMESPACE = "http://inkstitch.org/namespace"
SCHEMA_VERSION = "3"
GEOMETRY_EXCLUSIONS = {"effective_technique", "parameters", "satin"}


def _reject(code, description, objects=()):
    rule = ISSUE_RULES[code]
    raise VectorizeFailure(Issue(
        code=code, severity=rule.severity, stage=rule.stage,
        description=description, object_ids=tuple(objects),
        evidence={"adapter": "e1-fill-v1", "h3_validation_required": True},
        suggested_correction="Validar explícitamente en H3 la técnica y los parámetros físicos.",
    ))


def _same_geometry(original, reviewed):
    exclusions = {"objects", "decisions"}
    if original.model_dump(exclude=exclusions) != reviewed.model_dump(exclude=exclusions):
        return False
    if len(original.objects) != len(reviewed.objects):
        return False
    return all(
        before.model_dump(exclude=GEOMETRY_EXCLUSIONS)
        == after.model_dump(exclude=GEOMETRY_EXCLUSIONS)
        for before, after in zip(original.objects, reviewed.objects)
    )


def _fill_attributes(obj):
    params = obj.parameters
    if obj.effective_technique == "satin":
        _reject(IssueCode.SATIN_RAILS_UNVERIFIED,
                "E1 no convierte máscaras de relleno en columnas de satén.", (obj.object_id,))
    if obj.effective_technique != "fill":
        _reject(IssueCode.GEOMETRY_REPAIR_AMBIGUOUS,
                "El adaptador E1 solo implementa rellenos; no deduce ejes centrales.", (obj.object_id,))
    if (params.spacing_mm is None or params.direction_deg is None
            or params.underlay not in {"none", "fill"}
            or params.pull_compensation_mm != 0
            or (params.underlay == "fill" and params.underlay_spacing_mm is None)):
        _reject(IssueCode.DENSITY_REVIEW_REQUIRED,
                "Los parámetros H3 son incompletos o requieren una conversión todavía no implementada.",
                (obj.object_id,))
    attributes = {
        "inkstitch:auto_fill": "true",
        "inkstitch:angle": str(params.direction_deg),
        "inkstitch:row_spacing_mm": str(params.spacing_mm),
        "inkstitch:max_stitch_length_mm": str(params.stitch_length_mm),
        "inkstitch:running_stitch_length_mm": str(params.stitch_length_mm),
        "inkstitch:fill_underlay": str(params.underlay == "fill").lower(),
    }
    if params.underlay == "fill":
        attributes["inkstitch:fill_underlay_row_spacing_mm"] = str(params.underlay_spacing_mm)
    return attributes


def _svg_root(document):
    bounds = document.page_bounds_mm
    width = bounds.max_x_mm - bounds.min_x_mm
    height = bounds.max_y_mm - bounds.min_y_mm
    return ET.Element("svg", {
        "xmlns": SVG_NAMESPACE, "xmlns:inkstitch": INKSTITCH_NAMESPACE,
        "width": f"{width}mm", "height": f"{height}mm",
        "viewBox": f"{bounds.min_x_mm} {bounds.min_y_mm} {width} {height}",
    })


def _metadata(root, result):
    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "inkstitch:inkstitch_svg_version").text = SCHEMA_VERSION
    ET.SubElement(metadata, "desc").text = json.dumps({
        "adapter": "e1-fill-v1", "h3_document_supplied_by_caller": True,
        "digital_readiness_evaluated": False, "physical_approval": "untested",
        "source_issues": [issue.model_dump(mode="json") for issue in result.issues],
    }, ensure_ascii=False, sort_keys=True)


def to_inkstitch_svg(result: VectorizeResult, *, h3_document: EmbroideryDocument | None = None) -> bytes:
    """H3 document is a caller attestation, never digital/physical approval.

    No CLI is called. The caller must validate the supplied parameters against
    its machine/fabric profile; merely round-tripping E1 defaults is not H3.
    """
    if h3_document is None:
        _reject(IssueCode.DENSITY_REVIEW_REQUIRED,
                "Los parámetros provisionales de E1 no habilitan exportación de puntadas.",
                (obj.object_id for obj in result.document.objects))
    if not _same_geometry(result.document, h3_document):
        _reject(IssueCode.GEOMETRY_INVALID,
                "H3 debe conservar la identidad, el orden y la geometría medida de E1.")
    root = _svg_root(h3_document)
    _metadata(root, result)
    for obj in h3_document.objects:
        ET.SubElement(root, "path", {
            "id": obj.object_id, "d": obj.path_data_mm,
            "fill": obj.work_color, "fill-rule": "evenodd", "stroke": "none",
            **_fill_attributes(obj),
        })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
