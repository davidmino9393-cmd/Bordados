"""Serialize caller-validated H3 fill settings without changing E1 geometry."""
import json
import math
import xml.etree.ElementTree as ET

from embroidery_contracts import EmbroideryDocument, Issue, IssueCode
from embroidery_contracts.issues import ISSUE_RULES

from . import stitchable
from . import reference_geometry
from . import piece_bridges
from .native_commands import add_command, add_endpoint_commands
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


# Preserve the existing reference profile identifier for API compatibility.
# Recipes now follow the supplied Ink/Stitch guide; neither source nor the
# gabardina working conditions constitute physical calibration.
REFERENCE_PROFILE_ID = "gabardina_400ppm_referencia"
REFERENCE_ADAPTER = "e1-reference-local-width-v2"
REFERENCE_ROW_SPACING_MM = 0.35
REFERENCE_MAX_STITCH_LENGTH_MM = 5.0
REFERENCE_PULL_COMPENSATION_MM = 0.25
# Ink/Stitch reparte el corrido con una tolerancia de 0,2 mm por defecto y corta las esquinas de las letras chicas (El Fortín:
# la L salía «(», la esquina quedaba a ~0,5 mm del vértice). Con 0,05 mm cae una puntada en cada esquina.
REFERENCE_RUNNING_TOLERANCE_MM = 0.05
# Puntada más corta que Ink/Stitch deja en corrido, satén y relleno (las fuentes de Ink/Stitch usan 0,2-0,3 mm). Las más
# cortas suman pinchazos sin cubrir y pueden cortar el hilo; El Fortín tenía el 6,7 % por debajo de 0,3 mm.
REFERENCE_MIN_STITCH_MM = 0.3
REFERENCE_ANGLES_DEG = (45, 135, 0, 90)  # ángulos alternados por objeto: filas paralelas entre colores vecinos se notan más
REFERENCE_NOTICE = (
    "Los parámetros siguen la guía de digitalización de Ink/Stitch y las técnicas se derivan del ancho local; "
    "son una referencia sin calibración ni aprobación física para esta tela."
)
ADJUSTED_NOTICE = (
    f"Se ajustó la geometría para poder bordarla: se quitó lo que ninguna aguja puede formar (capas casi blancas, que se "
    f"toman como fondo, y manchas de menos de {stitchable.MIN_STITCHABLE_AREA_MM2:g} mm²) y se simplificaron los contornos "
    f"dentro de la tolerancia indicada."
)
ADJUSTED_CORRECTION = (
    "Comparar el bordado con la imagen original. Si una capa casi blanca es parte del diseño, o hace falta un detalle "
    "más chico, usar otra imagen o un tamaño mayor."
)
REFERENCE_CORRECTION = (
    "Coser una prueba en un retazo de la misma tela y estabilizador a 400 ppm antes de bordar; si el relleno se ve ralo "
    "o fruncido, ajustar la separación y crear otra revisión."
)


def reference_parameters():
    return {
        "profile_id": REFERENCE_PROFILE_ID, "parameter_source": "GUIA_BORDADO_INKSTITCH", "row_spacing_mm": REFERENCE_ROW_SPACING_MM,
        "max_stitch_length_mm": REFERENCE_MAX_STITCH_LENGTH_MM, "pull_compensation_mm": REFERENCE_PULL_COMPENSATION_MM,
        "underlay": "guide_per_technique_micro_disables_all", "angles_deg": list(REFERENCE_ANGLES_DEG), "calibrated": False,
        "pull_compensation_policy": "running=0; stable=.25mm; elastic=.35mm",
        "technique_width_mm": {"running_below": 1, "satin_from": 1, "satin_through": 4, "tatami_from": 7},
        "satin": {"zigzag_spacing_mm": .4, "short_stitch_inset": .15, "max_stitch_length_mm": 7},
        "micro": {"height_below_mm": 5, "width_below_mm": 1.5, "spacing_mm": .55, "all_underlays": False},
        "fill_underlay": {"row_spacing_mm": 5, "inset_mm": 1.5, "max_stitch_length_mm": 5, "angle": "perpendicular"},
        "satin_limitation": reference_geometry.SATIN_LIMITATION,
    }


