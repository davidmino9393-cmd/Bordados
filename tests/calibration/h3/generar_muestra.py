"""Genera la muestra de calibración física de H3 como SVG preparado para Ink/Stitch (1 unidad = 1 mm).

La muestra varía UN parámetro por fila para poder medir su efecto en tela: ancho de columna satin, densidad del satin,
compensación de tracción, separación de relleno y repeticiones de pespunte de línea fina. No es un diseño: es un instrumento.
Los valores NO están calibrados; la muestra existe para calibrarlos. Uso:  python generar_muestra.py [salida.svg]
"""
from pathlib import Path
import sys
from xml.sax.saxutils import quoteattr

COLOR = "#14285a"
SHEET_WIDTH_MM, SHEET_HEIGHT_MM = 150, 160
MARGIN_MM = 12
GAP_MM = 8
COLUMN_LENGTH_MM = 25
COLUMN_PITCH_MM = 16
RUNG_OVERSHOOT_MM = 0.5

# Una fila por variable; cada valor es un elemento de la muestra, de izquierda a derecha.
SATIN_WIDTHS_MM = (0.6, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0)         # fila A: ancho de columna (separación 0,4 mm, compensación 0,2 mm)
SATIN_SPACINGS_MM = (0.30, 0.35, 0.40, 0.45, 0.50, 0.60)            # fila B: densidad del satin (ancho 3 mm, compensación 0,2 mm)
PULL_COMPENSATIONS_MM = (0.0, 0.1, 0.2, 0.3, 0.4)                   # fila C: compensación de tracción (ancho 3 mm, separación 0,4 mm)
FILL_ROW_SPACINGS_MM = (0.3, 0.4, 0.5, 0.6, 0.8, 0.4)              # fila D: separación de relleno; el último con base («underlay»)
FILL_SQUARE_MM = 12
FILL_PITCH_MM = 22
RUNNING_LINES = ((2.0, 1), (2.5, 1), (3.0, 1), (2.5, 0), (2.5, 2), (2.5, 3))  # fila E: (largo de puntada mm, repeticiones de pespunte)
RUNNING_LENGTH_MM = 25
RUNNING_SPACING_MM = 4
DEFAULT_SATIN_SPACING_MM = 0.4
DEFAULT_PULL_COMPENSATION_MM = 0.2
FILL_ANGLE_DEG = 45


def satin(identifier, x, y, width, spacing, compensation):
    middle = y + COLUMN_LENGTH_MM / 2
    # Dos rieles rectos y un travesaño que los cruza en el medio: define la correspondencia sin avisos de «satin sin travesaños».
    rails = (f"M{x:g},{y:g} L{x:g},{y + COLUMN_LENGTH_MM:g} M{x + width:g},{y:g} L{x + width:g},{y + COLUMN_LENGTH_MM:g} "
             f"M{x - RUNG_OVERSHOOT_MM:g},{middle:g} L{x + width + RUNG_OVERSHOOT_MM:g},{middle:g}")
    return (
        f'<path id="{identifier}" d="{rails}" style="fill:none;stroke:{COLOR};stroke-width:1" inkstitch:satin_column="True" '
        f'inkstitch:zigzag_spacing_mm="{spacing:g}" inkstitch:pull_compensation_mm="{compensation:g}" '
        f'inkstitch:center_walk_underlay="False" inkstitch:contour_underlay="False" inkstitch:zigzag_underlay="False" '
        f'inkstitch:trim_after="True"/>'
    )


def fill(identifier, x, y, row_spacing, underlay):
    size = FILL_SQUARE_MM
    return (
        f'<path id="{identifier}" d="M{x:g},{y:g} L{x + size:g},{y:g} L{x + size:g},{y + size:g} L{x:g},{y + size:g} Z" '
        f'style="fill:{COLOR};stroke:none" inkstitch:row_spacing_mm="{row_spacing:g}" inkstitch:angle="{FILL_ANGLE_DEG}" '
        f'inkstitch:fill_underlay="{underlay}" inkstitch:pull_compensation_mm="{DEFAULT_PULL_COMPENSATION_MM:g}" inkstitch:trim_after="True"/>'
    )


