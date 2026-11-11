"""Orden 3.2 y 3.4: aviso de legibilidad ANTES de vectorizar, con números. No bloquea: avisa y mide.

Se mide el ancho de trazo de la tinta al tamaño final pedido, sobre los mismos píxeles que va a trazar el motor (la imagen ya
con los halos fusionados, `palette.clean_palette`). Método: aperturas morfológicas con un elemento cuadrado de lado 2r+1
(erosión + dilatación 3x3 repetidas) sobre una máscara remuestreada a una grilla de 0,05 mm o más gruesa (lado <= 1200 px); error de ancho ~ +-1 px de grilla. La tinta que la apertura de
radio r-1 conserva y la de radio r pierde tiene un ancho local de ~2r px. "Trazo" se pondera por LARGO (área / ancho): una
letra fina larga pesa lo que su recorrido, no lo que su área, que es lo que importa para leer texto. Se informa también la
fracción por área. Limitación declarada: con un elemento cuadrado, en trazos diagonales la finura se sobreestima hasta 1,41x.

OJO con la auditoría: sus "51,5 % < 0,6 mm" miden cuántos píxeles de tinta sobreviven k erosiones, o sea la banda de borde de
todo trazo (un trazo de 1,2 mm cuenta ~50 % como "fino"). Aquí se mide el ancho del trazo; los números son otros.
"""
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageFilter
from pydantic import BaseModel

from vectorize.image_input import decode_raster
from vectorize.inkstitch import REFERENCE_PULL_COMPENSATION_MM
from vectorize.segmentation import _foreground

from .palette import clean_palette

THIN_MM = 0.6                 # por debajo de esto un trazo no se borda con claridad
THIN_SHARE_WARN = 0.30        # se avisa si más de este porcentaje de la tinta queda por debajo de THIN_MM
LEGIBLE_MM = 0.8              # ancho al que se pide que llegue la mayoría del trazo
LEGIBLE_SHARE = 0.80          # "la mayoría": el 80 % de la tinta
WORK_MM = 0.05                # grilla de trabajo mínima
WORK_SIDE_PX = 1200           # la grilla se agranda para que el lado mayor no pase de esto
MAX_WIDTH_MM = 1.6            # trazos más anchos no se miden más: si el 20 % no baja de ahí, ya es legible
METHOD = (
    f"aperturas con elemento cuadrado (erosion+dilatacion 3x3) sobre la mascara de tinta remuestreada a >= {WORK_MM} mm; trazo "
    "ponderado por largo (area/ancho); en diagonales sobreestima la finura hasta 1,41x"
)


class MinimumSize(BaseModel):
    already_legible: bool
    scale_factor: float
    ink_width_mm: float
    ink_height_mm: float
    fits_in_hoop: bool | None
    message: str


class MarginOption(BaseModel):
    ink_bbox_px: tuple[int, int, int, int]
    gain_percent: float
    ink_width_mm_now: float
    ink_height_mm_now: float
    ink_width_mm_cropped: float
    ink_height_mm_cropped: float
    message: str


class LegibilityCheck(BaseModel):
    """Aviso previo a generar: números medidos al tamaño pedido; `warn` no bloquea nada."""
    schema_version: str = "0.1-legibility"
    requested_width_mm: float
    requested_height_mm: float
    ink_width_mm: float
    ink_height_mm: float
    thin_share_below_0_6_mm: float          # por largo de trazo
    thin_share_below_0_8_mm: float
    ink_area_share_below_0_6_mm: float
    warn: bool
    message: str | None
    minimum_size: MinimumSize
    margin_option: MarginOption | None
    palette_cleaning_applied: bool
    inks: list[str]
    method: str = METHOD


@dataclass(frozen=True)
class _Ink:
    mask: Image.Image          # "L" 0/255 a resolución nativa
    size: tuple[int, int]
    bbox: tuple[int, int, int, int]
    palette_applied: bool
    inks: tuple


def prepare(data, media_type, color_limit, cancel=None):
    """Máscara de tinta que va a trazar el motor (con halos ya fusionados si corresponde)."""
    cleaning = clean_palette(data, media_type, color_limit, cancel)
    source, kind = (cleaning.png, "image/png") if cleaning.applied else (data, media_type)
    decoded = decode_raster(source, kind, cancel)
    _rgb, visible, _evidence = _foreground(decoded.rgba)
    bbox = visible.getbbox()
    return _Ink(visible, decoded.size, bbox, cleaning.applied, cleaning.inks) if bbox else None