def _reference_attributes(index, spacing=REFERENCE_ROW_SPACING_MM, compensation=REFERENCE_PULL_COMPENSATION_MM, micro=False):
    angle = REFERENCE_ANGLES_DEG[index % len(REFERENCE_ANGLES_DEG)]
    return {
        "inkstitch:auto_fill": "true", "inkstitch:row_spacing_mm": str(spacing),
        "inkstitch:angle": str(angle), "inkstitch:max_stitch_length_mm": "5.0",
        "inkstitch:fill_underlay": str(not micro).lower(),
        "inkstitch:fill_underlay_row_spacing_mm": "5.0", "inkstitch:fill_underlay_inset_mm": "1.5",
        "inkstitch:fill_underlay_max_stitch_length_mm": "5.0",
        "inkstitch:fill_underlay_angle": str((angle + 90) % 180),
        "inkstitch:pull_compensation_mm": str(compensation),
        "inkstitch:min_stitch_length_mm": str(REFERENCE_MIN_STITCH_MM),
    }


def _unit_attributes(index, unit):
    micro = unit.get("micro", False)
    technique = unit["technique"]
    if technique == "running":
        return {"inkstitch:stroke_method": "running_stitch",
                "inkstitch:running_stitch_length_mm": str(unit.get("running_stitch_length_mm", 2.5)),
                "inkstitch:running_stitch_tolerance_mm": str(REFERENCE_RUNNING_TOLERANCE_MM),
                "inkstitch:min_stitch_length_mm": str(REFERENCE_MIN_STITCH_MM)}
    if technique == "satin":
        return {"inkstitch:satin_column": "true", "inkstitch:zigzag_spacing_mm": str(.55 if micro else .4),
                "inkstitch:short_stitch_inset": "0.15", "inkstitch:max_stitch_length_mm": "7.0",
                "inkstitch:start_at_nearest_point": "false", "inkstitch:end_at_nearest_point": "false",
                # Guía 6.3: en microtexto el refuerzo depende de la tela; en telas elásticas o blandas se conserva la pasada central.
                "inkstitch:center_walk_underlay": str(not micro or unit["pull_compensation_mm"] > REFERENCE_PULL_COMPENSATION_MM).lower(),
                "inkstitch:contour_underlay": "false", "inkstitch:zigzag_underlay": "false",
                "inkstitch:fill_underlay": "false",
                "inkstitch:pull_compensation_mm": str(unit["pull_compensation_mm"]),
                "inkstitch:min_stitch_length_mm": str(REFERENCE_MIN_STITCH_MM)}
    return _reference_attributes(index, unit["row_spacing_mm"], unit["pull_compensation_mm"], micro)


def _nearest_route(document, rings_by_object):
    """Deterministic nearest-entry routing within each original thread colour."""
    colors = {}
    for obj in document.objects:
        colors.setdefault(obj.work_color, []).extend((obj, unit, i) for i, unit in enumerate(rings_by_object[obj.object_id])
                                                   if not unit["omitted"])
    routed = []
    cursor = (0., 0.)
    for units in colors.values():
        pending = list(units)
        reverse = {id(entry[1]): _reversed_entry(entry) for entry in units}
        while pending:
            candidates = []
            for i, entry in enumerate(pending):
                for candidate in (entry, reverse[id(entry[1])]):
                    candidates.append((math.dist(cursor, candidate[1].get("entry_mm", cursor)), i, candidate))
            candidates.sort(key=lambda item: (item[0], item[2][0].object_id, item[2][2]))
            chosen = candidates[0]
            if routed and routed[-1][0].work_color == units[0][0].work_color:
                for candidate in candidates[:20]:
                    if _satin_bridge(routed[-1], candidate[2]) or _hidden_connector(routed[-1], candidate[2]):
                        chosen = candidate
                        break
            _, selected, entry = chosen
            pending.pop(selected)
            routed.append(entry)
            cursor = entry[1].get("exit_mm", cursor)
    return routed


