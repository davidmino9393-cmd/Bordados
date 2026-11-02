"""Regression checks for the two known Anime Socks variants."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import pyembroidery as pe

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
EVIDENCE = ROOT / "workers" / "embroidery" / "evidence"
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from jef_audit import binary_commands
from verify_commands import IDENTICAL, compare_raw_commands

TOLERANCE_MM = 0.2
READ_SETTINGS = {"trims": True, "trim_at": 3, "trim_distance": None, "clipping": True}


class RegressionTests(unittest.TestCase):
    def assert_dimension(self, name, actual, expected):
        self.assertLessEqual(
            abs(actual - expected),
            TOLERANCE_MM,
            f"{name}: esperado {expected} mm, real {actual} mm",
        )

    def assert_variant(self, case, width_mm, height_mm, stitches, thread_blocks, commands):
        directory = EVIDENCE / case
        jef = directory / "output.jef"
        pattern = pe.read(str(jef), settings=READ_SETTINGS)
        needle = [s for s in pattern.stitches if s[2] & pe.COMMAND_MASK == pe.STITCH]
        xs = [s[0] / 10 for s in needle]
        ys = [s[1] / 10 for s in needle]

        self.assert_dimension(f"{case} width_mm", max(xs) - min(xs), width_mm)
        self.assert_dimension(f"{case} height_mm", max(ys) - min(ys), height_mm)
        self.assertEqual(
            len(needle), stitches, f"{case}: needle_stitches esperadas {stitches}, reales {len(needle)}"
        )
        self.assertEqual(
            len(pattern.threadlist),
            thread_blocks,
            f"{case}: thread_blocks esperados {thread_blocks}, reales {len(pattern.threadlist)}",
        )

        derived = binary_commands(jef.read_bytes())["events_01mm"]
        with tempfile.TemporaryDirectory() as tmp:
            actual = Path(tmp) / "raw-commands.json"
            actual.write_text(
                json.dumps(derived, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            report = compare_raw_commands(directory / "raw-commands.json", actual)

        self.assertEqual(
            report["reference_count"],
            commands,
            f"{case}: raw-commands esperados {commands}, reales {report['reference_count']}",
        )
        self.assertEqual(report["actual_count"], commands)
        self.assertEqual(report["verdict"], IDENTICAL, f"{case}: {report}")
        self.assertEqual(report["difference_indices"], [])

    def test_large_variant_cli_main_final(self):
        self.assert_variant("cli-main-final", 150.0, 142.8, 6789, 3, 7064)

    def test_small_variant_cli_small_final(self):
        self.assert_variant("cli-small-final", 126.2, 120.0, 5600, 3, 5862)


if __name__ == "__main__":
    unittest.main()
