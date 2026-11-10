"""Guía 1.3: el texto en curva de un sello se borda con una fuente de Ink/Stitch en lugar del trazo copiado de la imagen.

En letras de 2-3 mm el trazo copiado pierde esquinas y patas (El Fortín: D como O, L como «(», I faltantes). La persona
confirma la frase y elige bordarla con letras: se quitan del SVG de referencia las piezas de esa frase en su arco y se
componen los glifos de la fuente sobre el mismo arco, a la misma altura y con el mismo recorrido angular.

La fuente se lee de la instalación de Ink/Stitch (no se copia al repositorio). Sus glifos traen columnas de satén y
parámetros propios; sus unidades son px de 1/96 pulgada con la línea de base en y = `units_per_em`.
"""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from vectorize import stitchable
from vectorize.reference_geometry import _components

FONT_ID = "glacial_tiny"
FONT_THREAD = "La fuente glacial_tiny pide hilo 60 y aguja 60/8; con hilo 40 probá antes en un retazo."
PX_MM = 25.4 / 96
CAP_GLYPH = "M"
# Una letra es una pieza chica dentro de la corona del sello; el anillo y el dibujo central no lo son.
LETTER_ZONE = (0.5, 1.02)            # fracción del radio del círculo detectado
MAX_LETTER_SHARE = 0.25              # alto radial máximo de una letra respecto del radio
MIN_LETTER_SHARE = 0.04              # una letra mide al menos esto del radio; menos es tilde, guion o borde de antialias
RING_MIN_POINTS = 40                 # un contorno con menos nodos no define bien un círculo
RING_RADIUS_SHARE = 0.10             # el borde del anillo usado de referencia mide el radio detectado ±10 %
RING_ROUNDNESS_SHARE = 0.02          # y ningún nodo se aparta del círculo ajustado más que esto del radio
CENTRE_SHIFT_SHARE = 0.05            # el ajuste no puede mover el centro más que esto del radio
TEXT_ROW_SHARE = 0.04                # las letras de una frase en curva están a este radio de la fila más poblada
MAX_LETTER_ANGLE_DEG = 40.0
MIN_LETTERS = 3
BAND_GROWTH = 0.15                   # la franja de la frase crece este tanto de la altura de letra a cada lado
MARGIN_MM = 0.15                     # distancia de las letras (con tilde) al borde del lugar libre

SVG = "http://www.w3.org/2000/svg"
IS = "http://inkstitch.org/namespace"
INK = "http://www.inkscape.org/namespaces/inkscape"
TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")
for _prefix, _namespace in (("", SVG), ("inkstitch", IS), ("inkscape", INK)):
    ET.register_namespace(_prefix, _namespace)


class LetteringUnavailable(Exception):
    """La frase no se pudo bordar con letras; el motivo es para la persona."""


@dataclass(frozen=True)
class ArcText:
    object_id: str
    color: str
    rings: frozenset
    first_deg: float          # centro de la primera letra, en orden de lectura
    last_deg: float
    inner_mm: float           # radios de las piezas de la frase
    outer_mm: float
    letter_mm: float          # alto típico de letra
    centre: tuple             # centro del sello ajustado al borde del anillo, en mm
    free_inner_mm: float      # lugar libre para las letras: hasta el dibujo más cercano (los anillos del sello)
    free_outer_mm: float


def font_directory(inkstitch_exe):
    """`.../inkstitch/bin/inkstitch.exe` -> `.../inkstitch/fonts/<fuente>`."""
    return Path(inkstitch_exe).resolve().parents[1] / "fonts" / FONT_ID


