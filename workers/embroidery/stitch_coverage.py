"""Spatial review of E1 colour masks against the same colour block reread from JEF."""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw

from vectorize import local_columns
from vectorize.reference_geometry import _components, _mask, _thin

SVG = "{http://www.w3.org/2000/svg}"
GRID_MM = 0.15
THREAD_DISTANCE_MM = 0.45
MIN_MISSING_AREA_MM2 = 0.30
MIN_GAP_MM = 1.0
MAX_REGISTRATION_ERROR_MM = 0.6
SEARCH_CELL_MM = 4.0
MIN_TRANSVERSE_SHARE = 0.60
MAX_DIRECTION_ERROR = math.cos(math.radians(35))
MAX_ROW_DISTANCE_MM = 0.55
MAX_CANVAS_MM = 500


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _bounds(points):
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _registered_groups(native, editable, block_count):
    """Only native E1 groups preserve a verified ordinal block and source mask ID."""
    groups = [g for g in native if g.get("id", "").startswith("native_color_")]
    if len(groups) != block_count or native.get("transform") or editable.get("transform"):
        return []
    paths = {p.get("id"): p for p in editable.findall(SVG + "path") if p.get("fill-rule") == "evenodd"}
    result = []
    for ordinal, group in enumerate(groups):
        if group.get("id") != f"native_color_{ordinal}":
            return []
        units = [node for node in group.iter() if node.get("data-source-object-id")]
        ids = {node.get("data-source-object-id") for node in units}
        if len(ids) != 1 or not ids.issubset(paths):
            return []
        mask = paths[ids.pop()]
        if mask.get("transform"):
            return []
        satin = {n.get("data-source-ring-index") for n in units if n.get("data-technique") == "satin"}
        result.append((mask, satin))
    return result


def _segment_blocks(events, origin):
    blocks = [[]]
    previous = origin
    for command, x, y in events:
        point = (x / 10 + origin[0], y / 10 + origin[1])
        if command == "stitch" and previous != point:
            blocks[-1].append((previous, point))
        elif command == "color_change":
            blocks.append([])
        previous = point
    return blocks


def _coverage(segments, size):
    ink = Image.new("L", size)
    draw = ImageDraw.Draw(ink)
    near = defaultdict(list)
    for start, end in segments:
        draw.line([tuple(round(v / GRID_MM - .5) for v in p) for p in (start, end)],
                  fill=255, width=2 * round(THREAD_DISTANCE_MM / GRID_MM) + 1)
        x0, y0, x1, y1 = _bounds((start, end))
        for x in range(math.floor((x0 - MAX_ROW_DISTANCE_MM) / SEARCH_CELL_MM),
                       math.floor((x1 + MAX_ROW_DISTANCE_MM) / SEARCH_CELL_MM) + 1):
            for y in range(math.floor((y0 - MAX_ROW_DISTANCE_MM) / SEARCH_CELL_MM),
                           math.floor((y1 + MAX_ROW_DISTANCE_MM) / SEARCH_CELL_MM) + 1):
                near[x, y].append((start, end))
    return ink, near


def _crossed(station, geometry, nearby):
    a, b = (geometry.mm(station[side]) for side in ("edge_left", "edge_right"))
    width = math.dist(a, b)
    nx, ny = (b[0] - a[0]) / width, (b[1] - a[1]) / width
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    for start, end in nearby[math.floor(cx / SEARCH_CELL_MM), math.floor(cy / SEARCH_CELL_MM)]:
        dx, dy = end[0] - start[0], end[1] - start[1]
        along = dx * nx + dy * ny
        if abs(along) < MAX_DIRECTION_ERROR * math.hypot(dx, dy):
            continue
        first = (start[0] - cx) * nx + (start[1] - cy) * ny
        low, high = sorted((first, first + along))
        if low > -MIN_TRANSVERSE_SHARE * width / 2 or high < MIN_TRANSVERSE_SHARE * width / 2:
            continue
        fraction = -first / along
        across = -(start[0] + fraction * dx - cx) * ny + (start[1] + fraction * dy - cy) * nx
        if abs(across) <= MAX_ROW_DISTANCE_MM:
            return True
    return False


