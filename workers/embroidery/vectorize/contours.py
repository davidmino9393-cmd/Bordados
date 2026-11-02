"""Exact directed pixel edges, with right-turn tracing at diagonal contacts."""
from array import array
from dataclasses import dataclass

from embroidery_contracts import IssueCode
from .segmentation import BACKGROUND
from .types import check_cancel, fail

# Adjacencies use one byte per vertex and one uint32 per edge. The cap also
# bounds the Python tuples needed for the returned, exact polygon vertices.
MAX_BOUNDARY_EDGES = 500_000
EDGE_CANCEL_INTERVAL = 1024
TURN_PRIORITY = {1: 0, 0: 1, 3: 2, 2: 3}
# At a shared vertex, outgoing edges were inserted from NW, NE, SW, SE pixels.
FIRST_DIRECTION_PRIORITY = {2: 0, 3: 1, 1: 2, 0: 3}


@dataclass(frozen=True)
class MaskContours:
    color: str
    loops: tuple
    pixel_count: int
    bounds: tuple
    edge_count: int
    holes: int


def contours(segmented, cancel):
    labels, width, height = segmented.labels, segmented.width, segmented.height
    edges = {label: array("I") for label in segmented.palette}
    pending = bytearray((width + 1) * (height + 1))
    counts = dict.fromkeys(edges, 0)
    boundary_counts = dict.fromkeys(edges, 0)
    bounds = {label: [width, height, 0, 0] for label in edges}
    edge_count = 0
    for y in range(height):
        if y % 16 == 0:
            check_cancel(cancel)
        for x in range(width):
            index = y * width + x
            label = labels[index]
            if label == BACKGROUND:
                continue
            counts[label] += 1
            box = bounds[label]
            box[0], box[1] = min(box[0], x), min(box[1], y)
            box[2], box[3] = max(box[2], x + 1), max(box[3], y + 1)
            vertex = y * (width + 1) + x
            candidates = (
                (y == 0 or labels[index - width] != label, vertex, vertex + 1, 0),
                (x == width - 1 or labels[index + 1] != label, vertex + 1, vertex + width + 2, 1),
                (y == height - 1 or labels[index + width] != label, vertex + width + 2, vertex + width + 1, 2),
                (x == 0 or labels[index - 1] != label, vertex + width + 1, vertex, 3),
            )
            for exposed, start, end, direction in candidates:
                if exposed:
                    if not _choices(start, pending, labels, label, width, height):
                        edges[label].append(start)
                    pending[start] |= 1 << direction
                    edge_count += 1
                    boundary_counts[label] += 1
            if edge_count > MAX_BOUNDARY_EDGES:
                fail(IssueCode.GEOMETRY_INVALID, "La máscara excede el límite de complejidad de E1.", "boundary_edge_limit", limit=MAX_BOUNDARY_EDGES)
    output = []
    for label in sorted(edges, key=lambda item: segmented.palette[item]):
        check_cancel(cancel)
        loops, count = _trace(edges[label], pending, labels, label, width, height, cancel)
        if count != boundary_counts[label]:
            fail(IssueCode.GEOMETRY_INVALID, "No se recorrieron todas las aristas de la máscara.", "untraced_pixel_boundary")
        holes = sum(signed_area(loop) < 0 for loop in loops)
        if sum(signed_area(loop) for loop in loops) != counts[label]:
            fail(IssueCode.GEOMETRY_INVALID, "Los contornos no reproducen el área de la máscara.", "mask_area_mismatch")
        output.append(MaskContours(segmented.palette[label], loops, counts[label], tuple(bounds[label]), count, holes))
    return tuple(output)


def _owner(vertex, direction, labels, width, height):
    x, y = vertex % (width + 1), vertex // (width + 1)
    if direction in (1, 2):
        x -= 1
    if direction in (2, 3):
        y -= 1
    return labels[y * width + x] if 0 <= x < width and 0 <= y < height else BACKGROUND


def _choices(vertex, pending, labels, label, width, height):
    return [direction for direction in range(4)
            if pending[vertex] & (1 << direction)
            and _owner(vertex, direction, labels, width, height) == label]


def _trace(edges, pending, labels, label, width, height, cancel):
    loops, processed = [], 0
    for start in edges:
        while _choices(start, pending, labels, label, width, height):
            loop, count = _trace_loop(start, pending, labels, label, width, height, cancel, processed)
            loops.append(_simplify(loop, cancel))
            processed += count
    return tuple(loops), processed


def _trace_loop(start, pending, labels, label, width, height, cancel, processed):
    stride = width + 1
    steps = (1, stride, -1, -stride)
    count = 0
    current, incoming, vertices = start, None, []
    while True:
        if (processed + count) % EDGE_CANCEL_INTERVAL == 0:
            check_cancel(cancel)
        vertices.append((current % stride, current // stride))
        choices = _choices(current, pending, labels, label, width, height)
        if not choices:
            fail(IssueCode.GEOMETRY_INVALID, "Se encontró un contorno abierto.", "open_pixel_boundary")
        direction = min(choices, key=FIRST_DIRECTION_PRIORITY.__getitem__) if incoming is None else min(choices, key=lambda item: TURN_PRIORITY[(item - incoming) % 4])
        pending[current] &= ~(1 << direction)
        current += steps[direction]
        incoming = direction
        count += 1
        if current == start:
            break
    return vertices, count


def _simplify(vertices, cancel):
    result = []
    count = len(vertices)
    for index, point in enumerate(vertices):
        if index % EDGE_CANCEL_INTERVAL == 0:
            check_cancel(cancel)
        previous, following = vertices[index - 1], vertices[(index + 1) % count]
        if (point[0] - previous[0], point[1] - previous[1]) != (following[0] - point[0], following[1] - point[1]):
            result.append(point)
    start = min(range(len(result)), key=lambda i: (result[i][1], result[i][0]))
    return tuple(result[start:] + result[:start])


def signed_area(loop):
    return sum(point[0] * loop[(index + 1) % len(loop)][1] - loop[(index + 1) % len(loop)][0] * point[1] for index, point in enumerate(loop)) / 2