def _work_mask(ink, scale_mm_per_px):
    left, top, right, bottom = ink.bbox
    crop = ink.mask.crop(ink.bbox)
    side = max(right - left, bottom - top) * scale_mm_per_px
    work_mm = max(WORK_MM, side / WORK_SIDE_PX)
    width = max(1, round(crop.size[0] * scale_mm_per_px / work_mm))
    height = max(1, round(crop.size[1] * scale_mm_per_px / work_mm))
    resample = Image.Resampling.BOX if width < crop.size[0] else Image.Resampling.BILINEAR
    return crop.resize((width, height), resample).point(lambda value: 255 if value >= 128 else 0), work_mm


def _profile(mask, work_mm):
    """[(ancho_mm, fraccion_de_largo_mas_angosta, fraccion_de_area_mas_angosta)] por radio, de r=0 al último medido."""
    areas = [mask.histogram()[255]]
    eroded = mask
    for radius in range(1, max(1, round((MAX_WIDTH_MM / work_mm - 1) / 2)) + 1):
        eroded = eroded.filter(ImageFilter.MinFilter(3))
        opened = eroded
        for _ in range(radius):
            opened = opened.filter(ImageFilter.MaxFilter(3))
        areas.append(opened.histogram()[255])
        if areas[-1] == 0:
            break
    total = areas[0]
    classes = [(areas[r - 1] - areas[r], 2 * r) for r in range(1, len(areas))]
    lengths = [area / width for area, width in classes] + [areas[-1] / (2 * len(areas))]
    total_length = sum(lengths) or 1.0
    profile, length_sum, area_sum = [(work_mm, 0.0, 0.0)], 0.0, 0.0
    for radius, ((area, _width), length) in enumerate(zip(classes, lengths), start=1):
        length_sum += length
        area_sum += area
        profile.append(((2 * radius + 1) * work_mm, length_sum / total_length, area_sum / total))
    return profile


def _share(profile, width_mm, column):
    """Fracción de tinta más angosta que `width_mm`, interpolando entre radios (column 0 = por largo, 1 = por área)."""
    for (w0, *v0), (w1, *v1) in zip(profile, profile[1:]):
        if width_mm <= w1:
            t = (width_mm - w0) / (w1 - w0) if w1 > w0 else 1.0
            return v0[column] + max(0.0, t) * (v1[column] - v0[column])
    return profile[-1][1 + column]


def _width_at_share(profile, share):
    """Ancho (mm) por debajo del cual está `share` del trazo; None si el perfil medido no llega a ese porcentaje."""
    for (w0, l0, _a0), (w1, l1, _a1) in zip(profile, profile[1:]):
        if l1 >= share:
            return w0 + (share - l0) / (l1 - l0) * (w1 - w0) if l1 > l0 else w1
    return None


def _fmt(value):
    return f"{value:.1f}".replace(".", ",")


RASTER_MAX_SIDE_MM = 130.0  # orden 5: el bastidor es un límite, no el destino de una imagen


def raster_box(width_mm, height_mm):
    """Cuadro destino de un raster: min(lado del bastidor, 130 mm) por lado. Nunca mayor que el bastidor."""
    return min(width_mm, RASTER_MAX_SIDE_MM), min(height_mm, RASTER_MAX_SIDE_MM)


def _pct(value):
    return f"{round(value * 100)}%"


