"""Serialize caller-validated H3 fill settings without changing E1 geometry."""
import json
import xml.etree.ElementTree as ET

from embroidery_contracts import EmbroideryDocument, Issue, IssueCode
from embroidery_contracts.issues import ISSUE_RULES

from . import stitchable
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


# Perfil de referencia: parámetros del bordado de Anime Socks que David confirmó que «salió muy bien» (gabardina,
# estabilizador grueso, hilo de bordar, aguja de fábrica de la Janome MC 550E, 400 ppm). No es una calibración: vale
# para esas condiciones y cada trabajo lo avisa (tests/calibration/h3/REFERENCIAS_JANOME_MC550E.md).
REFERENCE_PROFILE_ID = "anime_socks_gabardina_400ppm"
REFERENCE_ADAPTER = "e1-reference-fill-v1"
REFERENCE_ROW_SPACING_MM = 0.45  # entre los 0,40 mm de la referencia publicada y los 0,45-0,50 mm de los rellenos chicos de Anime Socks
REFERENCE_MAX_STITCH_LENGTH_MM = 2.5
REFERENCE_PULL_COMPENSATION_MM = 0.2
REFERENCE_ANGLES_DEG = (45, 135, 0, 90)  # ángulos alternados por objeto: filas paralelas entre colores vecinos se notan más
REFERENCE_NOTICE = (
    "Los parámetros de puntada son los de referencia de Anime Socks (gabardina, estabilizador grueso, 400 ppm), "
    "no una calibración para esta tela."
)
REMOVED_NOTICE = (
    f"Se quitó del bordado lo que ninguna aguja puede formar: capas casi blancas, que se toman como fondo, y manchas de "
    f"menos de {stitchable.MIN_STITCHABLE_AREA_MM2:g} mm²."
)
REMOVED_CORRECTION = (
    "Comparar el bordado con la imagen original. Si una capa casi blanca es parte del diseño, o hace falta un detalle "
    "más chico, usar otra imagen o un tamaño mayor."
)
REFERENCE_CORRECTION = (
    "Coser una prueba en un retazo de la misma tela y estabilizador a 400 ppm antes de bordar; si el relleno se ve ralo "
    "o fruncido, ajustar la separación y crear otra revisión."
)


def reference_parameters():
    return {
        "profile_id": REFERENCE_PROFILE_ID, "row_spacing_mm": REFERENCE_ROW_SPACING_MM,
        "max_stitch_length_mm": REFERENCE_MAX_STITCH_LENGTH_MM, "pull_compensation_mm": REFERENCE_PULL_COMPENSATION_MM,
        "underlay": "none", "angles_deg": list(REFERENCE_ANGLES_DEG), "calibrated": False,
    }


def _reference_attributes(index):
    return {
        "inkstitch:row_spacing_mm": str(REFERENCE_ROW_SPACING_MM),
        "inkstitch:angle": str(REFERENCE_ANGLES_DEG[index % len(REFERENCE_ANGLES_DEG)]),
        "inkstitch:max_stitch_length_mm": str(REFERENCE_MAX_STITCH_LENGTH_MM),
        "inkstitch:fill_underlay": "False",
        "inkstitch:pull_compensation_mm": str(REFERENCE_PULL_COMPENSATION_MM),
        "inkstitch:trim_after": "True",
    }


def to_reference_inkstitch_svg(result: VectorizeResult) -> bytes:
    """SVG de Ink/Stitch con rellenos de parámetros de referencia; la geometría y la identidad de E1 no cambian.

    A diferencia de `to_inkstitch_svg` no hay atestación H3: los valores vienen del perfil de referencia y el resultado
    sigue sin aprobación física (`physical_approval: untested`). No llama a ninguna CLI.
    """
    document = result.document
    planned = stitchable.plan(document)
    kept = [(obj, item) for obj, item in zip(document.objects, planned) if item.path_data_mm is not None]
    if not kept:
        _reject(IssueCode.GEOMETRY_INVALID, "No queda geometría que se pueda bordar: todo es casi blanco o más chico que la mínima.",
                (obj.object_id for obj in document.objects))
    root = _svg_root(document)
    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "inkstitch:inkstitch_svg_version").text = SCHEMA_VERSION
    ET.SubElement(metadata, "desc").text = json.dumps({
        "adapter": REFERENCE_ADAPTER, "parameters": reference_parameters(), "digital_readiness_evaluated": False,
        "physical_approval": "untested", "stitchable": stitchable.evidence(planned),
        "source_issues": [issue.model_dump(mode="json") for issue in result.issues],
    }, ensure_ascii=False, sort_keys=True)
    for index, (obj, item) in enumerate(kept):
        ET.SubElement(root, "path", {
            "id": obj.object_id, "d": item.path_data_mm,
            "style": f"fill:{obj.work_color};fill-rule:evenodd;stroke:none",
            **_reference_attributes(index),
        })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def reference_issues(result: VectorizeResult):
    """Incidencias de E1 para el bordado de referencia.

    El aviso de parámetros se reescribe (ya no son valores provisionales, son de referencia) y, si se quitó geometría que
    no se puede bordar, se agrega un aviso localizado en los objetos afectados.
    """
    planned = stitchable.plan(result.document)
    rewritten = []
    for issue in result.issues:
        if issue.code == IssueCode.DENSITY_REVIEW_REQUIRED:
            issue = issue.model_copy(update={
                "description": REFERENCE_NOTICE, "suggested_correction": REFERENCE_CORRECTION,
                "evidence": {**issue.evidence, "parameter_source": REFERENCE_PROFILE_ID, "parameters_calibrated": False,
                             "reference_parameters": reference_parameters()},
            })
        rewritten.append(issue)
    changed = tuple(item.object_id for item in planned if item.changed)
    if changed:
        rule = ISSUE_RULES[IssueCode.VISUAL_MISMATCH]
        rewritten.append(Issue(
            code=IssueCode.VISUAL_MISMATCH, severity=rule.severity, stage=rule.stage, object_ids=changed,
            description=REMOVED_NOTICE, evidence={"stitchable": stitchable.evidence(planned)},
            suggested_correction=REMOVED_CORRECTION,
        ))
    return tuple(rewritten)
