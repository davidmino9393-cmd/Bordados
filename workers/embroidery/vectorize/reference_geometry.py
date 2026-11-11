"""Reference-only width decisions and pixel centreline derivations, never E1 repairs.

Widths are area-weighted square-opening granulometry at the registered pixel
scale (axis oriented, up to sqrt(2) bias on diagonals). No physical calibration.
Local stroke widths and verified rails are derived inside the registered mask.
"""
from collections import defaultdict, deque
import math
import json

from PIL import Image, ImageDraw, ImageChops, ImageFilter, ImageOps

from . import stitchable, local_columns
from .contours import signed_area
from .thin_features import _opening, _window, _shift, PROVISIONAL_MIN_BORDABLE_WIDTH_MM
from .types import check_cancel

RUNNING_BELOW_MM = 1.0
WIDE_FILL_FROM_MM = 7.0
MIN_REFERENCE_FILL_AREA_MM2 = 2.0
# A rescued small stroke whose outline touches another colour along more than this share is an antialias seam
# or rim between two colours (El Fortín: 1 px mauve line where the coloured and grey halves meet), not a drawn line.
SEAM_CONTACT_SHARE = 0.5
NARROW_ROW_SPACING_MM = 0.35
WIDE_ROW_SPACING_MM = 0.35
MAX_COMPENSATION_MM = 0.25
COMPENSATION_WIDTH_FRACTION = 0.25
LEGIBILITY_AREA_FRACTION = 0.30
LEGIBILITY_TARGET_WIDTH_MM = 0.8
WIDTH_THRESHOLDS_MM = (0.4, 0.6, 0.8, 1.0)
QUANTILES = {"min": 0.0, "p10": 0.1, "p20": 0.2, "median": 0.5, "p90": 0.9}
DERIVATION = "zhang_suen_pixel_skeleton_8_connected_no_contour_substitution"
SATIN_LIMITATION = "local_width_over_4_under_7mm_conservative_tatami_avoids_long_floating_satin"


def _inside(point, ring):
    x, y = point
    return sum((a[1] > y) != (b[1] > y) and
               x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
               for a, b in zip(ring, ring[1:] + ring[:1])) % 2 == 1


def _components(path, cancel=None):
    """Outer rings with their holes; nested islands remain separate components."""
    rings = [ring for part in stitchable._SUBPATH.findall(path)
             for ring in stitchable.split_contacts(stitchable._points(part))]
    outers = [(index, ring, []) for index, ring in enumerate(rings) if signed_area(ring) > 0]
    bounds = {index: (min(x for x, _ in ring), min(y for _, y in ring),
                      max(x for x, _ in ring), max(y for _, y in ring)) for index, ring, _ in outers}
    for hole in (ring for ring in rings if signed_area(ring) < 0):
        check_cancel(cancel)
        x, y = hole[0]
        owners = [entry for entry in outers if bounds[entry[0]][0] <= x <= bounds[entry[0]][2]
                  and bounds[entry[0]][1] <= y <= bounds[entry[0]][3]
                  and any(_inside(point, entry[1]) for point in hole)]
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
    # Only pixels with 2-6 neighbours can be deleted; a fully surrounded pixel
    # changes only after a neighbour is deleted. Visiting the boundary alone
    # yields exactly the full-scan deletions, in time ~ perimeter, not area.
    candidates = {(x, y) for x, y in pixels if any((x + dx, y + dy) not in pixels for dx, dy in offsets)}
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            check_cancel(cancel)
            remove = set()
            for x, y in candidates:
                n = [int((x + dx, y + dy) in pixels) for dx, dy in offsets]
                if not 2 <= sum(n) <= 6 or sum(not n[i] and n[(i + 1) % 8] for i in range(8)) != 1:
                    continue
                triples = ((0, 2, 4), (2, 4, 6)) if step == 0 else ((0, 2, 6), (0, 4, 6))
                if all(not n[a] * n[b] * n[c] for a, b, c in triples):
                    remove.add((x, y))
            pixels.difference_update(remove)
            candidates.difference_update(remove)
            candidates.update(q for x, y in remove for dx, dy in offsets if (q := (x + dx, y + dy)) in pixels)
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


