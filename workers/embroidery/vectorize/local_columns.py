"""Reference stroke sections derived inside a registered mask, never mask edits."""
import math
from statistics import median

from PIL import Image, ImageDraw

from . import stitchable
from .types import check_cancel

RUNNING_LIMIT_MM = 1.0
SATIN_LIMIT_MM = 4.0
TATAMI_FROM_MM = 7.0
RAIL_INSET_MM = 0.15
RAY_STEP_PX = 0.2
TANGENT_WINDOW_MM = 0.5
SAMPLE_INTERVAL_MM = 0.2


def path(points):
    return " ".join(("M" if i == 0 else "L") + f"{x:.6f},{y:.6f}"
                    for i, (x, y) in enumerate(points))


def chains(pixels):
    graph = {p: set() for p in pixels}
    for x, y in pixels:
        for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
            q = (x + dx, y + dy)
            if q in pixels and not (dx and dy and ((x + dx, y) in pixels or (x, y + dy) in pixels)):
                graph[(x, y)].add(q)
                graph[q].add((x, y))
    output = []
    for start in sorted(pixels, key=lambda p: (len(graph[p]) == 2, p)):
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
            output.append([(x + .5, y + .5) for x, y in chain])
    return output


class Mask:
    def __init__(self, image, origin, scale):
        self.image, self.origin, self.scale = image, origin, scale
        self.pixels = image.load()

    def inside(self, point):
        x, y = point
        return 0 <= x < self.image.width and 0 <= y < self.image.height and bool(self.pixels[int(x), int(y)])

    def segment(self, a, b):
        # Partition exactly at pixel-grid crossings; fixed-distance sampling
        # can miss a short excursion through a hole near a pixel corner.
        if not self.inside(a) or not self.inside(b):
            return False
        cuts = {0., 1.}
        for axis in (0, 1):
            delta = b[axis] - a[axis]
            if not delta:
                continue
            first, last = sorted((a[axis], b[axis]))
            for boundary in range(math.floor(first) + 1, math.ceil(last)):
                cuts.add((boundary - a[axis]) / delta)
        ordered = sorted(cuts)
        return all(self.inside((a[0] + (b[0] - a[0]) * (first + last) / 2,
                                a[1] + (b[1] - a[1]) * (first + last) / 2))
                   for first, last in zip(ordered, ordered[1:]))

    def mm(self, point):
        return ((point[0] + self.origin[0]) * self.scale,
                (point[1] + self.origin[1]) * self.scale)

    def ray(self, point, normal, sign):
        distance = 0.
        maximum = math.hypot(*self.image.size)
        while distance < maximum:
            following = distance + RAY_STEP_PX
            if not self.inside((point[0] + normal[0] * following * sign,
                                point[1] + normal[1] * following * sign)):
                # Binary search the exact pixel boundary, then keep the rail inside.
                low, high = distance, following
                for _ in range(12):
                    middle = (low + high) / 2
                    if self.inside((point[0] + normal[0] * middle * sign,
                                    point[1] + normal[1] * middle * sign)):
                        low = middle
                    else:
                        high = middle
                return low
            distance = following
        return distance