def running(identifier, x, y, length_mm, repeats):
    return (
        f'<path id="{identifier}" d="M{x:g},{y:g} L{x + RUNNING_LENGTH_MM:g},{y:g}" style="fill:none;stroke:{COLOR};stroke-width:1" '
        f'inkstitch:stroke_method="running_stitch" inkstitch:running_stitch_length_mm="{length_mm:g}" '
        f'inkstitch:bean_stitch_repeats="{repeats}" inkstitch:trim_after="True"/>'
    )


def frame():
    left, top = 5, 5
    right, bottom = SHEET_WIDTH_MM - 5, SHEET_HEIGHT_MM - 5
    return (
        f'<path id="marco" d="M{left},{top} L{right},{top} L{right},{bottom} L{left},{bottom} Z" '
        f'style="fill:none;stroke:{COLOR};stroke-width:1" inkstitch:stroke_method="running_stitch" '
        f'inkstitch:running_stitch_length_mm="3" inkstitch:bean_stitch_repeats="0" inkstitch:trim_after="True"/>'
    )


def build():
    y_a = MARGIN_MM
    y_b = y_a + COLUMN_LENGTH_MM + GAP_MM
    y_c = y_b + COLUMN_LENGTH_MM + GAP_MM
    y_d = y_c + COLUMN_LENGTH_MM + GAP_MM
    y_e = y_d + FILL_SQUARE_MM + GAP_MM
    elements = [frame()]
    for i, width in enumerate(SATIN_WIDTHS_MM):
        elements.append(satin(f"A{i + 1}_satin_ancho_{width:g}", MARGIN_MM + i * COLUMN_PITCH_MM, y_a, width, DEFAULT_SATIN_SPACING_MM, DEFAULT_PULL_COMPENSATION_MM))
    for i, spacing in enumerate(SATIN_SPACINGS_MM):
        elements.append(satin(f"B{i + 1}_satin_separacion_{spacing:g}", MARGIN_MM + i * COLUMN_PITCH_MM, y_b, 3, spacing, DEFAULT_PULL_COMPENSATION_MM))
    for i, compensation in enumerate(PULL_COMPENSATIONS_MM):
        elements.append(satin(f"C{i + 1}_satin_compensacion_{compensation:g}", MARGIN_MM + i * COLUMN_PITCH_MM, y_c, 3, DEFAULT_SATIN_SPACING_MM, compensation))
    for i, spacing in enumerate(FILL_ROW_SPACINGS_MM):
        underlay = i == len(FILL_ROW_SPACINGS_MM) - 1
        elements.append(fill(f"D{i + 1}_relleno_separacion_{spacing:g}{'_con_base' if underlay else ''}", MARGIN_MM + i * FILL_PITCH_MM, y_d, spacing, underlay))
    for i, (length, repeats) in enumerate(RUNNING_LINES):
        elements.append(running(f"E{i + 1}_linea_puntada_{length:g}_repeticiones_{repeats}", MARGIN_MM, y_e + i * RUNNING_SPACING_MM, length, repeats))
    title = "Muestra de calibración H3 · Janome MC 550E (valores sin calibrar)"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        f'xmlns:inkstitch="http://inkstitch.org/namespace" width="{SHEET_WIDTH_MM}mm" height="{SHEET_HEIGHT_MM}mm" '
        f'viewBox="0 0 {SHEET_WIDTH_MM} {SHEET_HEIGHT_MM}" version="1.1">\n'
        f"  <title>{title}</title>\n"
        "  <metadata>\n    <inkstitch:inkstitch_svg_version>3</inkstitch:inkstitch_svg_version>\n"
        "    <inkstitch:collapse_len_mm>1.2</inkstitch:collapse_len_mm>\n    <inkstitch:min_stitch_len_mm>.3</inkstitch:min_stitch_len_mm>\n  </metadata>\n"
        '  <g id="muestra" inkscape:groupmode="layer" inkscape:label="muestra">\n    '
        + "\n    ".join(elements) + "\n  </g>\n</svg>\n"
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("muestra_h3.svg")
    target.write_text(build(), encoding="utf-8", newline="\n")
    print(f"escrito {target} ({quoteattr(target.name)})")