def _mask_contours(image, origin, scale, tolerance, cancel):
    from array import array
    from .contours import contours
    from .segmentation import Segmentation, BACKGROUND
    segmentation = Segmentation(array("H", (0 if p else BACKGROUND for p in image.tobytes())),
                                image.width, image.height, 0, 0, {0: "#000000"}, {})
    traced = contours(segmentation, cancel)
    rings = [[((x + origin[0]) * scale, (y + origin[1]) * scale) for x, y in ring]
             for item in traced for ring in item.loops]
    return stitchable.clean_rings(rings, tolerance)


def _fill_unit(index, rings, widths, stats, origin, scale, tolerance, cancel):
    clean = stitchable.clean_rings(rings, tolerance)
    if not clean:
        return None
    points = [point for ring in clean for point in ring]
    width = stats.get("median_mm", 0)
    limitation = ("residual_junction_or_cap_not_verified_as_single_satin_column" if width <= 4
                  else SATIN_LIMITATION if width < 7 else None)
    return {"ring_index": index, "width": stats, "area_mm2": widths.pixels * scale * scale,
            "technique": "fill", "local_width_mm": width,
            "pull_compensation_mm": MAX_COMPENSATION_MM, "row_spacing_mm": .35,
            "satin_limitation": limitation,
            "geometry_role": "residual_junction_or_cap_patch" if width <= 4 else "wide_stroke_region",
            "stitch_path_mm": None, "satin": None, "derivation": "topology_checked_derived_contours",
            "fill_path_mm": " ".join(stitchable._format_ring(r) for r in clean), "omitted": None,
            "height_mm": max(y for _, y in points) - min(y for _, y in points),
            "entry_mm": clean[0][0], "exit_mm": clean[0][0],
            "fallback_reason": limitation or "local_width_at_least_7mm_tatami"}


def _disk_dilate(image, radius, cancel):
    """Euclidean pixel disk, rather than a square that overgrows diagonals."""
    padded = ImageOps.expand(image, radius, fill=0)
    output = Image.new("L", padded.size, 0)
    for dy in range(-radius, radius + 1):
        check_cancel(cancel)
        reach = math.floor(math.sqrt(radius * radius - dy * dy))
        horizontal = _window(padded, 2 * reach + 1, ImageChops.lighter, 0, cancel)
        horizontal = _shift(horizontal, -reach, 0)
        output = ImageChops.lighter(output, _shift(horizontal, dy, 1))
    return output.crop((radius, radius, radius + image.width, radius + image.height))


def _broad_fill_overlap(fill_mask, fill_origin, original, origin, covered, scale, cancel):
    seed = Image.new("L", original.size, 0)
    seed.paste(fill_mask, (round(fill_origin[0] - origin[0]), round(fill_origin[1] - origin[1])))
    radius = max(1, math.floor(1.5 / scale))
    growth = ImageChops.darker(_disk_dilate(seed, radius, cancel), original)
    growth = ImageChops.darker(growth, covered.filter(ImageFilter.MaxFilter(3)))
    grown = ImageChops.lighter(seed, growth)
    # Growth-only lobes belong to future satin, not this fill seed. A second
    # disconnected exterior in one Ink/Stitch fill path is interpreted as a
    # hole and can invalidate the required underlay inset.
    raw, original_seed = grown.tobytes(), seed.tobytes()
    retained = bytearray(len(raw))
    pending = deque(i for i, value in enumerate(original_seed) if value)
    for index in pending:
        retained[index] = 255
    width = grown.width
    while pending:
        if len(pending) % 1024 == 0:
            check_cancel(cancel)
        index = pending.popleft()
        x, y = index % width, index // width
        neighbors = ((index - 1,) if x else ()) + ((index + 1,) if x + 1 < width else ())
        neighbors += ((index - width,) if y else ()) + ((index + width,) if y + 1 < grown.height else ())
        for following in neighbors:
            if raw[following] and not retained[following]:
                retained[following] = 255
                pending.append(following)
    grown = Image.frombytes("L", grown.size, bytes(retained))
    return grown, (grown.histogram()[255] - seed.histogram()[255]) * scale * scale


