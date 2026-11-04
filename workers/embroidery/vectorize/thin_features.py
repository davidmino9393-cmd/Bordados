"""Medición del ancho mínimo bordable: cuánto de cada color es más fino que lo que una máquina puede coser.

Política (hasta que H3 calibre con muestras físicas): **medir y avisar, nunca borrar ni engrosar**. El ancho mínimo es un
supuesto provisional. La medición usa apertura cuadrada con exterior cero y conserva elementos pares. Es una aproximación
orientada a los ejes: en diagonales puede marcar trazos de hasta 1,41 veces el ancho del elemento. No es calibración física.
"""
import math
import sys

from PIL import Image, ImageChops, ImageOps

from .segmentation import BACKGROUND
from .types import check_cancel

# Supuesto SIN calibrar: por debajo de este ancho de trazo (mm) una máquina doméstica no forma una línea reconocible.
PROVISIONAL_MIN_BORDABLE_WIDTH_MM = 0.4
MIN_ELEMENT_PX = 2  # con un solo píxel la apertura no distingue ningún trazo


def _label_mask(raw_low, raw_high_is_zero, label, size):
    table = bytes(255 if value == label else 0 for value in range(256))
    return ImageChops.darker(Image.frombytes("L", size, raw_low.translate(table)), raw_high_is_zero)


def _shift(image, amount, axis):
    if not amount:
        return image
    shifted = Image.new("L", image.size, 0)
    shifted.paste(image, (-amount, 0) if axis == 0 else (0, -amount))
    return shifted


def _window(image, size, combine, axis, cancel):
    """Combine contiguous windows with doubling, bounded by O(pixels * log(size))."""
    result, block = None, image
    offset, span, remaining = 0, 1, size
    while remaining:
        check_cancel(cancel)
        if remaining & 1:
            part = _shift(block, offset, axis)
            result = part if result is None else combine(result, part)
            offset += span
        remaining >>= 1
        if remaining:
            block = combine(block, _shift(block, span, axis))
            span *= 2
    return result


def _square_filter(image, size, combine, reflected, cancel):
    left = (size - 1) // 2
    right = size - 1 - left
    if reflected:
        left, right = right, left
    padded = ImageOps.expand(image, border=(left, left, right, right), fill=0)
    filtered = _window(padded, size, combine, 0, cancel)
    filtered = _window(filtered, size, combine, 1, cancel)
    return filtered.crop((0, 0, image.width, image.height))


def _opening(image, element, cancel):
    # No finite mask can contain a square larger than either of its dimensions.
    # This also avoids allocating padding or passing gigantic kernels to Pillow.
    if element > min(image.size):
        return Image.new("L", image.size, 0)
    eroded = _square_filter(image, element, ImageChops.darker, False, cancel)
    return _square_filter(eroded, element, ImageChops.lighter, True, cancel)


def measure(segmented, traced, objects, mm_per_px, cancel=None):
    """Evidencia `minimum_feature`: por objeto, píxeles y fracción más finos que el ancho mínimo provisional."""
    min_px = PROVISIONAL_MIN_BORDABLE_WIDTH_MM / mm_per_px
    element = math.ceil(min_px) if min_px > 1 else 0
    # Division can round an exact pixel width upward by one ULP. Check the
    # physical product before adding a pixel; no millimetre tolerance is used.
    if element > 1 and (element - 1) * mm_per_px >= PROVISIONAL_MIN_BORDABLE_WIDTH_MM:
        element -= 1
    evidence = {
        "min_width_mm": PROVISIONAL_MIN_BORDABLE_WIDTH_MM, "min_width_mm_is_calibrated": False,
        "min_width_px": round(min_px, 3), "structuring_element_px": element, "measurable": element >= MIN_ELEMENT_PX,
        "effective_test_width_mm": element * mm_per_px,
        "measurement_method": "square_opening_zero_exterior_even_kernels_supported",
        "policy": "measure_and_report_never_remove_or_thicken", "objects": {},
    }
    if not evidence["measurable"]:
        return evidence
    raw = segmented.labels.tobytes()
    size = (segmented.width, segmented.height)
    zero_table = bytes(255 if value == 0 else 0 for value in range(256))
    low_offset = 0 if sys.byteorder == "little" else 1
    high_is_zero = Image.frombytes("L", size, raw[1 - low_offset::2].translate(zero_table))
    low = raw[low_offset::2]
    label_of = {color: label for label, color in segmented.palette.items() if label != BACKGROUND}
    for obj, mask in zip(objects, traced):
        check_cancel(cancel)
        image = _label_mask(low, high_is_zero, label_of[mask.color], size)
        opened = _opening(image, element, cancel)
        thin = ImageChops.subtract(image, opened).histogram()[255]
        evidence["objects"][obj.object_id] = {
            "pixels": mask.pixel_count, "thin_pixels": thin,
            "thin_fraction": round(thin / mask.pixel_count, 6) if mask.pixel_count else 0.0,
        }
    return evidence
