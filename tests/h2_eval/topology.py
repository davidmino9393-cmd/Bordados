"""Topología medida sobre máscaras (solo Pillow): componentes y huecos, con su área.

Un hueco es un trozo de fondo (4-conexo) que no toca el borde de la imagen; los componentes del primer plano son
8-conexos. Se etiqueta por tramos horizontales (run-length) con unión-búsqueda, sin numpy.
"""
import re

from PIL import Image, ImageChops

RUN = re.compile(rb"\xff+")
AREA_BINS = (1, 4, 16, 64)  # un hueco "cuenta" desde ese número de píxeles
DARK_LUMA_THRESHOLDS = (230, 215, 192, 128)


def _find(parent, index):
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def analyze(mask, eight):
    """Lista de (área, toca_borde) de cada componente de los píxeles 255 de `mask` (modo 'L')."""
    width, height = mask.size
    data = mask.tobytes()
    rows, parent, areas, touches = [], [], [], []
    reach = 1 if eight else 0  # 8-conexo: los tramos que se tocan en diagonal también se unen
    for y in range(height):
        row = []
        for match in RUN.finditer(data, y * width, (y + 1) * width):
            start, end = match.start() - y * width, match.end() - y * width
            index = len(parent)
            parent.append(index)
            areas.append(end - start)
            touches.append(y in (0, height - 1) or start == 0 or end == width)
            row.append((start, end, index))
        if rows:
            above, cursor = rows[-1], 0
            for start, end, index in row:
                while cursor < len(above) and above[cursor][1] + reach <= start:
                    cursor += 1
                probe = cursor
                while probe < len(above) and above[probe][0] < end + reach:
                    a, b = _find(parent, index), _find(parent, above[probe][2])
                    if a != b:
                        parent[b] = a
                        areas[a] += areas[b]
                        touches[a] = touches[a] or touches[b]
                    probe += 1
        rows.append(row)
    return [(areas[i], touches[i]) for i in range(len(parent)) if _find(parent, i) == i]


def topology(mask):
    """Componentes del primer plano y huecos (fondo 4-conexo que no toca el borde), con sus áreas."""
    components = [area for area, _ in analyze(mask, eight=True)]
    holes = [area for area, border in analyze(ImageChops.invert(mask), eight=False) if not border]
    return {"components": sorted(components, reverse=True), "holes": sorted(holes, reverse=True)}


def summary(shape):
    """Conteos por tamaño mínimo; las listas completas no se guardan."""
    return {
        "components": {f">={n}px": sum(1 for a in shape["components"] if a >= n) for n in AREA_BINS},
        "holes": {f">={n}px": sum(1 for a in shape["holes"] if a >= n) for n in AREA_BINS},
    }


def dark_mask(image, threshold):
    """Máscara 255 donde la luminancia del RGB es menor que `threshold`."""
    return image.convert("L").point(lambda value: 255 if value < threshold else 0)


def blank(size):
    return Image.new("L", size, 0)
