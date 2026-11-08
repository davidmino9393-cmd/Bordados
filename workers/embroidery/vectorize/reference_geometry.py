"""Reference-only width decisions and pixel centreline derivations, never E1 repairs.

Widths are area-weighted square-opening granulometry at the registered pixel
scale (axis oriented, up to sqrt(2) bias on diagonals). No physical calibration.
Satin rails are not derived here: medium strokes use the declared fill fallback.
"""
from collections import defaultdict
import math

from PIL import Image, ImageDraw

from . import stitchable
from .contours import signed_area
from .thin_features import _opening, PROVISIONAL_MIN_BORDABLE_WIDTH_MM
from .types import check_cancel

RUNNING_BELOW_MM = 0.9
WIDE_FILL_FROM_MM = 2.0
MIN_REFERENCE_FILL_AREA_MM2 = 2.0
NARROW_ROW_SPACING_MM = 0.35
WIDE_ROW_SPACING_MM = 0.45
MAX_COMPENSATION_MM = 0.2
COMPENSATION_WIDTH_FRACTION = 0.25
LEGIBILITY_AREA_FRACTION = 0.30
LEGIBILITY_TARGET_WIDTH_MM = 0.8
WIDTH_THRESHOLDS_MM = (0.4, 0.6, 0.8, 1.0)
QUANTILES = {"min": 0.0, "p10": 0.1, "p20": 0.2, "median": 0.5, "p90": 0.9}
DERIVATION = "zhang_suen_pixel_skeleton_8_connected_no_contour_substitution"
SATIN_LIMITATION = "satin_pending_verified_rails; reference_fallback_fill_spacing_0.35mm"


def _inside(point, ring):
    x, y = point
    return sum((a[1] > y) != (b[1] > y) and
               x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
               for a, b in zip(ring, ring[1:] + ring[:1])) % 2 == 1


def _components(path, cancel=None):
    """Outer rings with their holes; nested islands remain separate components."""
    rings = [stitchable._points(part) for part in stitchable._SUBPATH.findall(path)]
    outers = [(index, ring, []) for index, ring in enumerate(rings) if signed_area(ring) > 0]
    bounds = {index: (min(x for x, _ in ring), min(y for _, y in ring),
                      max(x for x, _ in ring), max(y for _, y in ring)) for index, ring, _ in outers}
    for hole in (ring for ring in rings if signed_area(ring) < 0):
        check_cancel(cancel)
        x, y = hole[0]
        owners = [entry for entry in outers if bounds[entry[0]][0] <= x <= bounds[entry[0]][2]
                  and bounds[entry[0]][1] <= y <= bounds[entry[0]][3] and _inside(hole[0], entry[1])]
        if owners:
            min(owners, key=lambda entry: stitchable.ring_area_mm2(entry[1]))[2].append(hole)
    return outers


