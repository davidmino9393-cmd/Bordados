"""Connect stroke pieces of one mask component so native routing cuts only between blocks.

Component: E1 rings whose pixel masks overlap after a box dilation equal to
the pull compensation plus JEF rounding (gaps the compensated stitches close).
Bridge: a straight running connector from a stroke end to the nearest
centre-line point of another piece, accepted only when the whole segment lies
inside that dilated component mask. Registered E1 paths are never modified.
"""
import math

from PIL import Image, ImageChops, ImageFilter, ImageOps

from . import stitchable
from .local_columns import Mask, path
from .reference_geometry import _components, _mask
from .types import check_cancel

# Ink/Stitch 3.2.2 auto_satin joined centre lines 0.2-0.7 mm apart and cut at
# 1.0 mm (tests/engine/test_piece_bridges.py documents the probe); 0.5 keeps margin.
JOIN_MM = 0.5
# Longest within-component gap of the real logo was 2.41 mm; the guide's
# hidden connector penetrates 1-2 mm. Longer travel is cut, never bridged.
MAX_BRIDGE_MM = 3.0
JEF_ROUNDING_MM = 0.05
BRIDGE_STITCH_LENGTH_MM = 2.5


def _polyline(unit):
    if unit["technique"] == "satin":
        return [tuple(point) for point in unit["satin"]["centerline_mm"]]
    if unit["technique"] == "running":
        return stitchable._points(unit["stitch_path_mm"])
    return None


class _Union:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        self.parent[a] = b
        return True


def _dilated_rings(obj, indices, scale, grid_origin, radius, cancel):
    rings = {index: (border, holes) for index, border, holes in _components(obj.path_data_mm, cancel)}
    output = {}
    for index in indices:
        check_cancel(cancel)
        image, origin = _mask([rings[index][0], *rings[index][1]], scale, cancel, grid_origin)
        grown = ImageOps.expand(image, radius, fill=0).filter(ImageFilter.MaxFilter(2 * radius + 1))
        output[index] = (grown, (origin[0] - radius, origin[1] - radius))
    return output


def _box(entry):
    image, origin = entry
    return (round(origin[0]), round(origin[1]), round(origin[0]) + image.width, round(origin[1]) + image.height)


def _overlap(a, b):
    first, second = _box(a), _box(b)
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    if left >= right or top >= bottom:
        return False
    crop = lambda entry, box: entry[0].crop((left - box[0], top - box[1], right - box[0], bottom - box[1]))
    return ImageChops.darker(crop(a, first), crop(b, second)).getbbox() is not None


def _component_masks(dilated, members):
    masks = {}
    for component, indices in members.items():
        boxes = [_box(dilated[index]) for index in indices]
        left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
        canvas = Image.new("L", (max(b[2] for b in boxes) - left, max(b[3] for b in boxes) - top), 0)
        for index, box in zip(indices, boxes):
            canvas.paste(255, (box[0] - left, box[1] - top), dilated[index][0])
        # Whole-pixel offsets keep the shared fractional grid of every ring.
        fraction = dilated[indices[0]][1]
        masks[component] = (canvas, (left + fraction[0] - round(fraction[0]), top + fraction[1] - round(fraction[1])))
    return masks