def _original_normal_width(fill_mask, fill_origin, original, origin, scale, cancel):
    mask = local_columns.Mask(original, origin, scale)
    chains = local_columns.chains(_thin(fill_mask, cancel))
    if not chains:
        return 0.
    chain = max(chains, key=len)
    offset = (fill_origin[0] - origin[0], fill_origin[1] - origin[1])
    points = [(x + offset[0], y + offset[1]) for x, y in chain]
    samples = local_columns.sections(local_columns._smooth(points, mask), mask)
    from statistics import median
    return median(s["width"] for s in samples) if samples else 0.


def _is_small_running_stroke(units):
    # Retain an isolated stroke that can take a real short running stitch.
    # The span/width check excludes compact flecks with a spurious skeleton.
    if len(units) != 1 or units[0]["technique"] != "running":
        return False
    unit = units[0]
    span = math.dist(unit["entry_mm"], unit["exit_mm"])
    return span >= 1.25 and span >= 3 * unit["local_width_mm"]


def _contact_share(image, origin, others):
    """Share of the 1 px outline around a ring mask that lies on another colour's pixels."""
    if others is None:
        return 0.
    padded = Image.new("L", (image.width + 2, image.height + 2), 0)
    padded.paste(image, (1, 1))
    outline = ImageChops.subtract(padded.filter(ImageFilter.MaxFilter(3)), padded)
    left, top = round(origin[0]) - 1, round(origin[1]) - 1
    near = others.crop((left, top, left + padded.width, top + padded.height))
    total = outline.histogram()[255]
    return ImageChops.multiply(outline, near).histogram()[255] / total if total else 0.