def _absolute(d):
    """Comandos de un trazo SVG en coordenadas absolutas (M, L, C, Z); acepta M L H V C S Q Z en mayúscula o minúscula."""
    tokens, i, cur, start, cmd, output = TOKEN.findall(d), 0, (0., 0.), (0., 0.), None, []
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd, i = tokens[i], i + 1
        rel, kind = cmd.islower(), cmd.upper()

        def point(k):
            x, y = float(tokens[i + 2 * k]), float(tokens[i + 2 * k + 1])
            return (cur[0] + x, cur[1] + y) if rel else (x, y)
        if kind == "Z":
            output.append(("Z", ()))
            cur = start
        elif kind in "ML":
            cur, i = point(0), i + 2
            output.append((kind, (cur,)))
            if kind == "M":
                start, cmd = cur, "l" if rel else "L"
        elif kind in "HV":
            value, i = float(tokens[i]), i + 1
            axis = 0 if kind == "H" else 1
            cur = tuple(value + (cur[a] if rel else 0) if a == axis else cur[a] for a in (0, 1))
            output.append(("L", (cur,)))
        elif kind == "C":
            points, i = (point(0), point(1), point(2)), i + 6
            output.append(("C", points))
            cur = points[2]
        elif kind == "S":
            b, c = point(0), point(1)
            i += 4
            last = output[-1] if output and output[-1][0] == "C" else None
            a = (2 * cur[0] - last[1][1][0], 2 * cur[1] - last[1][1][1]) if last else cur
            output.append(("C", (a, b, c)))
            cur = c
        elif kind == "Q":
            q, c = point(0), point(1)
            i += 4
            output.append(("C", ((cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1])),
                                 (c[0] + 2 / 3 * (q[0] - c[0]), c[1] + 2 / 3 * (q[1] - c[1])), c)))
            cur = c
        else:
            raise LetteringUnavailable(f"La fuente usa un trazo que no se puede ubicar ({cmd}).")
    return output


class Font:
    def __init__(self, directory):
        directory = Path(directory)
        try:
            self.meta = json.loads((directory / "font.json").read_text(encoding="utf-8"))
            root = ET.parse(directory / "→.svg").getroot()
        except (OSError, ValueError, ET.ParseError) as exc:
            raise LetteringUnavailable(f"No se encontró la fuente {FONT_ID} de Ink/Stitch.") from exc
        self.glyphs = {}
        for group in root.iter(f"{{{SVG}}}g"):
            label = group.get(f"{{{INK}}}label") or ""
            if label.startswith("GlyphLayer-"):
                self.glyphs[label[len("GlyphLayer-"):]] = [
                    (path, _absolute(path.get("d", ""))) for path in group.iter(f"{{{SVG}}}path")]
        self.baseline = float(self.meta.get("units_per_em", 32))
        self.cap = self.baseline - self._top([CAP_GLYPH])

    def _top(self, characters):
        return min(y for ch in characters for _, commands in self.glyphs[ch] for _, points in commands for _, y in points)

    def height(self, text):
        """Alto en unidades de la fuente desde la línea de base hasta lo más alto de la frase (tildes incluidas)."""
        return max(self.baseline - self._top(set(text) - {" "}), self.cap)

    def advance(self, ch):
        advances = self.meta.get("horiz_adv_x") or {}
        return advances.get(ch) or (self.meta["horiz_adv_x_space"] if ch == " " else self.meta["horiz_adv_x_default"])

    def kerning(self, a, b):
        return (self.meta.get("kerning_pairs") or {}).get(f"{a} {b}", 0)


def _angle(point, centre, middle):
    """Ángulo en grados (y hacia abajo) medido alrededor de la mitad del arco, sin el salto de ±180°."""
    value = math.degrees(math.atan2(point[1] - centre[1], point[0] - centre[0]))
    return (value - middle + 180) % 360 - 180 + middle


