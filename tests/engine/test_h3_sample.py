"""La muestra de calibración H3 se genera igual cada vez, entra en el bastidor y se exporta con Ink/Stitch sin avisos."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
H3 = ROOT / "tests" / "calibration" / "h3"
sys.path.insert(0, str(H3))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))

import generar_muestra  # noqa: E402
import planilla_h3  # noqa: E402

PRIVATE_CONFIG = ROOT / "services" / "api" / ".runtime" / "api-config.json"
HOOP_MM = 200
TIMEOUT_S = 180


def find_inkstitch():
    candidate = os.environ.get("EMBROIDERY_INKSTITCH_EXE")
    if not candidate and PRIVATE_CONFIG.exists():
        candidate = json.loads(PRIVATE_CONFIG.read_text(encoding="utf-8")).get("inkstitch_executable")
    return Path(candidate) if candidate and Path(candidate).is_file() else None


class SampleDefinitionTests(unittest.TestCase):
    def test_the_svg_is_well_formed_has_unique_ids_and_the_expected_elements(self):
        root = ET.fromstring(generar_muestra.build())
        paths = list(root.iter("{http://www.w3.org/2000/svg}path"))
        ids = [path.get("id") for path in paths]
        expected = 1 + len(generar_muestra.SATIN_WIDTHS_MM) + len(generar_muestra.SATIN_SPACINGS_MM) + len(generar_muestra.PULL_COMPENSATIONS_MM) \
            + len(generar_muestra.FILL_ROW_SPACINGS_MM) + len(generar_muestra.RUNNING_LINES)
        self.assertEqual((len(ids), len(set(ids))), (expected, expected))
        self.assertEqual(sum(1 for item in planilla_h3.elementos()), expected - 1)  # todo menos el marco tiene fila en la planilla

    def test_it_fits_the_hoop_and_every_element_stays_inside_the_frame(self):
        self.assertLessEqual(max(generar_muestra.SHEET_WIDTH_MM, generar_muestra.SHEET_HEIGHT_MM), HOOP_MM)
        for _, _, _, _, (x0, x1, y0, y1) in planilla_h3.elementos():
            self.assertTrue(5 < x0 and x1 < generar_muestra.SHEET_WIDTH_MM - 5 and 5 < y0 and y1 < generar_muestra.SHEET_HEIGHT_MM - 5)

    def test_generation_is_deterministic_and_the_committed_svg_is_current(self):
        self.assertEqual(generar_muestra.build(), generar_muestra.build())
        committed = (H3 / "muestra_h3.svg").read_text(encoding="utf-8")
        self.assertEqual(committed.replace("\r\n", "\n"), generar_muestra.build())

    def test_the_measurement_sheet_has_the_physical_columns_empty_and_the_digital_ones_filled(self):
        self.assertEqual(planilla_h3.COLUMNAS[-3:], ("ancho_medido_mm", "aspecto", "notas"))
        digital = planilla_h3.digital_values(H3 / "muestra_h3.jef")
        self.assertTrue(all(extent is not None and stitches > 0 for extent, stitches in digital.values()))
        widths = {identifier: extent for identifier, (extent, _) in digital.items()}
        # El motor predice ancho nominal + 2 x compensación (0,2 mm por lado en la fila A).
        self.assertAlmostEqual(widths["A6"], 3.4, delta=0.05)
        self.assertAlmostEqual(widths["C1"], 3.0, delta=0.05)
        self.assertAlmostEqual(widths["C5"], 3.8, delta=0.05)


@unittest.skipUnless(find_inkstitch(), "Ink/Stitch no está disponible (EMBROIDERY_INKSTITCH_EXE o configuración privada)")
class SampleExportTests(unittest.TestCase):
    def test_a_fresh_export_has_the_frame_size_no_diagnostics_and_the_committed_commands(self):
        import pyembroidery  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as directory:
            job_dir = Path(directory) / "job"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "workers" / "embroidery" / "worker.py"), "--svg", str(H3 / "muestra_h3.svg"), "--job-dir", str(job_dir),
                 "--inkstitch", str(find_inkstitch()), "--engine-version", "v3.2.2", "--timeout", str(TIMEOUT_S)],
                capture_output=True, text=True, timeout=TIMEOUT_S + 60,
                env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "workers" / "embroidery"), str(ROOT / "packages" / "contracts")])},
            )
            result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(result["ok"], completed.stderr[-400:])
            self.assertEqual((result["metrics"]["width_mm"], result["metrics"]["height_mm"], result["metrics"]["thread_blocks"]), (140.0, 150.0, 1))
            self.assertEqual(result["diagnostics"], [])
            new = [tuple(stitch) for stitch in pyembroidery.read(str(job_dir / "output.jef")).stitches]
            old = [tuple(stitch) for stitch in pyembroidery.read(str(H3 / "muestra_h3.jef")).stitches]
            self.assertEqual(new, old)


if __name__ == "__main__":
    unittest.main()
