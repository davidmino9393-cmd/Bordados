"""Route generated guide columns with Ink/Stitch's own satin underpath planner."""
import hashlib
import json
import math
from pathlib import Path
import re
from time import monotonic
import xml.etree.ElementTree as ET

from process_runner import WorkerFailure, run_logged

SVG = "http://www.w3.org/2000/svg"
IS = "http://inkstitch.org/namespace"
INK = "http://www.inkscape.org/namespaces/inkscape"
XLINK = "http://www.w3.org/1999/xlink"
NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")
for prefix, namespace in (("", SVG), ("inkstitch", IS), ("inkscape", INK), ("xlink", XLINK)):
    ET.register_namespace(prefix, namespace)


def requested(source):
    root = ET.parse(source).getroot()
    description = root.find(".//{" + SVG + "}desc")
    if description is None:
        return False
    try:
        metadata = json.loads(description.text or "{}")
    except ValueError:
        return False
    return metadata.get("routing", {}).get("native_auto_route") is True


def _groups(root):
    paths = [node for node in root if node.get("data-technique") in {"satin", "running", "fill"}]
    selected_ids = {node.get("id") for node in paths}
    # These are generated endpoint commands, replaced by native auto-routing.
    for group in list(root):
        if group.get("data-technique") in {"hidden_running_connector", "connector"}:
            root.remove(group)
            continue
        if group.get("data-native-command") == "keep":
            continue
        if group.tag == "{" + SVG + "}g" and any(
                node.get("{" + INK + "}connection-end", "").lstrip("#") in selected_ids for node in group.iter()):
            root.remove(group)
    colors = {}
    for node in paths:
        root.remove(node)
        style = dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)
        color = style.get("fill") if node.get("data-technique") == "fill" else style.get("stroke")
        colors.setdefault(color, {}).setdefault(node.get("data-component", ""), []).append(node)
    groups, cursor, number = [], (0., 0.), 0
    for index, components in enumerate(colors.values()):
        color_group = ET.SubElement(root, "{" + SVG + "}g", {"id": f"native_color_{index}"})
        for nodes, cursor in _component_order(components, cursor):
            route = _component_group(color_group, nodes, number)
            number += 1
            if route:
                groups.append(route)
    return groups


def _numbers(node):
    values = [float(v) for v in NUMBER.findall(node.get("d", ""))]
    return list(zip(values[::2], values[1::2]))


def _component_order(components, cursor):
    """Nearest component first: each component is entered and finished once."""
    centres = {}
    for key, nodes in components.items():
        points = [point for node in nodes for point in _numbers(node)] or [cursor]
        centres[key] = (sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points))
    pending = sorted(components)
    while pending:
        key = min(pending, key=lambda item: (math.dist(cursor, centres[item]), item))
        pending.remove(key)
        cursor = centres[key]
        yield components[key], cursor


def _component_group(parent, nodes, number):
    """Fills, then strokes routed natively; the only cut is at the component exit."""
    for node in nodes:
        node.attrib.pop("{" + IS + "}trim_after", None)
        # Adapter-verified fill exits: unproven gaps are cut, verified ones are not.
        if node.get("data-fill-exit") == "trim":
            node.set("{" + IS + "}trim_after", "true")
    fills = sorted((node for node in nodes if node.get("data-technique") == "fill"),
                   key=lambda node: int(node.get("data-fill-order", "0")))
    strokes = [node for node in nodes if node.get("data-technique") != "fill"]
    # Native output may be appended to its parent: keep it inside this component.
    component = ET.SubElement(parent, "{" + SVG + "}g", {"id": f"native_component_{number}"})
    for node in fills:
        component.append(node)
    route_id = f"native_route_{number}"
    group = ET.SubElement(component, "{" + SVG + "}g", {"id": route_id})
    for node in strokes:
        group.append(node)
    if any(node.get("data-technique") == "satin" for node in strokes):
        return route_id, "auto_satin"
    if len(strokes) > 1:
        return route_id, "auto_run"
    # One running path or fills only: no native route adds a cut at the exit.
    (strokes or fills)[-1].set("{" + IS + "}trim_after", "true")
    return None


def route(source, executable, directory, timeout):
    directory = Path(directory)
    original = source.read_bytes()
    (directory / "reference-before-routing.svg").write_bytes(original)
    root = ET.fromstring(original)
    groups = _groups(root)
    prepared = directory / "routing-input.svg"
    prepared.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    started, records = monotonic(), []
    for index, (group_id, extension) in enumerate(groups):
        remaining = timeout - (monotonic() - started)
        if remaining <= 0:
            raise WorkerFailure("WORKER_TIMEOUT", "native_routing_deadline_exceeded", {"timeout_s": timeout})
        options = (["--keep_originals=false"] if extension == "auto_satin" else ["--break_up=false"])
        payload, record = run_logged([str(executable), "--extension=" + extension, "--id=" + group_id,
                                      "--preserve_order=false", *options, "--trim=true",
                                      str(prepared.resolve())], directory, f"route-{index}", remaining)
        records.append(record)
        prepared.write_bytes(payload)
    root = ET.parse(prepared).getroot()
    from native_satin_cleanup import cleanup
    satin_cleanup = cleanup(root)
    _normalize_underpaths(root)
    exit_trims = _ensure_exit_trims(root)
    source.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    return records, {"method": "Ink/Stitch auto_satin/auto_run per dilated mask component; native hidden underpaths; "
                               "cut only between components",
                     "components_routed": len(groups),
                     "extensions": {name: sum(e == name for _, e in groups) for name in ("auto_satin", "auto_run")},
                     "satin_cleanup": satin_cleanup, "component_exit_trims_added": exit_trims,
                     "source_svg_sha256": hashlib.sha256(original).hexdigest(),
                     "routed_svg_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def _ensure_exit_trims(root):
    """Leaving a component crosses blank fabric: its last stitched path must cut."""
    trimmed = {node.get("{" + INK + "}connection-end", "").lstrip("#")
               for group in root.iter("{" + SVG + "}g")
               if any(use.get("{" + XLINK + "}href") == "#inkstitch_trim" for use in group.findall("{" + SVG + "}use"))
               for node in group.findall("{" + SVG + "}path") if node.get("{" + INK + "}connection-end")}
    added = 0
    for component in root.iter("{" + SVG + "}g"):
        if not component.get("id", "").startswith("native_component_"):
            continue
        stitched = [node for node in component.iter("{" + SVG + "}path")
                    if not node.get("{" + INK + "}connection-start")]
        if stitched and stitched[-1].get("id") not in trimmed and \
                stitched[-1].get("{" + IS + "}trim_after", "").lower() != "true":
            stitched[-1].set("{" + IS + "}trim_after", "true")
            added += 1
    return added


def _normalize_underpaths(root):
    for node in root.iter("{" + SVG + "}path"):
        if node.get("{" + INK + "}connection-start") or node.get("{" + IS + "}satin_column", "").lower() == "true":
            continue
        style = node.get("style", "")
        if "stroke-dasharray" in style:
            node.set("data-technique", "connector")
            node.set("{" + IS + "}stroke_method", "running_stitch")
            if not node.get("{" + IS + "}running_stitch_length_mm"):
                node.set("{" + IS + "}running_stitch_length_mm", "2.5")