def _fit_circle(points):
    """Círculo por mínimos cuadrados (Kåsa): x² + y² + Dx + Ey + F = 0. None si los puntos no lo definen."""
    sums = [[0.] * 4 for _ in range(3)]
    for x, y in points:
        row, value = (x, y, 1.), -(x * x + y * y)
        for i in range(3):
            for j in range(3):
                sums[i][j] += row[i] * row[j]
            sums[i][3] += row[i] * value
    for col in range(3):  # Gauss con pivote parcial sobre el sistema 3x3
        pivot = max(range(col, 3), key=lambda r: abs(sums[r][col]))
        if abs(sums[pivot][col]) < 1e-9:
            return None
        sums[col], sums[pivot] = sums[pivot], sums[col]
        for r in range(3):
            if r != col:
                factor = sums[r][col] / sums[col][col]
                sums[r] = [a - factor * b for a, b in zip(sums[r], sums[col])]
    d, e, f = (sums[i][3] / sums[i][i] for i in range(3))
    return (-d / 2, -e / 2, math.sqrt(max(0., d * d / 4 + e * e / 4 - f)))


def _seal_centre(document, centre, radius):
    """Centro del sello ajustado al contorno más circular de su radio (el borde del anillo), no al círculo de Hough."""
    best = None
    for obj in document.objects:
        for _index, outer, holes in _components(obj.path_data_mm):
            for ring in (outer, *holes):
                if len(ring) < RING_MIN_POINTS:
                    continue
                fitted = _fit_circle(ring)
                if fitted is None or math.dist(fitted[:2], centre) > CENTRE_SHIFT_SHARE * radius:
                    continue
                error = max(abs(math.dist(fitted[:2], p) - fitted[2]) for p in ring)
                if abs(fitted[2] - radius) <= RING_RADIUS_SHARE * radius and error <= RING_ROUNDNESS_SHARE * radius:
                    if best is None or error < best[1]:
                        best = (fitted[:2], error)
    return best[0] if best else centre


def _pieces(document, centre, radius, arc):
    middle = -90. if arc == "top" else 90.
    found = {}
    for obj in document.objects:
        if stitchable.is_near_white(obj.work_color):
            continue
        for index, outer, _holes in _components(obj.path_data_mm):
            radii = [math.dist(centre, p) for p in outer]
            centroid = (sum(x for x, _ in outer) / len(outer), sum(y for _, y in outer) / len(outer))
            angles = [_angle(p, centre, middle) for p in outer]
            if (min(radii) < LETTER_ZONE[0] * radius or max(radii) > LETTER_ZONE[1] * radius
                    or max(radii) - min(radii) > MAX_LETTER_SHARE * radius
                    or max(angles) - min(angles) > MAX_LETTER_ANGLE_DEG
                    or (centroid[1] < centre[1]) != (arc == "top")):
                continue
            found.setdefault((obj.object_id, obj.work_color), []).append(
                {"index": index, "inner": min(radii), "outer": max(radii), "angle": _angle(centroid, centre, middle),
                 "centroid": centroid})
    return found