def sections(chain, mask):
    window = max(2, round(TANGENT_WINDOW_MM / SAMPLE_INTERVAL_MM))
    output = []
    for i, center in enumerate(chain):
        before, after = chain[max(0, i - window)], chain[min(len(chain) - 1, i + window)]
        dx, dy = after[0] - before[0], after[1] - before[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        normal = (-dy / length, dx / length)
        left, right = mask.ray(center, normal, 1), mask.ray(center, normal, -1)
        width = (left + right) * mask.scale
        # Numerical rounding of an exact one/four millimetre pixel strip must
        # not change the technique at a boundary.
        width = round(width, 4)
        technique = "running" if width < RUNNING_LIMIT_MM else "satin" if width <= SATIN_LIMIT_MM else "fill"
        inset = min(RAIL_INSET_MM / mask.scale, min(left, right) / 4)
        a = (center[0] + normal[0] * (left - inset), center[1] + normal[1] * (left - inset))
        b = (center[0] - normal[0] * (right - inset), center[1] - normal[1] * (right - inset))
        edge_a = (center[0] + normal[0] * left, center[1] + normal[1] * left)
        edge_b = (center[0] - normal[0] * right, center[1] - normal[1] * right)
        output.append({"center": center, "left": a, "right": b, "width": width,
                       "edge_left": edge_a, "edge_right": edge_b,
                       "inset_mm": inset * mask.scale, "technique": technique})
    # Smooth rails, but never smooth across a physical technique threshold:
    # a wide junction station must not leak into a narrow satin's rails.
    for side in ("left", "right"):
        original = [s[side] for s in output]
        for i in range(1, len(output) - 1):
            if not output[i - 1]["technique"] == output[i]["technique"] == output[i + 1]["technique"]:
                continue
            point = tuple((original[i - 1][axis] + 2 * original[i][axis] + original[i + 1][axis]) / 4 for axis in (0, 1))
            if mask.inside(point):
                output[i][side] = point
    return output


def _with_width_crossings(samples):
    """Split a sampled edge at the physical running/satin threshold."""
    for previous, current in zip(samples, samples[1:]):
        yield previous
        if {previous["technique"], current["technique"]} != {"running", "satin"}:
            continue
        t = (RUNNING_LIMIT_MM - previous["width"]) / (current["width"] - previous["width"])
        crossing = {"width": RUNNING_LIMIT_MM,
                    "inset_mm": min(previous["inset_mm"], current["inset_mm"])}
        for key in ("center", "left", "right", "edge_left", "edge_right"):
            crossing[key] = tuple(a + (b - a) * t for a, b in zip(previous[key], current[key]))
        if t > 0:
            yield {**crossing, "technique": previous["technique"]}
        if t < 1:
            yield {**crossing, "technique": current["technique"]}
    if samples:
        yield samples[-1]


def _runs(samples, mask):
    run = []
    for sample in _with_width_crossings(samples):
        compatible = not run or (sample["technique"] == run[-1]["technique"] and
                                 mask.segment(run[-1]["center"], sample["center"]) and
                                 (sample["technique"] != "satin" or
                                  (mask.segment(run[-1]["left"], sample["left"]) and
                                   mask.segment(run[-1]["right"], sample["right"]))))
        if not compatible:
            if len(run) >= 2:
                yield run
            run = []
        run.append(sample)
    if len(run) >= 2:
        yield run


def _satin(run, mask):
    left, right = [[mask.mm(s[side]) for s in run] for side in ("left", "right")]
    # One guide is deliberately used: it cannot intersect another rung and
    # is unambiguous even on a short/wide column. Cross segment interiors,
    # not shared vertices whose native flattening can move a few microns.
    rungs = []
    indices = sorted(range(len(run) - 1), key=lambda i: abs(i + .5 - (len(run) - 1) / 2))
    for i in indices:
        a = tuple((left[i][axis] + left[i + 1][axis]) / 2 for axis in (0, 1))
        b = tuple((right[i][axis] + right[i + 1][axis]) / 2 for axis in (0, 1))
        length = math.dist(a, b)
        if not length:
            continue
        extension = min(run[i]["inset_mm"], run[i + 1]["inset_mm"]) * .75
        dx, dy = (b[0] - a[0]) / length * extension, (b[1] - a[1]) / length * extension
        rung = [(a[0] - dx, a[1] - dy), (b[0] + dx, b[1] + dy)]
        pixels = [(x / mask.scale - mask.origin[0], y / mask.scale - mask.origin[1]) for x, y in rung]
        if (mask.segment(*pixels) and
                _intersection_count(rung, left) == _intersection_count(rung, right) == 1):
            rungs = [rung]
            break
    # Rails on a very small straight stroke may have only two nodes, which
    # Ink/Stitch would mistake for additional rungs. Add a collinear node.
    left, right = [_dedup(rail) for rail in (left, right)]
    for rail in (left, right):
        if len(rail) < 2 or sum(math.dist(a, b) for a, b in zip(rail, rail[1:])) < .25:
            return None
        if len(rail) == 2:
            rail.insert(1, ((rail[0][0] + rail[1][0]) / 2, (rail[0][1] + rail[1][1]) / 2))
    if not stitchable.simple_ring(left + list(reversed(right))):
        return None
    valid = [rung for rung in rungs if _intersection_count(rung, left) == _intersection_count(rung, right) == 1]
    rungs = valid[:3] if len(valid) >= 3 else valid[:1]
    if not rungs:
        return None
    return {"left_rail_mm": left, "right_rail_mm": right, "guides_mm": rungs,
            "centerline_mm": [mask.mm(s["center"]) for s in run],
            "paired_rail_stations_mm": [[mask.mm(s["left"]), mask.mm(s["right"])] for s in run],
            "correspondence": "guides", "path": " ".join(path(points) for points in [left, right, *rungs])}


def derive(image, origin, scale, thin, cancel=None, normal_image=None):
    """Return local stitch units plus their coverage in a separate derived mask."""
    mask = Mask(normal_image if normal_image is not None else image, origin, scale)
    covered = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(covered)
    output = []
    skeleton = thin(image, cancel)
    for chain in chains(skeleton):
        check_cancel(cancel)
        chain = _smooth(chain, mask)
        chain = _extend_ends(chain, mask, skeleton)
        for run in _runs(sections(chain, mask), mask):
            technique = run[0]["technique"]
            if technique == "fill":
                continue
            satin = _satin(run, mask) if technique == "satin" else None
            if technique == "satin" and satin is None:
                # Split a folded column rather than sending invalid rails.
                for part, local in _valid_parts(run, mask):
                    output.append(_unit(part, mask, local))
                    _cover(draw, part, scale)
                continue
            output.append(_unit(run, mask, satin))
            _cover(draw, run, scale)
    return output, covered


def _dedup(points):
    return [p for i, p in enumerate(points) if i == 0 or math.dist(p, points[i - 1]) > 1e-6]


def derive_axis(image, origin, scale, cancel=None):
    """A compact cap may thin to one point; use its longest interior scanline."""
    mask = Mask(image, origin, scale)
    longest = []
    for vertical in (False, True):
        major, minor = (image.height, image.width) if vertical else image.size
        for row in range(minor):
            check_cancel(cancel)
            current = []
            for column in range(major):
                point = (row + .5, column + .5) if vertical else (column + .5, row + .5)
                if mask.inside(point):
                    current.append(point)
                    if len(current) > len(longest):
                        longest = list(current)
                else:
                    current = []
    output, covered = [], Image.new("L", image.size, 0)
    if len(longest) < 2:
        return output, covered
    draw = ImageDraw.Draw(covered)
    for run in _runs(sections(_smooth(longest, mask), mask), mask):
        if run[0]["technique"] == "running":
            output.append(_unit(run, mask, None))
            _cover(draw, run, scale)
        elif run[0]["technique"] == "satin":
            for part, satin in _valid_parts(run, mask):
                output.append(_unit(part, mask, satin))
                _cover(draw, part, scale)
    return output, covered


def _intersection_count(rung, rail):
    a, b = rung
    intersections = set()
    for c, d in zip(rail, rail[1:]):
        if not stitchable.segments_intersect(a, b, c, d):
            continue
        dx, dy = b[0] - a[0], b[1] - a[1]
        ex, ey = d[0] - c[0], d[1] - c[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-10:
            return -1
        along = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / denominator
        intersections.add((round(a[0] + along * dx, 5), round(a[1] + along * dy, 5)))
    return len(intersections)


def _valid_parts(run, mask):
    """Bisect folded columns, keeping the longest valid parts intact.

    A piece too short to bisect further keeps its axis as a running stitch
    instead of being dropped: dropping it left gaps in narrow letters."""
    pending = [run]
    while pending:
        part = pending.pop()
        local = _satin(part, mask)
        if local:
            yield part, local
        elif len(part) > 3:
            middle = len(part) // 2
            pending.extend((part[:middle + 1], part[middle:]))
        else:
            yield [{**sample, "technique": "running"} for sample in part], None


def _smooth(chain, mask):
    simplified = stitchable._simplify_chain(chain, (.04 / mask.scale) ** 2)
    sampled = [simplified[0]]
    for a, b in zip(simplified, simplified[1:]):
        steps = max(1, math.ceil(math.dist(a, b) * mask.scale / SAMPLE_INTERVAL_MM))
        sampled.extend((a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps)
                       for i in range(1, steps + 1))
    smooth = [sampled[0]]
    for i in range(1, len(sampled) - 1):
        point = tuple((sampled[i - 1][axis] + 2 * sampled[i][axis] + sampled[i + 1][axis]) / 4 for axis in (0, 1))
        smooth.append(point if mask.inside(point) and mask.segment(smooth[-1], point) else sampled[i])
    return smooth + sampled[-1:]


def _cover(draw, run, scale):
    for a, b in zip(run, run[1:]):
        # The 0.25+ mm compensation covers the <=0.15 mm rail inset; use
        # the original normal endpoints for the derived coverage sweep.
        draw.polygon([a["edge_left"], b["edge_left"], b["edge_right"], a["edge_right"]], fill=255)


def _extend_ends(chain, mask, skeleton):
    """A terminal skeleton cap stops half a stroke short of a square end."""
    result = list(chain)
    for reverse in (False, True):
        points = list(reversed(result)) if reverse else result
        x, y = int(points[0][0]), int(points[0][1])
        neighbors = sum((x + dx, y + dy) in skeleton for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy)
        if neighbors != 1:
            continue
        other = points[min(len(points) - 1, max(2, round(.5 / mask.scale)))]
        dx, dy = points[0][0] - other[0], points[0][1] - other[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        direction = (dx / length, dy / length)
        reach = max(0., mask.ray(points[0], direction, 1) - RAIL_INSET_MM / mask.scale)
        terminal = (points[0][0] + direction[0] * reach, points[0][1] + direction[1] * reach)
        if reach > .1:
            points.insert(0, terminal)
        result = list(reversed(points)) if reverse else points
    return result


def _unit(run, mask, satin):
    points = [mask.mm(s["center"]) for s in run]
    width = median(s["width"] for s in run)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    direct = math.dist(points[0], points[-1])
    curved = (direct == 0 or length > direct * 1.005 or
              any(stitchable._distance_squared(p, points[0], points[-1]) > .05 ** 2 for p in points[1:-1]))
    return {"technique": run[0]["technique"], "local_width_mm": width,
            "local_width_min_mm": min(s["width"] for s in run),
            "local_width_max_mm": max(s["width"] for s in run),
            "stitch_path_mm": satin["path"] if satin else path(points), "satin": satin,
            "height_mm": max(y for _, y in points) - min(y for _, y in points) + width,
            "running_stitch_length_mm": 1.25 if curved else 2.5,
            "entry_mm": points[0], "exit_mm": points[-1], "length_mm": length}