def _decision(index, outer, holes, widths, origin, scale, tolerance, color, cancel, elastic=False, others=None):
    stats = _statistics([widths], scale)
    area = widths.pixels * scale * scale
    omitted = stitchable.OMITTED_NEAR_WHITE if stitchable.is_near_white(color) else None
    units, covered = [], None
    if not omitted:
        units, covered = local_columns.derive(widths.image, origin, scale, _thin, cancel)
        if (stitchable.ring_area_mm2(outer) < stitchable.MIN_STITCHABLE_AREA_MM2
                and not (_is_small_running_stroke(units)
                         and _contact_share(widths.image, origin, others) <= SEAM_CONTACT_SHARE)):
            omitted = stitchable.OMITTED_TOO_SMALL
    if omitted:
        return [{"ring_index": index, "width": stats, "area_mm2": area, "technique": "fill",
                 "omitted": omitted, "stitch_path_mm": None, "fill_path_mm": None,
                 "row_spacing_mm": None, "pull_compensation_mm": 0}]
    output = []
    source_height = max(y for _, y in outer) - min(y for _, y in outer)

    def append_units(derived, role="local_stroke"):
        for unit in derived:
            width = unit["local_width_mm"]
            micro = source_height < 5 or width < 1.5
            output.append({"ring_index": index, "width": stats, "area_mm2": area,
                           "local_estimated_stitch_area_mm2": width * unit["length_mm"],
                           "source_height_mm": source_height, "geometry_role": role,
                           "omitted": None, "fill_path_mm": None, "satin_limitation": None,
                           "derivation": "mask_skeleton_local_normal_intersections_verified_inside_stroke",
                           "row_spacing_mm": .55 if micro else .4,
                           "pull_compensation_mm": 0 if unit["technique"] == "running" else .35 if elastic else .25,
                           "micro": micro, **unit})

    append_units(units)
    # Only the reference coverage mask is subtracted. Original E1 paths and
    # design holes are never mutated. A subpixel rail inset does not create a
    # second fill band along the edge of a satin.
    residual = ImageChops.subtract(widths.image, covered.filter(ImageFilter.MaxFilter(3)))
    if not output:
        residual = widths.image
    # Junction/cap leftovers are not new skinny fill objects. Re-skeletonize
    # them once, measuring normals and extending terminals in the ORIGINAL
    # component mask. This produces overlapping real columns instead of a
    # tatami sliver whose 1.5 mm underlay inset cannot fit.
    if output and residual.histogram()[255] * scale * scale >= MIN_REFERENCE_FILL_AREA_MM2:
        cap_units, cap_covered = local_columns.derive(residual, origin, scale, _thin, cancel,
                                                     normal_image=widths.image)
        append_units(cap_units, "residual_junction_or_cap_column")
        covered = ImageChops.lighter(covered, cap_covered)
        residual = ImageChops.subtract(residual, cap_covered.filter(ImageFilter.MaxFilter(3)))
    if residual.histogram()[255] * scale * scale >= MIN_REFERENCE_FILL_AREA_MM2:
        broad_mask = _opening(widths.image, math.ceil(4 / scale), cancel)
        residual_rings = _mask_contours(residual, origin, scale, tolerance, cancel)
        path = " ".join(stitchable._format_ring(ring) for ring in residual_rings)
        for _, border, voids in _components(path, cancel):
            fill_mask, fill_origin = _mask([border, *voids], scale, cancel)
            measure = Widths(fill_mask, scale, cancel)
            fill_stats = _statistics([measure], scale)
            if measure.pixels * scale * scale < MIN_REFERENCE_FILL_AREA_MM2:
                continue
            seed = Image.new("L", widths.image.size, 0)
            seed.paste(fill_mask, (round(fill_origin[0] - origin[0]), round(fill_origin[1] - origin[1])))
            broad_fraction = ImageChops.darker(seed, broad_mask).histogram()[255] / max(1, measure.pixels)
            source_width = (_original_normal_width(fill_mask, fill_origin, widths.image, origin, scale, cancel)
                            if broad_fraction >= .8 else 0.)
            broad_source = source_width > 4
            if fill_stats.get("median_mm", 0) <= 4 and not broad_source:
                patch_units, patch_covered = local_columns.derive(fill_mask, fill_origin, scale, _thin, cancel)
                if not patch_units:
                    patch_units, patch_covered = local_columns.derive_axis(fill_mask, fill_origin, scale, cancel)
                uncovered = ImageChops.subtract(fill_mask, patch_covered.filter(ImageFilter.MaxFilter(3)))
                uncovered_area = uncovered.histogram()[255] * scale * scale
                if patch_units and uncovered_area < MIN_REFERENCE_FILL_AREA_MM2:
                    for patch_unit in patch_units:
                        patch_unit["uncovered_residual_area_mm2"] = uncovered_area
                    append_units(patch_units, "residual_patch_interior_columns")
                    continue
            unit = _fill_unit(index, [border, *voids], measure, fill_stats, fill_origin, scale, tolerance, cancel)
            if unit:
                if broad_source:
                    unit.update(local_width_mm=source_width, residual_median_width_mm=fill_stats["median_mm"],
                                broad_original_mask_fraction=broad_fraction, geometry_role="wide_stroke_region",
                                fallback_reason=SATIN_LIMITATION if source_width < 7 else "local_width_at_least_7mm_tatami",
                                satin_limitation=SATIN_LIMITATION if source_width < 7 else None)
                if broad_source or fill_stats.get("median_mm", 0) > 4:
                    grown, overlap_area = _broad_fill_overlap(fill_mask, fill_origin, widths.image, origin,
                                                               covered, scale, cancel)
                    if overlap_area:
                        grown_rings = _mask_contours(grown, origin, scale, tolerance, cancel)
                        unit["fill_path_mm"] = " ".join(stitchable._format_ring(r) for r in grown_rings)
                        unit["overlap_target_mm"] = 1.5
                        unit["overlap_area_mm2"] = overlap_area
                        unit["overlap_policy"] = "euclidean_disk_growth_clipped_to_original_mask_and_future_satin_coverage"
                micro = unit["height_mm"] < 5 or unit["local_width_mm"] < 1.5
                unit.update(micro=False, row_spacing_mm=.35,
                            source_height_mm=source_height,
                            pull_compensation_mm=.35 if elastic else .25)
                output.append(unit)
    return output or [{"ring_index": index, "width": stats, "area_mm2": area, "technique": "fill",
                       "omitted": "skeleton_has_no_stitch_segments", "stitch_path_mm": None,
                       "fill_path_mm": None, "row_spacing_mm": None, "pull_compensation_mm": 0}]


