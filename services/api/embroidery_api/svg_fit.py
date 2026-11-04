"""Ajusta el tamaño de un SVG preparado al destino de una variante, antes de digitalizar.

Solo cambia `width` y `height` de la raíz y deja el `viewBox`: el motor escala todo el dibujo por esa razón, mientras que los
parámetros físicos de las puntadas (separación, largo, compensación) siguen en milímetros. El resto de los bytes no se toca.
"""
import re
import xml.etree.ElementTree as ET

SVG_ROOT = "{http://www.w3.org/2000/svg}svg"
MM_PER_INCH = 25.4
PX_PER_INCH = 96  # una longitud sin unidad es una unidad de usuario = 1 px
MM_PER_UNIT = {
    "mm": 1.0, "cm": 10.0, "in": MM_PER_INCH, "pt": MM_PER_INCH / 72, "pc": MM_PER_INCH / 6,
    "px": MM_PER_INCH / PX_PER_INCH, "": MM_PER_INCH / PX_PER_INCH,
}
LENGTH = re.compile(r"^\s*([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*(mm|cm|in|pt|pc|px)?\s*$")
# Salta comentarios e instrucciones de proceso (un comentario puede contener `<svg`): solo cuenta la primera etiqueta real.
ROOT_START_TAG = re.compile(rb"<!--.*?-->|<\?.*?\?>|(<svg\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>)", re.S)
DECIMALS = 6


def _length(root, name):
    found = LENGTH.match(root.get(name) or "")
    if not found:
        raise ValueError(f"El SVG no declara un «{name}» absoluto (en mm, cm, in, pt, pc, px o sin unidad).")
    value, unit = float(found.group(1)), found.group(2) or ""
    if not value > 0:
        raise ValueError(f"El «{name}» del SVG debe ser positivo.")
    return value, unit, value * MM_PER_UNIT[unit]


def _number(value):
    return f"{value:.{DECIMALS}f}".rstrip("0").rstrip(".")


def _set_attribute(tag, name, value):
    pattern = re.compile(rb"(\s" + name.encode() + rb"\s*=\s*)(\"[^\"]*\"|'[^']*')")
    if len(pattern.findall(tag)) != 1:
        raise ValueError(f"No se pudo localizar «{name}» en la raíz del SVG.")
    return pattern.sub(lambda found: found.group(1) + b'"' + value.encode() + b'"', tag, count=1)


def fit_to_target(data, target_width_mm, target_height_mm):
    """Devuelve (SVG ajustado, factor): la hoja del SVG entra en el cuadro sin deformarse (`fit: contain`).

    Rechaza con `ValueError` y un motivo legible un SVG cuyo tamaño no se puede cambiar: sin `width`/`height` absolutos
    o sin `viewBox` el motor no escala el dibujo, y cambiar solo la hoja dejaría las puntadas del mismo tamaño.
    """
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("El SVG tiene DTD o entidades, que no se admiten.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise ValueError(f"El SVG no se pudo leer: {error}") from error
    if root.tag != SVG_ROOT:
        raise ValueError("El archivo no es un SVG.")
    if not (root.get("viewBox") or "").strip():
        raise ValueError("El SVG no declara viewBox: sin él no se puede cambiar el tamaño del dibujo.")
    width, width_unit, width_mm = _length(root, "width")
    height, height_unit, height_mm = _length(root, "height")
    factor = min(target_width_mm / width_mm, target_height_mm / height_mm)
    new_width, new_height = _number(width * factor) + width_unit, _number(height * factor) + height_unit

    found = next((match for match in ROOT_START_TAG.finditer(data) if match.group(1)), None)
    if not found:
        raise ValueError("No se pudo localizar la raíz del SVG.")
    tag = _set_attribute(_set_attribute(found.group(1), "width", new_width), "height", new_height)
    fitted = data[:found.start(1)] + tag + data[found.end(1):]

    check = ET.fromstring(fitted)
    if (check.get("width"), check.get("height")) != (new_width, new_height):
        raise ValueError("El SVG ajustado no coincide con el tamaño pedido.")
    return fitted, factor