def find_arc_text(document, circle_mm, arc):
    """Las piezas de la frase de un arco: del alto de una letra, dentro de la corona y del color con más letras.

    El círculo detectado (Hough sobre el original) puede estar corrido unas décimas: el centro se ajusta al borde del
    anillo y la franja se mide con percentiles, no con la mediana de piezas sueltas.
    """
    radius = circle_mm[2]
    centre = _seal_centre(document, tuple(circle_mm[:2]), radius)
    candidates = _pieces(document, centre, radius, arc)
    letters = {key: [p for p in pieces if p["outer"] - p["inner"] >= MIN_LETTER_SHARE * radius]
               for key, pieces in candidates.items()}
    if not letters or max(len(v) for v in letters.values()) < MIN_LETTERS:
        raise LetteringUnavailable("No se encontraron las letras de la frase en el arco del sello.")
    # Las letras de la frase forman una fila a radio parejo; el dibujo del centro (caminos, agua) no.
    for pieces in letters.values():
        radii = sorted(math.dist(centre, p["centroid"]) for p in pieces)
        row = max(radii, key=lambda r: sum(abs(r - other) <= TEXT_ROW_SHARE * radius / 2 for other in radii)) if radii else 0
        pieces[:] = [p for p in pieces if abs(math.dist(centre, p["centroid"]) - row) <= TEXT_ROW_SHARE * radius]
    key, main = max(letters.items(), key=lambda item: len(item[1]))
    if len(main) < MIN_LETTERS:
        raise LetteringUnavailable("No se encontraron las letras de la frase en el arco del sello.")
    object_id, color = key
    inners, outers = sorted(p["inner"] for p in main), sorted(p["outer"] for p in main)
    trim = len(main) // 10
    inner, outer = inners[trim], outers[-1 - trim]
    letter = outer - inner
    angles = sorted(p["angle"] for p in main if p["inner"] >= inner - .5 * letter and p["outer"] <= outer + .5 * letter)
    first, last = (angles[0], angles[-1]) if arc == "top" else (angles[-1], angles[0])
    grow = BAND_GROWTH * letter
    free_inner, free_outer = _free_band(document, centre, arc, (angles[0], angles[-1]), inner, outer, grow)
    # Tildes y guiones: piezas chicas del mismo color en el lugar libre de la frase (una tilde queda fuera de la fila).
    rings = {str(p["index"]) for p in candidates[key]
             if p["inner"] >= free_inner and p["outer"] <= free_outer and angles[0] - 1 <= p["angle"] <= angles[-1] + 1}
    return ArcText(object_id, color, frozenset(rings), first, last, inner, outer, letter, centre, free_inner, free_outer)


