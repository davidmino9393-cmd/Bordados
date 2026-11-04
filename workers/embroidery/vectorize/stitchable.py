"""Qué parte de la geometría de E1 se puede bordar: se quita lo que ninguna aguja forma y se avisa de lo omitido.

E1 reproduce la máscara de píxeles sin juzgar si se puede coser. Un degradado o el ruido de un JPEG dejan miles de
manchas de unas pocas décimas de milímetro (en Anime Socks, ~4000 en un solo color), una capa casi blanca que es el
resplandor del fondo y no un hilo, y contornos en escalera de decenas de miles de puntos. Ink/Stitch trata cada mancha
por separado (con cortes y remates) y tarda minutos en los contornos. Este paso no cambia el documento de E1: decide
qué entra en el SVG para puntadas, simplifica los contornos y deja la cuenta de lo que cambió.
"""
from dataclasses import dataclass
import re

# ≈ 1 mm de lado: el ancho mínimo publicado de un satin (tests/calibration/h3/REFERENCIAS_JANOME_MC550E.md, §5).
MIN_STITCHABLE_AREA_MM2 = 1.0
# Una capa cuyo color tiene todos los canales por encima de esto se toma como fondo y no se borda.
NEAR_WHITE_MIN_CHANNEL = 240
# La resolución del JEF es 0,1 mm: un contorno más fino que eso se pierde igual al exportar.
SIMPLIFY_TOLERANCE_MM = 0.1
# Un borde en diagonal de la máscara es una escalera cuyas esquinas quedan a 0,71 px de la recta: con menos que eso
# no se alisa. Dentro de media a un píxel el borde ya era incierto, así que la tolerancia sube con el tamaño del píxel.
SIMPLIFY_PIXEL_FRACTION = 0.75
MIN_RING_POINTS = 4
OUTPUT_DECIMALS = 3
OMITTED_NEAR_WHITE = "near_white_layer_taken_as_background"
OMITTED_TOO_SMALL = "no_stitchable_area"

_SUBPATH = re.compile(r"M[^M]*")
_POINT = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
_HEX_CHANNEL = 2


@dataclass(frozen=True)
class StitchableObject:
    object_id: str
    path_data_mm: str | None  # None: el objeto entero se omite
    omitted: str | None
    loops: int
    removed_loops: int
    total_area_mm2: float
    removed_area_mm2: float
    points: int  # todos los puntos de E1 en este objeto
    kept_points_before: int  # los de los contornos que se quedan, antes de simplificar
    kept_points: int  # y después
    tolerance_mm: float

    @property
    def simplified(self):
        return self.kept_points < self.kept_points_before

    @property
    def changed(self):
        """Algo del objeto no llegó tal cual al bordado: se omitió, se quitaron manchas o se simplificó el contorno."""
        return self.omitted is not None or self.removed_loops > 0 or self.simplified


def _points(subpath):
    return [(float(x), float(y)) for x, y in _POINT.findall(subpath)]


def ring_area_mm2(points):
    if len(points) < 3:
        return 0.0
    twice = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]))
    return abs(twice) / 2


def _distance_squared(point, start, end):
    """Distancia al SEGMENTO (no a la recta infinita): un punto más allá de un extremo mide hasta ese extremo.

    Con la recta, un contorno que se aleja por la misma dirección de la cuerda y vuelve se daba por «cerca» y se perdía.
    """
    (x, y), (x1, y1), (x2, y2) = point, start, end
    dx, dy = x2 - x1, y2 - y1
    length_squared = dx * dx + dy * dy
    along = 0.0 if length_squared == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_squared))
    return (x - (x1 + along * dx)) ** 2 + (y - (y1 + along * dy)) ** 2


def _simplify_chain(chain, tolerance_squared):
    """Douglas-Peucker iterativo: un contorno de 50 000 puntos no cabe en la recursión de Python."""
    last = len(chain) - 1
    keep = [False] * len(chain)
    keep[0] = keep[last] = True
    stack = [(0, last)]
    while stack:
        first, final = stack.pop()
        start, end = chain[first], chain[final]
        worst, index = tolerance_squared, -1
        for position in range(first + 1, final):
            distance = _distance_squared(chain[position], start, end)
            if distance > worst:
                worst, index = distance, position
        if index >= 0:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, final))
    return [point for point, kept in zip(chain, keep) if kept]


