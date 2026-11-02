"""Exact directed pixel edges, with right-turn tracing at diagonal contacts."""
from collections import defaultdict
from dataclasses import dataclass

from embroidery_contracts import IssueCode
from .segmentation import BACKGROUND
from .types import check_cancel, fail

MAX_BOUNDARY_EDGES = 250_000
EDGE_CANCEL_INTERVAL = 1024
TURN_PRIORITY = {1: 0, 0: 1, 3: 2, 2: 3}


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
    edges = {label: defaultdict(list) for label in segmented.palette}
    counts = dict.fromkeys(edges, 0)
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
                    edges[label][start].append((end, direction))
                    edge_count += 1
            if edge_count > MAX_BOUNDARY_EDGES:
                fail(IssueCode.GEOMETRY_INVALID, "La máscara excede el límite de complejidad de E1.", "boundary_edge_limit", limit=MAX_BOUNDARY_EDGES)
    output = []
    for label in sorted(edges, key=lambda item: segmented.palette[item]):
        check_cancel(cancel)
        loops, count = _trace(edges[label], width + 1, cancel)
        holes = sum(signed_area(loop) < 0 for loop in loops)
        if sum(signed_area(loop) for loop in loops) != counts[label]:
            fail(IssueCode.GEOMETRY_INVALID, "Los contornos no reproducen el área de la máscara.", "mask_area_mismatch")
        output.append(MaskContours(segmented.palette[label], loops, counts[label], tuple(bounds[label]), count, holes))
    return tuple(output)


def _trace(edges, stride, cancel):
    loops, processed = [], 0
    while edges:
        # Dict insertion order follows the source raster scan, with no set iteration.
        start = next(iter(edges))
        current, incoming, vertices = start, None, []
        while True:
            if processed % EDGE_CANCEL_INTERVAL == 0:
                check_cancel(cancel)
            vertices.append((current % stride, current // stride))
            choices = edges.get(current)
            if not choices:
                fail(IssueCode.GEOMETRY_INVALID, "Se encontró un contorno abierto.", "open_pixel_boundary")
            chosen = 0 if incoming is None else min(range(len(choices)), key=lambda i: TURN_PRIORITY[(choices[i][1] - incoming) % 4])
            following, incoming = choices.pop(chosen)
            if not choices:
                del edges[current]
            current = following
            processed += 1
            if current == start:
                break
        loops.append(_simplify(vertices, cancel))
    return tuple(loops), processed


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
