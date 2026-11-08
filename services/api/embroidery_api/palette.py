"""Orden 3.1: paleta honesta. Los halos de antialias se fusionan con su tinta ANTES de crear objetos.

Un límite de hilos es de hilos: el vectorizador cuantiza los píxeles a `color_limit` colores y, si la imagen trae el
borde suavizado de cada trazo (mezclas del color de la tinta con el blanco), esas mezclas compiten por los mismos
lugares que las tintas reales. Resultado medido en un logo de una tinta pedido con 3 hilos: 2 de los 3 "colores" eran
halos (decenas de miles de anillos de 1-3 px) y el segundo bloque de hilo salía sin una puntada.

Este módulo vive en la capa de la API y no toca el motor: devuelve un PNG con solo las tintas reales sobre blanco
(más la declaración de qué se hizo), y el runner se lo entrega al motor como imagen de entrada.

No es borrar geometría para aprobar un control: es limpieza de ruido de compresión, declarada como tal y con conteos.
Regla (determinista, sin ajustes por logo):
  1. Tintas = colores exactos más poblados que NO sean una mezcla `tinta -> blanco` de otra tinta más poblada
     (distancia RGB a ese segmento <= BLEND_TOLERANCE) ni un vecino a <= MERGE_RADIUS de una tinta. Un color con
     >= INTERIOR_MIN_PX píxeles lejos del fondo (a más de BAND_PX) es tinta real aunque caiga sobre un segmento
     (pero un vecino casi idéntico de otra tinta siempre se fusiona: es ruido de compresión).
  2. Si hay más tintas que `color_limit`, la menos poblada se fusiona con la tinta más cercana (se declara).
  3. Una tinta con < 1 % de la figura a <= MINOR_RADIUS de otra es una sombra de ruido y se fusiona (se declara).
  4. Cada píxel de la figura pasa a la tinta más cercana o al fondo, lo que sea más cerca en RGB: eso es la misma
     regla de cobertura del 50 % que usa el motor para el borde. Un píxel del interior (lejos del fondo) nunca se
     vuelve fondo.
"""
from dataclasses import dataclass, field
import hashlib
from io import BytesIO

from PIL import Image, ImageChops, ImageFilter

from vectorize.image_input import decode_raster
from vectorize.segmentation import _foreground

BLEND_TOLERANCE = 30.0
MERGE_RADIUS = 40.0
BAND_PX = 3
INTERIOR_MIN_PX = 64
NEAR_WHITE_MIN_CHANNEL = 235
MAX_DISTINCT_COLOURS = 300_000
MIN_COVERAGE = 0.02
MINOR_SHARE = 0.01
MINOR_RADIUS = 80.0
RULE = (
    f"tinta = color exacto dominante que no es mezcla tinta->blanco (tolerancia {BLEND_TOLERANCE:g} RGB) ni vecino "
    f"(radio {MERGE_RADIUS:g}); color con >= {INTERIOR_MIN_PX} px a mas de {BAND_PX} px del fondo es tinta real; "
    "cada pixel pasa a la tinta o al fondo mas cercano en RGB (cobertura 50 %); el interior nunca se vuelve fondo"
)


@dataclass(frozen=True)
class PaletteCleaning:
    applied: bool
    report: dict
    png: bytes | None = None
    sha256: str | None = None
    size: tuple[int, int] | None = None
    inks: tuple = field(default_factory=tuple)
    engine_colour_limit: int | None = None


def _skip(reason, **extra):
    return PaletteCleaning(False, {"applied": False, "reason": reason, "is_noise_cleanup_not_geometry_removal": True, **extra})


def _distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _blend_distance(colour, ink):
    """Distancia RGB de `colour` al segmento ink->blanco; infinita si no es más claro o la cobertura no es creíble."""
    direction = tuple(255 - channel for channel in ink)
    norm = sum(value * value for value in direction)
    if norm == 0:
        return float("inf")
    # colour ~ blanco - a * (blanco - ink)  =>  a por mínimos cuadrados.
    coverage = sum((255 - c) * d for c, d in zip(colour, direction)) / norm
    if not MIN_COVERAGE <= coverage <= 1.0:
        return float("inf")
    projected = tuple(255 - coverage * d for d in direction)
    return _distance(colour, projected)


def _colours(image, mask):
    plain = Image.new("RGB", image.size, (255, 255, 255))
    plain.paste(image, mask=mask)
    found = plain.getcolors(maxcolors=image.size[0] * image.size[1])
    return {colour: count for count, colour in found}


def _inks(counts, interior_counts):
    ordered = sorted((item for item in counts.items() if item[0] != (255, 255, 255)), key=lambda item: (-item[1], item[0]))
    inks, explained = [], {}
    for colour, count in ordered:
        if min(colour) >= NEAR_WHITE_MIN_CHANNEL and interior_counts.get(colour, 0) < INTERIOR_MIN_PX:
            explained[colour] = "near_white"
            continue
        real = interior_counts.get(colour, 0) >= INTERIOR_MIN_PX
        if any(_distance(colour, ink) <= MERGE_RADIUS for ink in inks):
            explained[colour] = "neighbour"
        elif not real and any(
            _blend_distance(colour, ink) <= BLEND_TOLERANCE and sum(colour) >= sum(ink) for ink in inks
        ):
            explained[colour] = "blend"
        else:
            inks.append(colour)
    return inks, explained


