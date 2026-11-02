"""Regresión que vuelve a EXPORTAR con Ink/Stitch (la de OpenCode solo relee archivos guardados).

Corre el worker real sobre `Anime_Socks_InkStitch.svg` y compara el JEF nuevo, comando por comando, con el entregado
(`Anime_Socks_Optimizado.jef`). Los bytes del JEF no sirven para comparar (la cabecera lleva la fecha); las órdenes sí.
Se omite si no hay Ink/Stitch: se toma de `EMBROIDERY_INKSTITCH_EXE` o de la configuración privada de la API.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))

SVG = ROOT / "Anime_Socks_Bordado" / "Anime_Socks_InkStitch.svg"
DELIVERED_JEF = ROOT / "Anime_Socks_Bordado" / "Anime_Socks_Optimizado.jef"
WORKER = ROOT / "workers" / "embroidery" / "worker.py"
PRIVATE_CONFIG = ROOT / "services" / "api" / ".runtime" / "api-config.json"
ENGINE_VERSION = "v3.2.2"
TIMEOUT_S = 180
# Medido en el JEF entregado (README de Anime_Socks_Bordado y relectura con pyembroidery).
EXPECTED_METRICS = {
    "width_mm": 150.0, "height_mm": 142.8, "stitch_bounds_mm": [-75.0, -71.4, 75.0, 71.4],
    "needle_stitches": 6789, "thread_blocks": 3, "color_changes": 2,
}


def find_inkstitch():
    candidate = os.environ.get("EMBROIDERY_INKSTITCH_EXE")
    if not candidate and PRIVATE_CONFIG.exists():
        candidate = json.loads(PRIVATE_CONFIG.read_text(encoding="utf-8")).get("inkstitch_executable")
    return Path(candidate) if candidate and Path(candidate).is_file() else None


def commands(path):
    import pyembroidery  # noqa: PLC0415

    pattern = pyembroidery.read(str(path))
    return [tuple(stitch) for stitch in pattern.stitches], len(pattern.threadlist)


@unittest.skipUnless(find_inkstitch(), "Ink/Stitch no está disponible (EMBROIDERY_INKSTITCH_EXE o configuración privada)")
class ReexportRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workdir = tempfile.TemporaryDirectory()
        cls.job_dir = Path(cls.workdir.name) / "job"  # el worker exige que no exista
        completed = subprocess.run(
            [sys.executable, str(WORKER), "--svg", str(SVG), "--job-dir", str(cls.job_dir), "--inkstitch", str(find_inkstitch()),
             "--engine-version", ENGINE_VERSION, "--timeout", str(TIMEOUT_S)],
            capture_output=True, text=True, timeout=TIMEOUT_S + 60,
            env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "workers" / "embroidery"), str(ROOT / "packages" / "contracts")])},
        )
        cls.stdout, cls.stderr = completed.stdout, completed.stderr
        result_file = cls.job_dir / "result.json"
        cls.result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else None

    @classmethod
    def tearDownClass(cls):
        cls.workdir.cleanup()

    def test_the_worker_exports_again_and_reports_the_expected_metrics(self):
        self.assertIsNotNone(self.result, self.stderr[-500:])
        self.assertTrue(self.result["ok"], self.result.get("issue"))
        self.assertEqual(self.result["input_sha256"], hashlib.sha256(SVG.read_bytes()).hexdigest())
        self.assertEqual(self.result["engine_version"], ENGINE_VERSION)
        self.assertEqual(self.result["engine_backend"], "inkstitch_cli")
        self.assertTrue(self.result["format_checks_passed"])
        for name, expected in EXPECTED_METRICS.items():
            self.assertEqual(self.result["metrics"][name], expected, name)

    def test_the_new_jef_has_exactly_the_commands_of_the_delivered_one(self):
        new_commands, new_threads = commands(self.job_dir / "output.jef")
        old_commands, old_threads = commands(DELIVERED_JEF)
        self.assertEqual((len(new_commands), new_threads), (len(old_commands), old_threads))
        self.assertEqual(new_commands, old_commands)

    def test_a_fresh_export_never_claims_digital_or_physical_approval(self):
        self.assertFalse(self.result["digital_readiness_evaluated"])
        self.assertEqual(self.result["physical_approval"], "untested")
        self.assertTrue(self.result["diagnostics"])  # los avisos del motor se conservan, no se ocultan


if __name__ == "__main__":
    unittest.main()