def _satin_gaps(mask, origin, nearby):
    geometry = local_columns.Mask(mask, origin, GRID_MM)
    missed = tested = 0
    gaps = []
    for chain in local_columns.chains(_thin(mask, None)):
        run = []
        stations = local_columns.sections(local_columns._smooth(chain, geometry), geometry)
        for station in [*stations, None]:
            if station and station["technique"] == "satin":
                tested += 1
                if not _crossed(station, geometry, nearby):
                    missed += 1
                    run.append(geometry.mm(station["center"]))
                    continue
            if run:
                length = sum(math.dist(p, q) for p, q in zip(run, run[1:]))
                if length >= MIN_GAP_MM:
                    gaps.append({"length_mm": round(length, 2), "bounds_mm": _rounded_bounds(run)})
                run = []
    return tested, missed, gaps


def _rounded_bounds(points):
    return [round(v, 3) for v in _bounds(points)]


def _component(mask, origin, ink, nearby, expected_satin):
    left, top = origin
    crop = ink.crop((left, top, left + mask.width, top + mask.height))
    missing = ImageChops.subtract(mask, crop)
    area = missing.histogram()[255] * GRID_MM ** 2
    box = missing.getbbox()
    row = {}
    if box and area >= MIN_MISSING_AREA_MM2 and max(box[2]-box[0], box[3]-box[1]) * GRID_MM >= MIN_GAP_MM:
        row.update(missing_area_mm2=round(area, 3), source_area_mm2=round(mask.histogram()[255] * GRID_MM ** 2, 3),
                   missing_bounds_mm=[round((v + origin[i % 2]) * GRID_MM, 3) for i, v in enumerate(box)])
    if expected_satin:
        tested, missed, gaps = _satin_gaps(mask, origin, nearby)
        if gaps:
            row.update(satin_stations=tested, stations_without_crossing=missed, transverse_gaps=gaps)
    return row


def inspect(directory, editable_svg, result):
    """Return localized review candidates, never OCR, physical coverage, or stitch-type identification."""
    if not editable_svg:
        return []
    directory = Path(directory)
    native_data = (directory / "input.svg").read_bytes()
    native = ET.fromstring(native_data)
    if not any(g.get("id", "").startswith("native_color_") for g in native):
        return []
    editable_data = Path(editable_svg).read_bytes()
    editable = ET.fromstring(editable_data)
    metadata = editable.findtext(SVG + "metadata") or "{}"
    if not json.loads(metadata).get("method", "").startswith("e1-pixel-mask"):
        return []
    metrics = result["metrics"]
    groups = _registered_groups(native, editable, metrics["thread_blocks"])
    if not groups:
        return []
    events_data = (directory / "raw-commands.json").read_bytes().rstrip(b"\r\n")
    geom_hash, jef_hash = _hash(native_data), _hash((directory / "output.jef").read_bytes())
    if (geom_hash != result["input_sha256"] or jef_hash != metrics["jef_sha256"]
            or _hash(events_data) != metrics["normalized_commands_sha256"]):
        return []
    view = tuple(map(float, editable.get("viewBox").split()))
    if (view != tuple(map(float, native.get("viewBox").split())) or view[:2] != (0, 0)
            or not all(0 < v <= MAX_CANVAS_MM for v in view[2:])
            or any(editable.get(key) != native.get(key) or not native.get(key, "").endswith("mm")
                   or not math.isclose(float(native.get(key)[:-2]), view[i])
                   for key, i in (("width", 2), ("height", 3)))):
        return []
    objects = [(_components(path.get("d")), path.get("id"), satins) for path, satins in groups]
    bounds = _bounds(p for rings, _, _ in objects for _, ring, _ in rings for p in ring)
    jef = metrics["stitch_bounds_mm"]
    if any(abs((bounds[i+2] - bounds[i]) - (jef[i+2] - jef[i])) > MAX_REGISTRATION_ERROR_MM for i in (0, 1)):
        return []
    origin = tuple((bounds[i] + bounds[i+2] - jef[i] - jef[i+2]) / 2 for i in (0, 1))
    blocks = _segment_blocks(json.loads(events_data), origin)
    if len(blocks) != len(objects):
        return []
    size = tuple(math.ceil(v / GRID_MM) + 1 for v in view[2:])
    findings = []
    for block, (rings, object_id, satins) in zip(blocks, objects):
        ink, nearby = _coverage(block, size)
        for index, ring, holes in rings:
            mask, offset = _mask([ring, *holes], GRID_MM, None)
            row = _component(mask, tuple(map(int, offset)), ink, nearby, str(index) in satins)
            if row:
                row.update(object_id=object_id, ring_index=index, bounds_mm=_rounded_bounds(ring))
                findings.append(row)
    return findings

