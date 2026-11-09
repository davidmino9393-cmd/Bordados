"""Verify one direction guide after native Auto-Satin splits/reverses columns.

Only derived direction lines are replaced. The two native rail subpaths,
stitch parameters, object identity, and registered E1 geometry stay intact.
"""
import math
import re

from process_runner import WorkerFailure

SVG = "{http://www.w3.org/2000/svg}"
IS = "{http://inkstitch.org/namespace}"
SUBPATH = re.compile(r"[Mm][^Mm]*")
TOKENS = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")
FLATNESS_MM = .00001
GUIDE_EXTENSION_MM = .075
VERTEX_CLEARANCE_MM = .005


class _Rail(list):
    def __init__(self, points, vertices):
        super().__init__(points)
        self.vertices = vertices


def _fail(node, reason):
    raise WorkerFailure("WORKER_EXPORT_FAILED", "native_satin_cleanup_unverified",
                        {"object_id": node.get("id"), "detail": reason})


def _distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = dx * dx + dy * dy
    t = 0 if not length else max(0., min(1., ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length))
    return math.dist(point, (start[0] + t * dx, start[1] + t * dy))


def _flatten_cubic(a, b, c, d, depth=0):
    if depth >= 18 or max(_distance(b, a, d), _distance(c, a, d)) <= FLATNESS_MM:
        return [d]
    middle = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    ab, bc, cd = middle(a, b), middle(b, c), middle(c, d)
    abc, bcd = middle(ab, bc), middle(bc, cd)
    center = middle(abc, bcd)
    return _flatten_cubic(a, ab, abc, center, depth + 1) + _flatten_cubic(center, bcd, cd, d, depth + 1)


def _points(subpath):
    """Flatten SVG curves for verification; preserve their original SVG text."""
    tokens = TOKENS.findall(subpath)
    points, cursor, current, start, command, control = [], 0, (0., 0.), None, None, None
    vertices = []
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2}
    previous = None
    while cursor < len(tokens):
        if tokens[cursor].isalpha():
            command, cursor = tokens[cursor], cursor + 1
            if command.upper() == "Z":
                if start is not None:
                    points.append(start)
                    vertices.append(start)
                    current = start
                previous, control = "Z", None
                continue
        if command is None or command.upper() not in counts:
            raise ValueError("Unsupported SVG rail command")
        kind = command.upper()
        count = counts[kind]
        values = [float(v) for v in tokens[cursor:cursor + count]]
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise ValueError("Incomplete/nonfinite rail coordinates")
        cursor += count
        relative = command.islower()
        point = lambda x, y: (x + (current[0] if relative else 0), y + (current[1] if relative else 0))
        if kind in {"M", "L"}:
            end = point(*values)
            points.append(end)
            if kind == "M":
                start = end
                command = "l" if relative else "L"
            control = None
        elif kind in {"H", "V"}:
            end = ((values[0] + (current[0] if relative else 0), current[1]) if kind == "H" else
                   (current[0], values[0] + (current[1] if relative else 0)))
            points.append(end)
            control = None
        elif kind in {"C", "S"}:
            if kind == "C":
                first, second, end = point(*values[:2]), point(*values[2:4]), point(*values[4:])
            else:
                first = ((2 * current[0] - control[0], 2 * current[1] - control[1])
                         if previous in {"C", "S"} and control is not None else current)
                second, end = point(*values[:2]), point(*values[2:])
            points.extend(_flatten_cubic(current, first, second, end))
            control = second
        else:
            if kind == "Q":
                quadratic, end = point(*values[:2]), point(*values[2:])
            else:
                quadratic = ((2 * current[0] - control[0], 2 * current[1] - control[1])
                             if previous in {"Q", "T"} and control is not None else current)
                end = point(*values)
            first = (current[0] + (quadratic[0] - current[0]) * 2 / 3,
                     current[1] + (quadratic[1] - current[1]) * 2 / 3)
            second = (end[0] + (quadratic[0] - end[0]) * 2 / 3,
                      end[1] + (quadratic[1] - end[1]) * 2 / 3)
            points.extend(_flatten_cubic(current, first, second, end))
            control = quadratic
        vertices.append(end)
        current, previous = end, kind
    return _Rail([p for i, p in enumerate(points) if not i or math.dist(p, points[i - 1]) > 1e-10], vertices)