def _mask(rings, scale, cancel, grid_origin=(0, 0)):
    """Scan pixel centres, avoiding Pillow polygon's inclusive right/bottom edges."""
    rings = [[((x - grid_origin[0]) / scale, (y - grid_origin[1]) / scale) for x, y in ring] for ring in rings]
    left = math.floor(min(x for x, _ in rings[0]))
    top = math.floor(min(y for _, y in rings[0]))
    right = math.ceil(max(x for x, _ in rings[0]))
    bottom = math.ceil(max(y for _, y in rings[0]))
    image = Image.new("L", (max(1, right - left), max(1, bottom - top)), 0)
    draw = ImageDraw.Draw(image)
    scanlines = defaultdict(list)
    for ring in rings:
        check_cancel(cancel)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if a[1] == b[1]:
                continue
            first = max(top, math.ceil(min(a[1], b[1]) - 0.5))
            last = min(bottom, math.ceil(max(a[1], b[1]) - 0.5))
            for y in range(first, last):
                scanlines[y - top].append(a[0] + (y + 0.5 - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    for row, values in scanlines.items():
        check_cancel(cancel)
        crossings = sorted(values)
        for start, end in zip(crossings[::2], crossings[1::2]):
            first = math.ceil(start - left - 0.5)
            last = math.ceil(end - left - 0.5) - 1
            if last >= first:
                draw.line((first, row, last, row), fill=255)
    return image, (left + grid_origin[0] / scale, top + grid_origin[1] / scale)


class Widths:
    def __init__(self, image, scale, cancel):
        self.image, self.scale, self.cancel = image, scale, cancel
        self.pixels = image.histogram()[255]
        self.maximum = min(image.size)
        self.cache = {1: self.pixels, self.maximum + 1: 0}

    def surviving(self, element):
        if element > self.maximum:
            return 0
        if element not in self.cache:
            self.cache[element] = _opening(self.image, element, self.cancel).histogram()[255]
        return self.cache[element]

    def below(self, width):
        element = max(1, math.ceil(width / self.scale))
        if element > 1 and (element - 1) * self.scale >= width:
            element -= 1
        return self.pixels - self.surviving(element)


def _statistics(measures, scale):
    pixels = sum(item.pixels for item in measures)
    if not pixels:
        return {"pixels": 0, "measurable": False}
    maximum = max(item.maximum for item in measures)
    quantiles = {}
    for name, fraction in QUANTILES.items():
        low, high = 1, maximum + 1
        while high - low > 1:
            middle = (low + high) // 2
            lost = pixels - sum(item.surviving(middle) for item in measures)
            if lost <= pixels * fraction:
                low = middle
            else:
                high = middle
        quantiles[name + "_mm"] = low * scale
    return {"pixels": pixels, "measurable": True, **quantiles,
            "fraction_below_mm": {str(width): sum(m.below(width) for m in measures) / pixels
                                  for width in WIDTH_THRESHOLDS_MM},
            "method": "area_weighted_square_opening_at_registered_pixel_scale",
            "mm_per_px": scale, "diagonal_width_bias_max": math.sqrt(2),
            "minimum_scale_for_80pct_above_0.8mm":
                LEGIBILITY_TARGET_WIDTH_MM / quantiles["p20_mm"]}


def _thin(image, cancel):
    """Zhang-Suen thinning: two topology-preserving parallel deletion passes."""
    width = image.width
    pixels = {(i % width, i // width) for i, value in enumerate(image.tobytes()) if value}
    offsets = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            check_cancel(cancel)
            remove = set()
            for x, y in pixels:
                n = [int((x + dx, y + dy) in pixels) for dx, dy in offsets]
                if not 2 <= sum(n) <= 6 or sum(not n[i] and n[(i + 1) % 8] for i in range(8)) != 1:
                    continue
                triples = ((0, 2, 4), (2, 4, 6)) if step == 0 else ((0, 2, 6), (0, 4, 6))
                if all(not n[a] * n[b] * n[c] for a, b, c in triples):
                    remove.add((x, y))
            pixels.difference_update(remove)
            changed |= bool(remove)
    return pixels


def _centreline(image, origin, scale, cancel):
    pixels = _thin(image, cancel)
    graph = {p: set() for p in pixels}
    for x, y in pixels:
        for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
            q = (x + dx, y + dy)
            if q in pixels and not (dx and dy and ((x + dx, y) in pixels or (x, y + dy) in pixels)):
                graph[(x, y)].add(q)
                graph[q].add((x, y))
    paths = []
    starts = sorted(pixels, key=lambda p: (len(graph[p]) == 2, p))
    for start in starts:
        while graph[start]:
            chain, current = [start], start
            while graph[current]:
                following = min(graph[current])
                graph[current].remove(following)
                graph[following].remove(current)
                chain.append(following)
                current = following
                if current == start or len(graph[current]) != 1:
                    break
            points = [((x + origin[0] + 0.5) * scale, (y + origin[1] + 0.5) * scale) for x, y in chain]
            paths.append(" ".join(("M" if i == 0 else "L") + f"{x:.9f},{y:.9f}"
                                  for i, (x, y) in enumerate(points)))
    return " ".join(paths) or None


def _decision(index, outer, holes, widths, origin, scale, tolerance, color, cancel):
    stats = _statistics([widths], scale)
    median = stats.get("median_mm", 0)
    technique = "running" if median < RUNNING_BELOW_MM else "fill"
    area = widths.pixels * scale * scale
    omitted = None
    if stitchable.is_near_white(color):
        omitted = stitchable.OMITTED_NEAR_WHITE
    elif stitchable.ring_area_mm2(outer) < stitchable.MIN_STITCHABLE_AREA_MM2:
        omitted = stitchable.OMITTED_TOO_SMALL
    elif technique == "fill" and area < MIN_REFERENCE_FILL_AREA_MM2:
        omitted = "reference_fill_below_2mm2"
    retained = [ring for ring in [outer, *holes]
                if stitchable.ring_area_mm2(ring) >= stitchable.MIN_STITCHABLE_AREA_MM2]
    fill_path = " ".join(stitchable._format_ring(stitchable.simplify_ring(r, tolerance)) for r in retained)
    centreline = _centreline(widths.image, origin, scale, cancel) if technique == "running" and not omitted else None
    if technique == "running" and not centreline and not omitted:
        omitted = "skeleton_has_no_stitch_segments"
    return {"ring_index": index, "width": stats, "area_mm2": area, "technique": technique,
            "pull_compensation_mm": 0 if technique == "running" else min(MAX_COMPENSATION_MM, COMPENSATION_WIDTH_FRACTION * median),
            "row_spacing_mm": None if technique == "running" else
                (NARROW_ROW_SPACING_MM if median < WIDE_FILL_FROM_MM else WIDE_ROW_SPACING_MM),
            "satin_limitation": SATIN_LIMITATION if RUNNING_BELOW_MM <= median < WIDE_FILL_FROM_MM else None,
            "stitch_path_mm": centreline, "derivation": DERIVATION if technique == "running" else None,
            "fill_path_mm": fill_path if technique == "fill" else None, "omitted": omitted}


def measure_object(obj, scale, tolerance, cancel=None, grid_origin=(0, 0)):
    measured, rings = [], []
    for index, outer, holes in _components(obj.path_data_mm, cancel):
        check_cancel(cancel)
        image, origin = _mask([outer, *holes], scale, cancel, grid_origin)
        widths = Widths(image, scale, cancel)
        rings.append(_decision(index, outer, holes, widths, origin, scale, tolerance, obj.work_color, cancel))
        measured.append(widths)
    # A residual colour layer below the real fill floor must not become a
    # phantom thread just because its last fragment now qualifies for running.
    kept_area = sum(r["area_mm2"] for r in rings if not r["omitted"])
    if 0 < kept_area < MIN_REFERENCE_FILL_AREA_MM2:
        rings = [{**r, "omitted": "reference_object_below_2mm2",
                  "object_kept_area_mm2": kept_area} if not r["omitted"] else r for r in rings]
    return tuple(rings), _statistics(measured, scale)


def apply(document, cancel=None):
    """Publish per-ring decisions on objects while retaining E1 paths and bounds."""
    affine = document.coordinates.source_px_to_mm
    scale = abs(affine[0])
    objects, evidence = [], {}
    for obj in document.objects:
        rings, stats = measure_object(obj, scale, stitchable.tolerance_for(document), cancel, (affine[4], affine[5]))
        kept = [r for r in rings if not r["omitted"]]
        technique = "running" if kept and all(r["technique"] == "running" for r in kept) else "fill"
        objects.append(obj.model_copy(update={"reference_rings": rings, "effective_technique": technique,
                                              "proposed_technique": technique,
                                              "stitch_path_mm": " ".join(r["stitch_path_mm"] for r in kept
                                                                          if r["stitch_path_mm"]) or None}))
        evidence[obj.object_id] = {**stats, "rings": list(rings), "technique": technique,
                                  "minimum_target_mm_for_80pct_above_0.8mm": [
                                      document.page_bounds_mm.max_x_mm * stats.get("minimum_scale_for_80pct_above_0.8mm", 1),
                                      document.page_bounds_mm.max_y_mm * stats.get("minimum_scale_for_80pct_above_0.8mm", 1)]}
    return document.model_copy(update={"objects": tuple(objects)}), evidence


def groups(obj, rings):
    grouped = defaultdict(list)
    for ring in rings:
        if not ring["omitted"]:
            key = (ring["technique"], ring["row_spacing_mm"], ring["pull_compensation_mm"])
            grouped[key].append(ring["stitch_path_mm"] if key[0] == "running" else ring["fill_path_mm"])
    return [(key, " ".join(paths)) for key, paths in grouped.items()]


def legibility_issues(evidence):
    from embroidery_contracts import IssueCode
    from .types import issue
    return tuple(issue(IssueCode.LEGIBILITY_RISK,
                       "Más del 30% del área está bajo el ancho bordable provisional; revisar la legibilidad.",
                       {"provisional_min_bordable_width_mm": PROVISIONAL_MIN_BORDABLE_WIDTH_MM,
                        **{key: value for key, value in stats.items() if key != "rings"}}, (object_id,),
                       "Revisar las corridas y el tamaño mínimo medido; coser una muestra sin asumir calibración.")
                 for object_id, stats in evidence.items()
                 if stats.get("fraction_below_mm", {}).get(str(PROVISIONAL_MIN_BORDABLE_WIDTH_MM), 0) > LEGIBILITY_AREA_FRACTION)