def _free_band(document, centre, arc, angles, inner, outer, grow):
    """Hasta dónde pueden crecer las letras: el contorno largo más cercano (los anillos) adentro y afuera de la frase."""
    middle = -90. if arc == "top" else 90.
    below, above = [], []
    for obj in document.objects:
        if stitchable.is_near_white(obj.work_color):
            continue
        for _index, ring_outer, holes in _components(obj.path_data_mm):
            for ring in (ring_outer, *holes):
                spread = [_angle(p, centre, middle) for p in ring]
                if max(spread) - min(spread) <= 2 * MAX_LETTER_ANGLE_DEG:
                    continue  # solo los contornos largos (anillos, marcos) limitan; las piezas sueltas no
                # El borde de un anillo se mide por la mediana de su radio: los vértices extremos son dientes de antialias.
                radii = sorted(math.dist(centre, p) for p, a in zip(ring, spread) if angles[0] <= a <= angles[1])
                if radii:
                    r = radii[len(radii) // 2]
                    (below if r <= inner else above if r >= outer else []).append(r)
    # Sin anillos que la limiten, la frase solo crece un poco alrededor de las letras originales.
    return (max(below) if below else inner - grow), (min(above) if above else outer + grow)


def _glyph_paths(font, text, found, centre, arc):
    """Glifos sobre el arco: misma altura de letra, tildes dentro de la franja y el recorrido angular del original."""
    band = (found.free_inner_mm, found.free_outer_mm)
    height = font.height(text)
    # La altura de letra del original, nunca menos que el mínimo de la fuente, y la frase (tildes incluidas) en el lugar libre.
    fit = (band[1] - band[0] - 2 * MARGIN_MM) / height
    k = min(fit, max(found.letter_mm / font.cap, font.meta.get("min_scale", 0) * PX_MM))  # mm por unidad de la fuente
    scale = k / PX_MM
    if not font.meta.get("min_scale", 0) <= scale <= font.meta.get("max_scale", math.inf):
        raise LetteringUnavailable(
            f"La frase necesita la fuente al {scale:.0%} y {FONT_ID} admite de {font.meta['min_scale']:.0%} a "
            f"{font.meta['max_scale']:.0%}: el texto es demasiado chico o grande para bordarlo con letras.")
    slack = (band[1] - band[0] - height * k) / 2
    bottom = arc == "bottom"
    baseline = band[1] - slack if bottom else band[0] + slack
    advances = [font.advance(ch) * k for ch in text]
    kerns = [font.kerning(a, b) * k for a, b in zip(text, text[1:])] + [0.]
    centres = [sum(advances[:i]) + sum(kerns[:i]) + advances[i] / 2 for i in range(len(text))]
    span = abs(found.last_deg - found.first_deg) * math.pi / 180 * baseline
    tracking = (span - (centres[-1] - centres[0])) / max(1, len(text) - 1)
    paths = []
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        theta = math.radians(found.first_deg) + (-1 if bottom else 1) * (centres[i] - centres[0] + i * tracking) / baseline
        base = (centre[0] + baseline * math.cos(theta), centre[1] + baseline * math.sin(theta))
        right = (math.sin(theta), -math.cos(theta)) if bottom else (-math.sin(theta), math.cos(theta))
        up = (-math.cos(theta), -math.sin(theta)) if bottom else (math.cos(theta), math.sin(theta))
        origin = (base[0] - right[0] * advances[i] / 2, base[1] - right[1] * advances[i] / 2)

        def place(p, origin=origin, right=right, up=up):
            u, v = p[0] * k, (font.baseline - p[1]) * k
            return (origin[0] + right[0] * u + up[0] * v, origin[1] + right[1] * u + up[1] * v)
        for element, commands in font.glyphs[ch]:
            d = " ".join(c + "".join(f" {x:.4f},{y:.4f}" for x, y in map(place, pts)) for c, pts in commands)
            paths.append((i, element, d))
    return paths, {"scale": round(scale, 3), "cap_mm": round(font.cap * k, 3), "height_mm": round(height * k, 3),
                   "baseline_radius_mm": round(baseline, 3), "tracking_mm": round(tracking, 3)}


def apply(svg, document, phrases, font_dir):
    """Reemplaza cada frase confirmada (texto, círculo en mm, arco) por glifos de la fuente. Devuelve el SVG y la evidencia."""
    font = Font(font_dir)
    root = ET.fromstring(svg)
    evidence = []
    for text, circle_mm, arc in phrases:
        missing = sorted({ch for ch in text if ch != " " and ch not in font.glyphs})
        if missing:
            raise LetteringUnavailable(f"La fuente {FONT_ID} no tiene estos caracteres: {' '.join(missing)}.")
        found = find_arc_text(document, circle_mm, arc)
        paths, layout = _glyph_paths(font, text, found, found.centre, arc)
        removed = 0
        for node in list(root):
            if node.get("data-source-object-id") == found.object_id and node.get("data-source-ring-index") in found.rings:
                root.remove(node)
                removed += 1
        for number, (i, element, d) in enumerate(paths):
            attrs = {key: value for key, value in element.attrib.items() if key.startswith(f"{{{IS}}}")}
            satin = element.get(f"{{{IS}}}satin_column", "").lower() == "true"
            attrs.update({"id": f"lettering_{arc}_{number}", "d": d, "data-technique": "satin" if satin else "running",
                          "data-source-object-id": found.object_id, "data-component": f"lettering:{arc}:{i}",
                          "data-lettering-font": FONT_ID,
                          "style": f"fill:none;stroke:{found.color};stroke-width:0.1"})
            if not satin:
                attrs[f"{{{IS}}}stroke_method"] = "running_stitch"
            ET.SubElement(root, f"{{{SVG}}}path", attrs)
        evidence.append({"text": text, "arc": arc, "font": FONT_ID, "object_id": found.object_id,
                         "pieces_replaced": len(found.rings), "paths_removed": removed, "glyph_paths": len(paths), **layout})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), evidence


def circle_to_mm(document, circle_px):
    """El círculo detectado en el original, en mm del documento (la limpieza de paleta conserva el tamaño en px)."""
    a, b, c, d, e, f = document.coordinates.source_px_to_mm
    x, y, r = circle_px
    return (a * x + c * y + e, b * x + d * y + f, r * math.hypot(a, b))