def _crossings(guide, rail):
    a, b = guide
    dx, dy = b[0] - a[0], b[1] - a[1]
    points = set()
    for c, d in zip(rail, rail[1:]):
        ex, ey = d[0] - c[0], d[1] - c[1]
        denominator = dx * ey - dy * ex
        if abs(denominator) < 1e-12:
            if abs((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) < 1e-10:
                length = dx * dx + dy * dy
                if length:
                    t1 = ((c[0] - a[0]) * dx + (c[1] - a[1]) * dy) / length
                    t2 = ((d[0] - a[0]) * dx + (d[1] - a[1]) * dy) / length
                    if min(1., max(t1, t2)) - max(0., min(t1, t2)) > 1e-10:
                        return {tuple(c), tuple(d)}
            continue
        t = ((c[0] - a[0]) * ey - (c[1] - a[1]) * ex) / denominator
        u = ((c[0] - a[0]) * dy - (c[1] - a[1]) * dx) / denominator
        if -1e-10 <= t <= 1 + 1e-10 and -1e-10 <= u <= 1 + 1e-10:
            points.add((round(a[0] + t * dx, 10), round(a[1] + t * dy, 10)))
    return points


def _valid_guide(guide, rails):
    if len(guide) != 2 or math.dist(*guide) < .001:
        return False
    for rail in rails:
        crossings = _crossings(guide, rail)
        if len(crossings) != 1:
            return False
        crossing = next(iter(crossings))
        # Avoid adjacent-segment vertex intersections that native curve
        # flattening can report as multiple intersections after splitting.
        if min(math.dist(crossing, vertex) for vertex in getattr(rail, "vertices", rail)) < VERTEX_CLEARANCE_MM:
            return False
    return True


def _at_fraction(rail, fraction):
    lengths = [math.dist(a, b) for a, b in zip(rail, rail[1:])]
    remaining = sum(lengths) * fraction
    for (a, b), length in zip(zip(rail, rail[1:]), lengths):
        if remaining <= length:
            t = remaining / length
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        remaining -= length
    return rail[-1]


def _replacement(rails, existing):
    for guide in existing:
        if _valid_guide(guide, rails):
            return guide, "existing_verified"
    left, right = rails
    if (math.dist(left[0], right[0]) + math.dist(left[-1], right[-1]) >
            math.dist(left[0], right[-1]) + math.dist(left[-1], right[0])):
        right = list(reversed(right))
    fractions = sorted((i / 257 for i in range(1, 257)), key=lambda f: abs(f - .5))
    for fraction in fractions:
        a, b = _at_fraction(left, fraction), _at_fraction(right, fraction)
        length = math.dist(a, b)
        if not length:
            continue
        dx, dy = (b[0] - a[0]) / length * GUIDE_EXTENSION_MM, (b[1] - a[1]) / length * GUIDE_EXTENSION_MM
        guide = [(a[0] - dx, a[1] - dy), (b[0] + dx, b[1] + dy)]
        if _valid_guide(guide, rails):
            return guide, "interior_arclength_crossing"
    return None, None


def cleanup(root):
    """Normalize derived native guides, or fail before unsafe machine export."""
    metadata = {"satin_columns": 0, "rewritten_columns": 0, "removed_guides": 0,
                "rails_preserved": True, "methods": {}}
    for node in root.iter(SVG + "path"):
        if node.get(IS + "satin_column", "").lower() != "true":
            continue
        metadata["satin_columns"] += 1
        subpaths = SUBPATH.findall(node.get("d", ""))
        if len(subpaths) < 2:
            _fail(node, "Fewer than two native rail subpaths")
        try:
            rails = [_points(part) for part in subpaths[:2]]
            existing = [_points(part) for part in subpaths[2:]]
            if any(len(rail) < 2 for rail in rails):
                _fail(node, "Degenerate native rail")
            guide, method = _replacement(rails, existing)
        except (ValueError, IndexError, OverflowError) as exc:
            _fail(node, str(exc))
        if guide is None:
            _fail(node, "No single unambiguous guide crossing both rails")
        metadata["methods"][method] = metadata["methods"].get(method, 0) + 1
        if len(existing) == 1 and method == "existing_verified":
            continue
        a, b = guide
        direction = f"M {a[0]:.9f},{a[1]:.9f} L {b[0]:.9f},{b[1]:.9f}"
        node.set("d", subpaths[0] + subpaths[1] + " " + direction)
        metadata["rewritten_columns"] += 1
        metadata["removed_guides"] += max(0, len(existing) - 1)
    return metadata