def _reversed_entry(entry):
    obj, unit, index = entry
    if unit["technique"] == "fill":
        return entry
    reversed_unit = {**unit, "entry_mm": unit["exit_mm"], "exit_mm": unit["entry_mm"]}
    if unit["technique"] == "running":
        reversed_unit["stitch_path_mm"] = reference_geometry.local_columns.path(list(reversed(stitchable._points(unit["stitch_path_mm"]))))
    else:
        rails = unit["satin"]
        left, right = list(reversed(rails["left_rail_mm"])), list(reversed(rails["right_rail_mm"]))
        satin = {**rails, "left_rail_mm": left, "right_rail_mm": right,
                 "centerline_mm": list(reversed(rails.get("centerline_mm", []))),
                 "paired_rail_stations_mm": list(reversed(rails.get("paired_rail_stations_mm", []))),
                 "path": " ".join(reference_geometry.local_columns.path(points) for points in [left, right, *rails["guides_mm"]])}
        reversed_unit.update(satin=satin, stitch_path_mm=satin["path"])
    return obj, reversed_unit, index


def _hidden_connector(previous, following):
    """A connector is allowed only when a future satin covers its entire line.

    Fill exits and satin exits are selected by Ink/Stitch; without explicit
    measured exit coordinates we cannot safely claim a hidden connector there.
    Running endpoints are deterministic, so only those can initiate one.
    """
    before_obj, before, _ = previous
    after_obj, after, _ = following
    if before_obj.work_color != after_obj.work_color or before["technique"] != "running" or after["technique"] != "satin":
        return None
    rails = after["satin"]
    centers = rails.get("centerline_mm") or [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                                           for a, b in zip(rails["left_rail_mm"], rails["right_rail_mm"])]
    distance, target = 0., None
    for a, b in zip(centers, centers[1:]):
        span = math.dist(a, b)
        if distance + span >= 1.5:
            fraction = (1.5 - distance) / span
            target = (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
            break
        distance += span
    if target is None:
        return None
    start = before["exit_mm"]
    length = math.dist(start, target)
    if length > 12:
        return None
    polygon = rails["left_rail_mm"] + list(reversed(rails["right_rail_mm"]))
    if not all(reference_geometry._inside(point, polygon) for point in (start, target)):
        return None
    if any(stitchable.segments_intersect(start, target, a, b)
           for a, b in zip(polygon, polygon[1:] + polygon[:1])):
        return None
    return {"kind": "explicit_hidden_running_connector", "entry_mm": target,
            "path": reference_geometry.local_columns.path([start, target]), "length_mm": length,
            "penetration_mm": 1.5, "covering_object_id": after_obj.object_id,
            "coverage_proof": "both_endpoints_inside_simple_future_satin_polygon_and_no_boundary_intersections"}


def _satin_bridge(previous, following):
    """Force a short native end-run underneath the next satin's rail polygon."""
    before_obj, before, _ = previous
    after_obj, after, _ = following
    if before_obj.work_color != after_obj.work_color or before["technique"] != after["technique"] or before["technique"] != "satin":
        return None
    rails = after["satin"]
    centers = rails.get("centerline_mm") or [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                                           for a, b in zip(rails["left_rail_mm"], rails["right_rail_mm"])]
    remaining, target = 1.5, None
    for a, b in zip(centers, centers[1:]):
        span = math.dist(a, b)
        if span >= remaining:
            target = (a[0] + (b[0] - a[0]) * remaining / span,
                      a[1] + (b[1] - a[1]) * remaining / span)
            break
        remaining -= span
    if target is None:
        return None
    old = before["satin"]
    a, b = old["left_rail_mm"][-1], old["right_rail_mm"][-1]
    center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    span = math.dist(a, b)
    compensation = before["pull_compensation_mm"]
    dx, dy = (a[0] - b[0]) / span * compensation, (a[1] - b[1]) / span * compensation
    exits = [a, b, center, (a[0] + dx, a[1] + dy), (b[0] - dx, b[1] - dy)]
    polygons = [_satin_footprint(after)]
    if not reference_geometry._inside(target, polygons[0]):
        return None
    for point in exits:
        # >=1.5 prevents Ink/Stitch ignoring the ending command near its end;
        # <=2.5 keeps the native final running stitch at the guide length.
        if not 1.5 - 1e-6 <= math.dist(point, target) <= 2.5 + 1e-6:
            return None
        if not _segment_covered(point, target, polygons):
            return None
    return {"kind": "native_hidden_ending_path", "entry_mm": target, "exit_mm": target,
            "length_mm": max(math.dist(p, target) for p in exits), "penetration_mm": 1.5,
            "covering_object_id": after_obj.object_id,
            "coverage_proof": "exact_segment_intervals_inside_next_future_compensated_satin"}


def _satin_footprint(unit):
    rails = unit["satin"]
    stations = rails.get("paired_rail_stations_mm") or list(zip(rails["left_rail_mm"], rails["right_rail_mm"]))
    left, right = [], []
    for a, b in stations:
        distance = math.dist(a, b)
        if not distance:
            continue
        dx, dy = (a[0] - b[0]) / distance * unit["pull_compensation_mm"], (a[1] - b[1]) / distance * unit["pull_compensation_mm"]
        left.append((a[0] + dx, a[1] + dy))
        right.append((b[0] - dx, b[1] - dy))
    return reference_geometry.local_columns._dedup(left + list(reversed(right)))


def _segment_covered(a, b, polygons):
    """Exact partition at polygon crossings, including nonconvex footprints."""
    values = {0., 1.}
    dx, dy = b[0] - a[0], b[1] - a[1]
    for polygon in polygons:
        for c, d in zip(polygon, polygon[1:] + polygon[:1]):
            ex, ey = d[0] - c[0], d[1] - c[1]
            denominator = dx * ey - dy * ex
            if abs(denominator) < 1e-10:
                continue
            t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / denominator
            u = ((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                values.add(t)
    cuts = sorted(values)
    for first, last in zip(cuts, cuts[1:]):
        t = (first + last) / 2
        point = (a[0] + dx * t, a[1] + dy * t)
        if not any(reference_geometry._inside(point, polygon) for polygon in polygons):
            return False
    return True


def to_reference_inkstitch_svg(result: VectorizeResult) -> bytes:
    """Guide-based reference SVG; E1 paths remain registered and unchanged."""
    document = result.document
    planned = stitchable.plan(document)
    rings_by_object = _reference_rings(document)
    routed = _nearest_route(document, rings_by_object)
    if not routed:
        from .types import issue
        raise VectorizeFailure(issue(IssueCode.GEOMETRY_INVALID,
                                     "No queda geometría que se pueda bordar.",
                                     {"reference_rings": {key: list(value) for key, value in rings_by_object.items()}},
                                     (obj.object_id for obj in document.objects)))
    connectors = {i: _satin_bridge(current, routed[i + 1]) or _hidden_connector(current, routed[i + 1])
                  for i, current in enumerate(routed[:-1])}
    affine = document.coordinates.source_px_to_mm
    pieces = {obj.object_id: piece_bridges.plan(obj, rings_by_object[obj.object_id], abs(affine[0]),
                                                (affine[4], affine[5]), REFERENCE_PULL_COMPENSATION_MM)
              for obj in document.objects}
    root = _svg_root(document)
    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "inkstitch:inkstitch_svg_version").text = SCHEMA_VERSION
    ET.SubElement(metadata, "desc").text = json.dumps({
        "adapter": REFERENCE_ADAPTER, "parameters": reference_parameters(), "digital_readiness_evaluated": False,
        "physical_approval": "untested", "stitchable": stitchable.evidence(planned),
        "technique_selection": {object_id: [{key: value for key, value in unit.items()
                                             if key not in {"stitch_path_mm", "fill_path_mm", "satin"}}
                                            for unit in units] for object_id, units in rings_by_object.items()},
        "satin_limitation": reference_geometry.SATIN_LIMITATION,
        "routing": {"method": "nearest_neighbor_within_color", "preliminary": True, "native_auto_route": True,
                    "final_route_authority": "native_auto_satin_after_fills", "endpoint_positions": "derived_geometry_estimates",
                    "hidden_connectors": [value for value in connectors.values() if value],
                    "unsafe_or_unproven_travel": "trim", "max_hidden_connector_mm": 12,
                    "cut_policy": "native_route_per_dilated_mask_component; cut only between components",
                    "piece_bridges": {object_id: value["evidence"] for object_id, value in pieces.items()}},
        "source_issues": [issue.model_dump(mode="json") for issue in result.issues],
    }, ensure_ascii=False, sort_keys=True)
    nodes = {}
    for index, (obj, unit, unit_index) in enumerate(routed):
        technique = unit["technique"]
        stroke = technique in {"running", "satin"}
        width = unit.get("local_width_mm", .2) if technique == "satin" else .2
        attributes = _unit_attributes(index, unit)
        following = routed[index + 1] if index + 1 < len(routed) else None
        connector = connectors.get(index)
        # A shared endpoint of two running paths needs no jump or cut. Other
        # exits are engine-selected and conservatively require a cut.
        continuous = bool(following and obj.work_color == following[0].work_color and
                          technique == following[1]["technique"] == "running" and
                          math.dist(unit["exit_mm"], following[1]["entry_mm"]) < .001)
        if following and not connector and not continuous:
            attributes["inkstitch:trim_after"] = "true"
        node = ET.SubElement(root, "path", {
            "id": obj.object_id if sum(not item["omitted"] for item in rings_by_object[obj.object_id]) == 1 else f"{obj.object_id}_unit_{unit_index}",
            "d": unit["stitch_path_mm"] if stroke else unit["fill_path_mm"],
            "data-source-object-id": obj.object_id, "data-technique": technique,
            "data-source-ring-index": str(unit["ring_index"]),
            "data-component": f"{obj.object_id}:{pieces[obj.object_id]['component_of'][unit_index]}",
            "data-local-width-mm": str(unit.get("local_width_mm", 0)),
            "style": (f"fill:none;stroke:{obj.work_color};stroke-width:{width}" if stroke else
                      f"fill:{obj.work_color};fill-rule:evenodd;stroke:none"), **attributes,
        })
        nodes[(obj.object_id, unit_index)] = node
        if technique == "fill":
            node.set("data-fill-order", str(pieces[obj.object_id]["fill_order"][unit_index]))
            node.set("data-fill-exit", pieces[obj.object_id]["fill_exits"][unit_index]["kind"])
        previous_connector = connectors.get(index - 1)
        entry = previous_connector.get("entry_mm") if previous_connector and previous_connector.get("kind") else None
        exit_point = connector.get("exit_mm") if connector and connector.get("kind") else None
        if entry is not None or exit_point is not None:
            add_endpoint_commands(root, node, entry, exit_point)
        if connector and "path" in connector:
            ET.SubElement(root, "path", {"id": f"hidden_connector_{index}", "d": connector["path"],
                                        "data-technique": "hidden_running_connector",
                                        "data-covering-object-id": connector["covering_object_id"],
                                        "data-penetration-mm": "1.5", "data-length-mm": str(connector["length_mm"]),
                                        "style": f"fill:none;stroke:{obj.work_color};stroke-width:0.2",
                                        "inkstitch:stroke_method": "running_stitch",
                                        "inkstitch:running_stitch_length_mm": "2.5"})
    for obj in document.objects:
        for unit_index, exit_plan in pieces[obj.object_id]["fill_exits"].items():
            if exit_plan["kind"] == "trim":
                continue
            # The fill ends where the verified gap starts; the next fill (or the
            # native stroke route) starts across that gap, inside the mask.
            add_command(root, nodes[(obj.object_id, unit_index)], "ending_point", exit_plan["exit_mm"])
            following = nodes[(obj.object_id, exit_plan["next_unit"])]
            add_command(root, following, "starting_point" if exit_plan["kind"] == "fill_link" else "autoroute_start",
                        exit_plan["entry_mm"])
        for number, bridge in enumerate(pieces[obj.object_id]["bridges"]):
            ET.SubElement(root, "path", {
                "id": f"{obj.object_id}_bridge_{number}", "d": bridge["path"],
                "data-source-object-id": obj.object_id, "data-technique": "running",
                "data-role": "piece_bridge", "data-component": f"{obj.object_id}:{bridge['component']}",
                "data-length-mm": f"{bridge['length_mm']:.3f}",
                "style": f"fill:none;stroke:{obj.work_color};stroke-width:0.2",
                "inkstitch:stroke_method": "running_stitch",
                "inkstitch:running_stitch_length_mm": str(piece_bridges.BRIDGE_STITCH_LENGTH_MM)})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def reference_issues(result: VectorizeResult):
    """Incidencias de E1 para el bordado de referencia.

    El aviso de parámetros se reescribe (ya no son valores provisionales, son de referencia) y, si se quitó o simplificó geometría,
    se agrega un aviso localizado en los objetos afectados (con los números de lo que cambió).
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
            description=ADJUSTED_NOTICE, evidence={"stitchable": stitchable.evidence(planned)},
            suggested_correction=ADJUSTED_CORRECTION,
        ))
    rings_by_object = _reference_rings(result.document)
    for object_id, rings in rings_by_object.items():
        residual_patches = [ring for ring in rings if not ring["omitted"] and
                            ring.get("geometry_role") == "residual_junction_or_cap_patch"]
        if residual_patches:
            rule = ISSUE_RULES[IssueCode.SATIN_RAILS_UNVERIFIED]
            rewritten.append(Issue(
                code=IssueCode.SATIN_RAILS_UNVERIFIED, severity=rule.severity, stage=rule.stage,
                object_ids=(object_id,),
                description="Los parches residuales de uniones o extremos no admitieron una columna de satín verificada; se conservaron como relleno para revisión.",
                evidence={"residual_patch_count": len(residual_patches),
                          "original_ring_indices": sorted({ring["ring_index"] for ring in residual_patches}),
                          "fallback": "conservative_fill_not_a_width_rule_override"},
                suggested_correction="Revisar y digitalizar manualmente las uniones y los extremos señalados antes de aprobar el bordado.",
            ))
        omitted = [ring for ring in rings if ring["omitted"] in {
            "reference_fill_below_2mm2", "reference_object_below_2mm2", "skeleton_has_no_stitch_segments"}]
        if omitted:
            rule = ISSUE_RULES[IssueCode.VISUAL_MISMATCH]
            rewritten.append(Issue(
                code=IssueCode.VISUAL_MISMATCH, severity=rule.severity, stage=rule.stage, object_ids=(object_id,),
                description="Se omitieron anillos sin recorrido cosible o bajo el mínimo real de relleno de 2 mm².",
                evidence={"reference_omitted_rings": omitted,
                          "minimum_reference_fill_area_mm2": reference_geometry.MIN_REFERENCE_FILL_AREA_MM2},
                suggested_correction=ADJUSTED_CORRECTION,
            ))
    return tuple(rewritten)


def _reference_rings(document):
    affine = document.coordinates.source_px_to_mm
    scale = abs(affine[0])
    return {obj.object_id: obj.reference_rings or reference_geometry.measure_object(
        obj, scale, stitchable.tolerance_for(document), grid_origin=(affine[4], affine[5]))[0] for obj in document.objects}
