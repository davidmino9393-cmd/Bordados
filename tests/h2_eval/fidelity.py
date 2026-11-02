"""Fidelidad medida del documento de E contra los píxeles del original (solo Pillow, sin umbrales de aceptación).

Se redibuja cada objeto en la resolución del original con relleno par-impar (los huecos quedan vacíos) y se compara con el
original. El fondo se define aquí, aparte de E: píxel con alpha < ALPHA_BACKGROUND o con los tres canales >= WHITE_BACKGROUND.
Esa regla coincide con la que usa E1 hoy, así que el IoU NO valida la suposición de fondo blanco; solo mide cuánto del
resto del dibujo se conserva.
"""
import io
import math
import re

from PIL import Image, ImageChops, ImageStat

ALPHA_BACKGROUND = 128
WHITE_BACKGROUND = 250
LARGE_CHANNEL_ERROR = 64  # diferencia de canal a partir de la cual el color dibujado ya no se parece al original
TOKEN = re.compile(r"([MLZmlz])|(-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?),(-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?)")


def subpaths(path_data):
    """Lista de polígonos [(x, y), ...] de un `d` con solo M, L y Z (el único formato que emite E1)."""
    polygons, current = [], []
    for command, x, y in TOKEN.findall(path_data):
        if command.upper() == "M":
            if current:
                polygons.append(current)
            current = []
        elif command.upper() == "Z":
            if current:
                polygons.append(current)
            current = []
        elif x:
            current.append((float(x), float(y)))
    if current:
        polygons.append(current)
    return polygons


def inverse_affine(matrix):
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError("source_px_to_mm no es invertible")
    return d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det


def fill_even_odd(polygons, width, height):
    """Máscara 'L' (255 dentro) rellenando por filas, con el muestreo en el centro de cada píxel y regla par-impar."""
    rows = [[] for _ in range(height)]
    for polygon in polygons:
        for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
            if y1 == y2:
                continue
            low, high = (y1, y2) if y1 < y2 else (y2, y1)
            first, last = max(0, math.ceil(low - 0.5)), min(height, math.ceil(high - 0.5))
            slope = (x2 - x1) / (y2 - y1)
            for y in range(first, last):
                rows[y].append(x1 + (y + 0.5 - y1) * slope)
    data = bytearray(width * height)
    for y, crossings in enumerate(rows):
        crossings.sort()
        for left, right in zip(crossings[0::2], crossings[1::2]):
            start, end = max(0, math.ceil(left - 0.5)), min(width, math.ceil(right - 0.5))
            if end > start:
                data[y * width + start:y * width + end] = b"\xff" * (end - start)
    return Image.frombytes("L", (width, height), bytes(data))


def original_foreground(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    red, green, blue, alpha = image.split()
    white = ImageChops.darker(ImageChops.darker(red, green), blue).point(lambda v: 255 if v >= WHITE_BACKGROUND else 0)
    opaque = alpha.point(lambda v: 255 if v >= ALPHA_BACKGROUND else 0)
    return image.convert("RGB"), ImageChops.subtract(opaque, white)


def hex_to_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def measure(document, image_bytes):
    """Métricas de fidelidad (números medidos) del documento frente al original."""
    rgb, foreground = original_foreground(image_bytes)
    width, height = rgb.size
    matrix = document.coordinates.source_px_to_mm
    if matrix is None:
        raise ValueError("el documento no declara source_px_to_mm")
    a, b, c, d, e, f = inverse_affine(matrix)
    rendered = Image.new("L", (width, height), 0)
    colour = Image.new("RGB", (width, height), (255, 255, 255))
    for obj in document.objects:
        polygons = [[(a * x + c * y + e, b * x + d * y + f) for x, y in p] for p in subpaths(obj.path_data_mm)]
        mask = fill_even_odd(polygons, width, height)
        rendered.paste(255, mask=mask)
        colour.paste(hex_to_rgb(obj.work_color), mask=mask)
    both = ImageChops.darker(foreground, rendered)
    original_px, rendered_px, both_px = (m.histogram()[255] for m in (foreground, rendered, both))
    union = original_px + rendered_px - both_px
    difference = ImageChops.difference(rgb, colour)
    channel_sums = ImageStat.Stat(difference, mask=both).sum
    worst = ImageChops.lighter(ImageChops.lighter(*difference.split()[:2]), difference.split()[2])
    histogram = worst.histogram(mask=both)
    large = sum(histogram[LARGE_CHANNEL_ERROR:])
    cumulative, p95 = 0, 0
    for value, count in enumerate(histogram):
        cumulative += count
        if both_px and cumulative >= 0.95 * both_px:
            p95 = value
            break
    return {
        "foreground_iou": round(both_px / union, 6) if union else 1.0,
        "original_foreground_px": original_px, "rendered_px": rendered_px,
        "missing_px": original_px - both_px, "extra_px": rendered_px - both_px,
        "large_error_px": large, "large_error_fraction": round(large / both_px, 6) if both_px else None,
        "p95_max_channel_error": p95, "large_error_threshold": LARGE_CHANNEL_ERROR,
        "mean_abs_rgb_error": round(sum(channel_sums) / (3 * both_px), 4) if both_px else None,
        "background_rule": f"alpha<{ALPHA_BACKGROUND} o RGB>={WHITE_BACKGROUND}",
    }
