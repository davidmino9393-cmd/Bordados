"""Medición del ancho mínimo bordable: cuánto de cada color es más fino que lo que una máquina puede coser.

Política (hasta que H3 calibre con muestras físicas): **medir y avisar, nunca borrar ni engrosar**. El ancho mínimo es un
supuesto provisional. La medición es una apertura morfológica con un elemento cuadrado: lo que la apertura quita pertenece a
trazos más angostos que el elemento (en diagonal el ancho real es hasta 1,41 veces mayor, así que la medición es prudente
y puede subestimar lo fino de una línea oblicua).
"""
import math

from PIL import Image, ImageChops, ImageFilter

from .segmentation import BACKGROUND
from .types import check_cancel

# Supuesto SIN calibrar: por debajo de este ancho de trazo (mm) una máquina doméstica no forma una línea reconocible.
PROVISIONAL_MIN_BORDABLE_WIDTH_MM = 0.4
MIN_ELEMENT_PX = 3  # con un elemento menor la apertura no distingue nada: la resolución es demasiado gruesa para medir


def _label_mask(raw_low, raw_high_is_zero, label, size):
    table = bytes(255 if value == label else 0 for value in range(256))
    return ImageChops.darker(Image.frombytes("L", size, raw_low.translate(table)), raw_high_is_zero)


def _odd_at_least(value):
    size = math.ceil(value)
    return max(MIN_ELEMENT_PX, size if size % 2 else size + 1)


def measure(segmented, traced, objects, mm_per_px, cancel=None):
    """Evidencia `minimum_feature`: por objeto, píxeles y fracción más finos que el ancho mínimo provisional."""
    min_px = PROVISIONAL_MIN_BORDABLE_WIDTH_MM / mm_per_px
    element = _odd_at_least(min_px) if min_px > 1 else 0  # elemento = el menor tamaño impar que cubre el ancho mínimo
    evidence = {
        "min_width_mm": PROVISIONAL_MIN_BORDABLE_WIDTH_MM, "min_width_mm_is_calibrated": False,
        "min_width_px": round(min_px, 3), "structuring_element_px": element, "measurable": element >= MIN_ELEMENT_PX,
        "policy": "measure_and_report_never_remove_or_thicken", "objects": {},
    }
    if not evidence["measurable"]:
        return evidence
    raw = segmented.labels.tobytes()
    size = (segmented.width, segmented.height)
    zero_table = bytes(255 if value == 0 else 0 for value in range(256))
    high_is_zero = Image.frombytes("L", size, raw[1::2].translate(zero_table))  # BACKGROUND (65535) tiene byte alto 255
    low = raw[0::2]
    label_of = {color: label for label, color in segmented.palette.items() if label != BACKGROUND}
    for obj, mask in zip(objects, traced):
        check_cancel(cancel)
        image = _label_mask(low, high_is_zero, label_of[mask.color], size)
        opened = image.filter(ImageFilter.MinFilter(element)).filter(ImageFilter.MaxFilter(element))
        thin = ImageChops.subtract(image, opened).histogram()[255]
        evidence["objects"][obj.object_id] = {
            "pixels": mask.pixel_count, "thin_pixels": thin,
            "thin_fraction": round(thin / mask.pixel_count, 6) if mask.pixel_count else 0.0,
        }
    return evidence
