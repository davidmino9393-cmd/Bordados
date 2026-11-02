"""Planilla de medidas de la muestra H3: una fila por elemento, con el valor nominal y el valor digital releído del JEF.

Uso:  python planilla_h3.py [muestra_h3.jef] [salida.csv]
Las columnas de medida física (ancho_medido_mm, aspecto, notas) quedan vacías: las completa quien cose la muestra.
"""
import csv
from pathlib import Path
import sys

import generar_muestra as g

ASPECTOS = ("bien", "hueco_se_ve_la_tela", "fruncido", "hilo_roto", "borde_irregular", "no_se_distingue")
JEF_UNIT_MM = 0.1  # el JEF guarda décimas de milímetro; el origen es el centro de la hoja
COLUMNAS = ("elemento", "fila", "variable", "valor_nominal", "ancho_o_lado_digital_mm", "puntadas_digitales",
            "ancho_medido_mm", "aspecto", "notas")


def elementos():
    """(id, fila, variable, valor nominal, rectángulo de la hoja donde buscar sus puntadas) de cada elemento de la muestra."""
    y_a = g.MARGIN_MM
    y_b = y_a + g.COLUMN_LENGTH_MM + g.GAP_MM
    y_c = y_b + g.COLUMN_LENGTH_MM + g.GAP_MM
    y_d = y_c + g.COLUMN_LENGTH_MM + g.GAP_MM
    y_e = y_d + g.FILL_SQUARE_MM + g.GAP_MM
    for i, width in enumerate(g.SATIN_WIDTHS_MM):
        x = g.MARGIN_MM + i * g.COLUMN_PITCH_MM
        yield f"A{i + 1}", "A", "ancho del satin (mm)", width, (x - 1.2, x + width + 1.2, y_a, y_a + g.COLUMN_LENGTH_MM)
    for i, spacing in enumerate(g.SATIN_SPACINGS_MM):
        x = g.MARGIN_MM + i * g.COLUMN_PITCH_MM
        yield f"B{i + 1}", "B", "separación del satin (mm)", spacing, (x - 1.2, x + 3 + 1.2, y_b, y_b + g.COLUMN_LENGTH_MM)
    for i, compensation in enumerate(g.PULL_COMPENSATIONS_MM):
        x = g.MARGIN_MM + i * g.COLUMN_PITCH_MM
        yield f"C{i + 1}", "C", "compensación de tracción (mm)", compensation, (x - 1.2, x + 3 + 1.2, y_c, y_c + g.COLUMN_LENGTH_MM)
    for i, spacing in enumerate(g.FILL_ROW_SPACINGS_MM):
        x = g.MARGIN_MM + i * g.FILL_PITCH_MM
        label = f"{spacing:g} con base" if i == len(g.FILL_ROW_SPACINGS_MM) - 1 else f"{spacing:g}"
        yield f"D{i + 1}", "D", "separación del relleno (mm)", label, (x - 1, x + g.FILL_SQUARE_MM + 1, y_d - 1, y_d + g.FILL_SQUARE_MM + 1)
    for i, (length, repeats) in enumerate(g.RUNNING_LINES):
        y = y_e + i * g.RUNNING_SPACING_MM
        yield f"E{i + 1}", "E", "largo de puntada (mm) / repeticiones", f"{length:g} / {repeats}", (g.MARGIN_MM - 1, g.MARGIN_MM + g.RUNNING_LENGTH_MM + 1, y - 1.2, y + 1.2)


def digital_values(jef_path):
    import pyembroidery  # noqa: PLC0415

    pattern = pyembroidery.read(str(jef_path))
    needles = [(x * JEF_UNIT_MM + g.SHEET_WIDTH_MM / 2, y * JEF_UNIT_MM + g.SHEET_HEIGHT_MM / 2)
               for x, y, command in pattern.stitches if command == pyembroidery.STITCH]
    result = {}
    for identifier, _, _, _, (x0, x1, y0, y1) in elementos():
        points = [(x, y) for x, y in needles if x0 <= x <= x1 and y0 <= y <= y1]
        result[identifier] = (round(max(x for x, _ in points) - min(x for x, _ in points), 2), len(points)) if points else (None, 0)
    return result


def write(jef_path, target):
    digital = digital_values(jef_path)
    with open(target, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNAS)
        for identifier, row, variable, nominal, _ in elementos():
            extent, stitches = digital[identifier]
            writer.writerow([identifier, row, variable, nominal, extent, stitches, "", "", ""])


if __name__ == "__main__":
    here = Path(__file__).parent
    write(Path(sys.argv[1]) if len(sys.argv) > 1 else here / "muestra_h3.jef", Path(sys.argv[2]) if len(sys.argv) > 2 else here / "planilla_h3.csv")
    print("planilla escrita")