def check(data, media_type, width_mm, height_mm, color_limit, hoop_mm=None, cancel=None, prepared=None):
    """Mide el trazo al tamaño final del pedido. `prepared` permite reutilizar la máscara entre consultas."""
    ink = prepared or prepare(data, media_type, color_limit, cancel)
    if ink is None:
        return None
    width_mm, height_mm = raster_box(width_mm, height_mm)
    inset = 2 * REFERENCE_PULL_COMPENSATION_MM
    target_w = width_mm - inset if min(width_mm, height_mm) > 2 * inset else width_mm
    target_h = height_mm - inset if min(width_mm, height_mm) > 2 * inset else height_mm
    scale = min(target_w / ink.size[0], target_h / ink.size[1])
    left, top, right, bottom = ink.bbox
    ink_w, ink_h = (right - left) * scale, (bottom - top) * scale
    mask, work_mm = _work_mask(ink, scale)
    if mask.histogram()[255] == 0:
        return None
    profile = _profile(mask, work_mm)
    thin06 = _share(profile, THIN_MM, 0)
    thin08 = _share(profile, LEGIBLE_MM, 0)
    area06 = _share(profile, THIN_MM, 1)
    warn = thin06 > THIN_SHARE_WARN
    longest = max(ink_w, ink_h)

    # Tamaño mínimo: ancho w20 bajo el cual queda el 20 % del trazo; escalando por f = 0,8 / w20 el 80 % supera 0,8 mm.
    w20 = _width_at_share(profile, 1 - LEGIBLE_SHARE)
    legible_now = w20 is None or w20 >= LEGIBLE_MM
    factor = LEGIBLE_MM / w20 if w20 else 1.0
    min_w, min_h = ink_w * factor, ink_h * factor
    fits = None if hoop_mm is None else (min_w <= hoop_mm[0] and min_h <= hoop_mm[1])
    if legible_now:
        advice = f"El {_pct(LEGIBLE_SHARE)} o más del trazo ya supera {_fmt(LEGIBLE_MM)} mm."
    elif fits is False:
        advice = (f"Para que el {_pct(LEGIBLE_SHARE)} del trazo supere {_fmt(LEGIBLE_MM)} mm haría falta un dibujo de ~{round(min_w)} x "
                  f"{round(min_h)} mm, que no entra en el bastidor ({round(hoop_mm[0])} x {round(hoop_mm[1])} mm): no hay un tamaño "
                  "útil para este dibujo; conviene simplificarlo (menos texto fino) o bordarlo como línea.")
    else:
        advice = (f"El tamaño mínimo para que el {_pct(LEGIBLE_SHARE)} del trazo supere {_fmt(LEGIBLE_MM)} mm es de ~{round(min_w)} x "
                  f"{round(min_h)} mm.")
    minimum = MinimumSize(
        already_legible=legible_now, scale_factor=round(factor, 2), ink_width_mm=round(min_w, 1), ink_height_mm=round(min_h, 1),
        fits_in_hoop=fits, message=advice,
    )
    message = None
    if warn:
        message = (f"El {_pct(thin06)} del trazo mide menos de {_fmt(THIN_MM)} mm; a {round(longest)} mm las letras no van a quedar "
                   f"legibles. {advice}")

    # Orden 3.4: recortar el margen blanco antes de ajustar. Es una opción de tamaño; no resuelve el trazo fino.
    margin = None
    crop_w, crop_h = right - left, bottom - top
    crop_scale = min(target_w / crop_w, target_h / crop_h)
    gain = crop_scale / scale - 1
    if gain >= 0.01:
        margin = MarginOption(
            ink_bbox_px=ink.bbox, gain_percent=round(gain * 100, 1), ink_width_mm_now=round(ink_w, 1), ink_height_mm_now=round(ink_h, 1),
            ink_width_mm_cropped=round(crop_w * crop_scale, 1), ink_height_mm_cropped=round(crop_h * crop_scale, 1),
            message=(f"La imagen trae margen blanco: recortándolo antes de ajustar, el dibujo pasaría de {_fmt(ink_w)} x {_fmt(ink_h)} mm a "
                     f"{_fmt(crop_w * crop_scale)} x {_fmt(crop_h * crop_scale)} mm (+{_fmt(gain * 100)}%). Es solo más tamaño: no "
                     "resuelve el problema de las letras finas."),
        )
    return LegibilityCheck(
        requested_width_mm=width_mm, requested_height_mm=height_mm, ink_width_mm=round(ink_w, 1), ink_height_mm=round(ink_h, 1),
        thin_share_below_0_6_mm=round(thin06, 4), thin_share_below_0_8_mm=round(thin08, 4), ink_area_share_below_0_6_mm=round(area06, 4), warn=warn, message=message,
        minimum_size=minimum, margin_option=margin, palette_cleaning_applied=ink.palette_applied, inks=list(ink.inks),
    )