def measure_object(obj, scale, tolerance, cancel=None, grid_origin=(0, 0), elastic=False, others=None):
    measured, rings, kept_area = [], [], 0.
    for index, outer, holes in _components(obj.path_data_mm, cancel):
        check_cancel(cancel)
        image, origin = _mask([outer, *holes], scale, cancel, grid_origin)
        widths = Widths(image, scale, cancel)
        units = _decision(index, outer, holes, widths, origin, scale, tolerance, obj.work_color, cancel, elastic, others)
        rings.extend(units)
        if any(not unit["omitted"] for unit in units):
            kept_area += widths.pixels * scale * scale
        measured.append(widths)
    # A residual colour layer below the real fill floor must not become a
    # phantom thread just because its last fragment now qualifies for running.
    if 0 < kept_area < MIN_REFERENCE_FILL_AREA_MM2:
        rings = [{**r, "omitted": "reference_object_below_2mm2",
                  "object_kept_area_mm2": kept_area} if not r["omitted"] else r for r in rings]
    # JsonValue accepts JSON arrays, not arbitrary Python tuples. Keep the
    # contract serializable and valid after a complete H3 model round trip.
    return tuple(json.loads(json.dumps(rings))), _statistics(measured, scale)


# Telas del catálogo con elasticidad media según la guía (6.1: piqué, franela, toalla -> 0,30-0,40 mm): compensación 0,35.
# Las estables (gabardina, jean, lino, algodón plano) quedan en 0,25. Un id desconocido se trata como estable.
ELASTIC_FABRIC_PROFILES = frozenset({"pique", "polar"})
ELASTIC_KEYWORDS = ("elastic", "knit", "punto", "jersey", "lycra", "licra", "toalla", "felpa", "franela")


def is_elastic(fabric_profile):
    name = str(fabric_profile or "").lower()
    return name in ELASTIC_FABRIC_PROFILES or any(word in name for word in ELASTIC_KEYWORDS)


def _coloured_pages(document, scale, cancel):
    """One page raster per non-white object; pixel = mm / scale, the frame of the ring mask origins."""
    bounds = document.page_bounds_mm
    size = (math.ceil(bounds.max_x_mm / scale) + 2, math.ceil(bounds.max_y_mm / scale) + 2)
    pages = {}
    for obj in document.objects:
        if stitchable.is_near_white(obj.work_color):
            continue
        page = Image.new("L", size, 0)
        draw = ImageDraw.Draw(page)
        for _, outer, holes in _components(obj.path_data_mm, cancel):
            for ring, fill in ((outer, 255), *((hole, 0) for hole in holes)):
                draw.polygon([(x / scale, y / scale) for x, y in ring], fill=fill)
        pages[obj.object_id] = page
    return pages


def _others(pages, object_id):
    union = None
    for key, page in pages.items():
        if key != object_id:
            union = page if union is None else ImageChops.lighter(union, page)
    return union


def apply(document, cancel=None, settings=None):
    """Publish per-ring decisions on objects while retaining E1 paths and bounds."""
    affine = document.coordinates.source_px_to_mm
    scale = abs(affine[0])
    objects, evidence = [], {}
    pages = _coloured_pages(document, scale, cancel)
    for obj in document.objects:
        elastic = is_elastic(getattr(settings, "fabric_profile", None))
        rings, stats = measure_object(obj, scale, stitchable.tolerance_for(document), cancel, (affine[4], affine[5]), elastic,
                                      _others(pages, obj.object_id))
        kept = [r for r in rings if not r["omitted"]]
        techniques = {r["technique"] for r in kept}
        technique = next(iter(techniques)) if len(techniques) == 1 else "fill"
        satin = None
        if technique == "satin":
            from embroidery_contracts.design import SatinRails
            rails = kept[0]["satin"]
            point = lambda value: {"x_mm": value[0], "y_mm": value[1]}
            satin = SatinRails(correspondence="guides",
                               left_rail_mm=tuple(point(p) for p in rails["left_rail_mm"]),
                               right_rail_mm=tuple(point(p) for p in rails["right_rail_mm"]),
                               guides_mm=tuple(tuple(point(p) for p in guide) for guide in rails["guides_mm"]))
        objects.append(obj.model_copy(update={"reference_rings": rings, "effective_technique": technique,
                                              "proposed_technique": technique, "satin": satin,
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
            grouped[key].append(ring["stitch_path_mm"] if key[0] in {"running", "satin"} else ring["fill_path_mm"])
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