def _nearest_on(point, polyline):
    best = (math.inf, None)
    for a, b in zip(polyline, polyline[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = dx * dx + dy * dy
        t = 0. if not length else max(0., min(1., ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length))
        candidate = (a[0] + t * dx, a[1] + t * dy)
        distance = math.dist(point, candidate)
        if distance < best[0]:
            best = (distance, candidate)
    return best


def _bounds(polyline, margin):
    xs, ys = [x for x, _ in polyline], [y for _, y in polyline]
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def _apart(a, b):
    return a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


def _candidates(keys, lines, inside, cancel):
    """Endpoint-to-centre-line gaps between two units; the segment must stay inside."""
    bounds = {key: _bounds(lines[key], MAX_BRIDGE_MM) for key in keys}
    for i, first in enumerate(keys):
        check_cancel(cancel)
        for second in keys[i + 1:]:
            if _apart(bounds[first], bounds[second]):
                continue
            for start, target in ((first, second), (second, first)):
                for end in (lines[start][0], lines[start][-1]):
                    distance, point = _nearest_on(end, lines[target])
                    if distance <= MAX_BRIDGE_MM:
                        yield distance, start, target, end, point, inside(end, point)


def _rings(unit):
    return [stitchable._points(part) for part in stitchable._SUBPATH.findall(unit["fill_path_mm"] or "")]


def _gap(first, second):
    """Nearest boundary points between two fills (vertices against edges, both ways)."""
    best = (math.inf, None, None)
    for source, target, swap in ((first, second, False), (second, first, True)):
        for ring in source:
            for point in ring:
                for other in target:
                    distance, nearest = _nearest_on(point, other + other[:1])
                    if distance < best[0]:
                        best = (distance, nearest, point) if swap else (distance, point, nearest)
    return best


def _fill_plan(fills, strokes, lines, units, inside):
    """Chain fills through verified short gaps; enter the stroke route nearest the last fill."""
    rings = {i: _rings(units[i]) for i in fills}
    order, pending = [fills[0]], fills[1:]
    exits = {}
    while pending:
        gaps = {i: _gap(rings[order[-1]], rings[i]) for i in pending}
        following = min(pending, key=lambda i: (gaps[i][0], i))
        distance, exit_point, entry = gaps[following]
        verified = distance <= MAX_BRIDGE_MM and inside(exit_point, entry)
        exits[order[-1]] = {"kind": "fill_link" if verified else "trim", "next_unit": following,
                            "exit_mm": exit_point, "entry_mm": entry, "length_mm": distance}
        order.append(following)
        pending.remove(following)
    last, best = order[-1], (math.inf, None, None, None)
    for i in strokes:
        for ring in rings[last]:
            for point in ring:
                distance, nearest = _nearest_on(point, lines[i])
                if distance < best[0]:
                    best = (distance, point, nearest, i)
    distance, exit_point, entry, unit = best
    verified = unit is not None and distance <= MAX_BRIDGE_MM and inside(exit_point, entry)
    exits[last] = ({"kind": "route_start", "next_unit": unit, "exit_mm": exit_point, "entry_mm": entry,
                    "length_mm": distance} if verified else {"kind": "trim", "length_mm": distance})
    return {i: n for n, i in enumerate(order)}, exits


def plan(obj, units, scale, grid_origin, pull_compensation_mm, cancel=None):
    """Components, verified bridges and fill sequence for one colour object."""
    kept = [i for i, unit in enumerate(units) if not unit["omitted"]]
    if not kept:
        return {"component_of": {}, "bridges": [], "fill_order": {}, "fill_exits": {},
                "evidence": {"components": 0, "pieces_before": 0, "pieces_after": 0}}
    radius = max(1, math.ceil((pull_compensation_mm + JEF_ROUNDING_MM) / scale))
    indices = sorted({units[i]["ring_index"] for i in kept})
    dilated = _dilated_rings(obj, indices, scale, grid_origin, radius, cancel)
    rings = _Union()
    for i, first in enumerate(indices):
        rings.find(first)
        for second in indices[i + 1:]:
            if _overlap(dilated[first], dilated[second]):
                rings.join(first, second)
    labels = {root: number for number, root in enumerate(sorted({rings.find(i) for i in indices}))}
    ring_component = {index: labels[rings.find(index)] for index in indices}
    members = {}
    for index in indices:
        members.setdefault(ring_component[index], []).append(index)
    masks = {component: Mask(image, origin, scale) for component, (image, origin)
             in _component_masks(dilated, members).items()}
    component_of = {i: ring_component[units[i]["ring_index"]] for i in kept}
    lines = {i: _polyline(units[i]) for i in kept}
    lines = {i: line for i, line in lines.items() if line and len(line) >= 2}
    pieces, bridges = _Union(), []
    by_component = {}
    for i in lines:
        pieces.find(i)
        by_component.setdefault(component_of[i], []).append(i)
    def inside_of(component):
        mask = masks[component]
        pixel = lambda p: (p[0] / scale - mask.origin[0], p[1] / scale - mask.origin[1])
        return lambda a, b: mask.segment(pixel(a), pixel(b))

    fill_order, fill_exits = {}, {}
    for component in sorted(set(component_of.values())):
        fills = [i for i in kept if component_of[i] == component and units[i]["technique"] == "fill"]
        if fills:
            strokes = [i for i in lines if component_of[i] == component]
            order, exits = _fill_plan(fills, strokes, lines, units, inside_of(component))
            fill_order.update(order)
            fill_exits.update(exits)
    for component, keys in by_component.items():
        inside = inside_of(component)
        found = sorted(_candidates(keys, lines, inside, cancel), key=lambda item: item[:3])
        for distance, start, target, end, point, verified in found:
            if distance <= JOIN_MM:
                pieces.join(start, target)
        for distance, start, target, end, point, verified in found:
            if distance > JOIN_MM and verified and pieces.join(start, target):
                bridges.append({"component": component, "from_unit": start, "to_unit": target,
                                "length_mm": distance, "path": path([end, point]),
                                "coverage_proof": "segment_inside_component_mask_dilated_by_pull_compensation"})
    roots = {pieces.find(i) for i in lines}
    evidence = {"components": len(members), "dilation_radius_mm": radius * scale,
                "pieces_after": len(roots), "bridges": len(bridges),
                "max_bridge_mm": max((b["length_mm"] for b in bridges), default=0.),
                "join_mm": JOIN_MM, "max_allowed_bridge_mm": MAX_BRIDGE_MM}
    evidence["pieces_before"] = evidence["pieces_after"] + len(bridges)
    evidence["fill_exits"] = {str(i): {k: v for k, v in e.items() if k in {"kind", "length_mm", "next_unit"}}
                              for i, e in fill_exits.items()}
    return {"component_of": component_of, "bridges": bridges, "fill_order": fill_order,
            "fill_exits": fill_exits, "evidence": evidence}