def _reduce(inks, counts, limit, foreground_pixels):
    merged = []
    inks = list(inks)
    # Una "tinta" con menos del 1 % de la figura y a <= MINOR_RADIUS de otra es una sombra de ruido (ringing de JPEG), no
    # un hilo; un acento de otro matiz (a más distancia) se conserva aunque sea chico.
    for colour in sorted(inks, key=lambda item: (counts[item], item)):
        others = [ink for ink in inks if ink != colour]
        if others and counts[colour] < MINOR_SHARE * foreground_pixels:
            target = min(others, key=lambda ink: (_distance(ink, colour), ink))
            if _distance(target, colour) <= MINOR_RADIUS and counts[target] > counts[colour]:
                inks.remove(colour)
                merged.append({"from": _hex(colour), "into": _hex(target), "pixels": counts[colour], "reason": "minor_shade"})
    while len(inks) > limit:
        smallest = min(inks, key=lambda colour: (counts[colour], colour))
        inks.remove(smallest)
        target = min(inks, key=lambda colour: (_distance(colour, smallest), colour))
        merged.append({"from": _hex(smallest), "into": _hex(target), "pixels": counts[smallest], "reason": "colour_limit"})
    return inks, merged


def _hex(colour):
    return "#%02x%02x%02x" % colour


def _palette_image(colours):
    flat = [channel for colour in colours for channel in colour]
    image = Image.new("P", (1, 1))
    image.putpalette(flat + [0] * (768 - len(flat)))
    return image


def _indices(rgb, colours):
    return Image.frombytes("L", rgb.size, rgb.quantize(palette=_palette_image(colours), dither=Image.Dither.NONE).tobytes())


def clean_palette(data, media_type, color_limit, cancel=None):
    """PNG con solo las tintas reales sobre blanco, o `applied=False` con el motivo (la imagen sigue tal cual)."""
    decoded = decode_raster(data, media_type, cancel)
    rgb, visible, evidence = _foreground(decoded.rgba)
    if not evidence["white_removed_globally"]:
        return _skip("fondo no blanco o con transparencia: el motor ya usa el alfa y no hay halos contra blanco que fusionar",
                     background_method=evidence["background_method"])
    foreground_pixels = visible.histogram()[255]
    if foreground_pixels == 0:
        return _skip("sin pixeles de figura")
    interior = visible.filter(ImageFilter.MinFilter(2 * BAND_PX + 1))
    counts = _colours(rgb, visible)
    if len(counts) > MAX_DISTINCT_COLOURS:
        return _skip("demasiados colores distintos (foto o degradado): no es un logo plano", distinct_colours=len(counts))
    interior_counts = _colours(rgb, interior)
    inks, explained = _inks(counts, interior_counts)
    if not inks:
        return _skip("sin tintas por encima del blanco")
    # Una capa casi blanca REAL (con cuerpo, no un halo) no es un hilo: el motor la toma como fondo y lo informa. No cuenta
    # contra el límite ni se fusiona con una tinta oscura; se conserva para que el motor la omita y la declare como siempre.
    pale = [ink for ink in inks if min(ink) >= NEAR_WHITE_MIN_CHANNEL]
    chromatic, merged = _reduce([ink for ink in inks if ink not in pale], counts, color_limit, foreground_pixels)
    inks = chromatic + pale
    colours = inks + [(255, 255, 255)]
    white_index = len(inks)
    nearest = _indices(rgb, colours)
    to_white = nearest.point(lambda value: 255 if value == white_index else 0)
    rescue = ImageChops.darker(ImageChops.darker(to_white, interior), visible)
    if rescue.getbbox() is not None:
        nearest = Image.composite(_indices(rgb, inks), nearest, rescue)
    nearest = Image.composite(nearest, Image.new("L", rgb.size, white_index), visible)
    cleaned = Image.frombytes("P", rgb.size, nearest.tobytes())
    cleaned.putpalette(_palette_image(colours).getpalette())
    buffer = BytesIO()
    cleaned.convert("RGB").save(buffer, format="PNG")
    png = buffer.getvalue()
    histogram = nearest.histogram()
    kept = {index: histogram[index] for index in range(len(inks))}
    removed = foreground_pixels - sum(kept.values())
    ink_hex = [_hex(colour) for colour in inks]
    by_rule = {"blend": 0, "near_white": 0, "neighbour": 0}
    for colour, rule in explained.items():
        by_rule[rule] += counts[colour]
    report = {
        "applied": True,
        "is_noise_cleanup_not_geometry_removal": True,
        "rule": RULE,
        "thresholds": {
            "blend_tolerance_rgb": BLEND_TOLERANCE, "merge_radius_rgb": MERGE_RADIUS, "band_px": BAND_PX,
            "interior_min_px": INTERIOR_MIN_PX, "minor_share": MINOR_SHARE, "minor_radius_rgb": MINOR_RADIUS, "near_white_min_channel": NEAR_WHITE_MIN_CHANNEL,
        },
        "colour_limit_requested": color_limit,
        "distinct_foreground_colours_before": len(counts),
        "inks_after": ink_hex,
        "ink_count_after": len(inks),
        "thread_inks_after": len(chromatic),
        "near_white_layers_kept_for_the_engine_to_omit": [_hex(ink) for ink in pale],
        "colours_merged_into_inks": len(counts) - len(inks),
        "colours_merged_by_rule": {rule: sum(1 for value in explained.values() if value == rule) for rule in by_rule},
        "pixels_of_merged_colours_by_rule": by_rule,
        "inks_merged": merged,
        "foreground_pixels_before": foreground_pixels,
        "foreground_pixels_after": sum(kept.values()),
        "foreground_pixels_returned_to_background": removed,
        "pixels_per_ink": {_hex(inks[index]): kept[index] for index in kept},
        "source_sha256": decoded.sha256,
        "cleaned_sha256": hashlib.sha256(png).hexdigest(),
        "visual_size_px": list(decoded.size),
    }
    return PaletteCleaning(True, report, png, report["cleaned_sha256"], decoded.size, tuple(ink_hex), len(inks))