def simplify_ring(points, tolerance=SIMPLIFY_TOLERANCE_MM):
    """Contorno cerrado sin punto repetido; ningún punto original queda a más de `tolerance` del resultado."""
    if len(points) <= MIN_RING_POINTS:
        return list(points)
    tolerance_squared = tolerance * tolerance
    anchor = max(range(len(points)), key=lambda i: (points[i][0] - points[0][0]) ** 2 + (points[i][1] - points[0][1]) ** 2)
    first = _simplify_chain(points[:anchor + 1], tolerance_squared)
    second = _simplify_chain(points[anchor:] + points[:1], tolerance_squared)
    return first[:-1] + second[:-1]


def _number(value):
    return f"{value:.{OUTPUT_DECIMALS}f}".rstrip("0").rstrip(".") or "0"


def _format_ring(points):
    commands = [f"M{_number(points[0][0])},{_number(points[0][1])}"]
    commands.extend(f"L{_number(x)},{_number(y)}" for x, y in points[1:])
    return " ".join(commands) + " Z"


def is_near_white(color):
    channels = [int(color[1 + index * _HEX_CHANNEL: 1 + (index + 1) * _HEX_CHANNEL], 16) for index in range(3)]
    return min(channels) >= NEAR_WHITE_MIN_CHANNEL


def tolerance_for(document):
    """Tolerancia de simplificación en mm: la mayor entre 0,1 mm y 3/4 de píxel (escala uniforme de E1)."""
    affine = document.coordinates.source_px_to_mm
    pixel_mm = abs(affine[0]) if affine else 0.0
    return max(SIMPLIFY_TOLERANCE_MM, SIMPLIFY_PIXEL_FRACTION * pixel_mm)


def plan_object(obj, tolerance=SIMPLIFY_TOLERANCE_MM):
    rings = [_points(subpath) for subpath in _SUBPATH.findall(obj.path_data_mm)]
    areas = [ring_area_mm2(ring) for ring in rings]
    total, points = sum(areas), sum(len(ring) for ring in rings)
    whole = dict(object_id=obj.object_id, path_data_mm=None, loops=len(rings), removed_loops=len(rings), total_area_mm2=total,
                 removed_area_mm2=total, points=points, kept_points_before=0, kept_points=0, tolerance_mm=tolerance)
    if is_near_white(obj.work_color):
        return StitchableObject(**whole, omitted=OMITTED_NEAR_WHITE)
    large = [ring for ring, area in zip(rings, areas) if area >= MIN_STITCHABLE_AREA_MM2]
    kept = [ring for ring in (simplify_ring(ring, tolerance) for ring in large) if len(ring) >= 3]
    if not kept:
        return StitchableObject(**whole, omitted=OMITTED_TOO_SMALL)
    return StitchableObject(
        object_id=obj.object_id, path_data_mm=" ".join(_format_ring(ring) for ring in kept), omitted=None, loops=len(rings),
        removed_loops=len(rings) - len(kept), total_area_mm2=total,
        removed_area_mm2=sum(area for area in areas if area < MIN_STITCHABLE_AREA_MM2), points=points,
        kept_points_before=sum(len(ring) for ring in large), kept_points=sum(len(ring) for ring in kept), tolerance_mm=tolerance)


def plan(document):
    tolerance = tolerance_for(document)
    return tuple(plan_object(obj, tolerance) for obj in document.objects)


def evidence(planned):
    return {
        "min_stitchable_area_mm2": MIN_STITCHABLE_AREA_MM2, "near_white_min_channel": NEAR_WHITE_MIN_CHANNEL,
        "simplify_tolerance_mm": round(planned[0].tolerance_mm, 4) if planned else SIMPLIFY_TOLERANCE_MM,
        "objects": {
            item.object_id: {
                "loops": item.loops, "removed_loops": item.removed_loops, "omitted": item.omitted,
                "total_area_mm2": round(item.total_area_mm2, 2), "removed_area_mm2": round(item.removed_area_mm2, 2),
                "points": item.points, "kept_points_before_simplification": item.kept_points_before,
                "kept_points": item.kept_points, "simplified": item.simplified, "simplify_tolerance_mm": round(item.tolerance_mm, 4),
            } for item in planned
        },
    }
