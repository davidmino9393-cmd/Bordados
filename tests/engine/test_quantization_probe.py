"""Sanity checks for research measurements, not acceptance of a new quantizer."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/engine/experiments"))
from quantization_probe import compare


class QuantizationProbeTests(unittest.TestCase):
    def test_known_two_colour_mask_is_preserved_in_all_comparisons(self):
        temporary_root = ROOT / "tests/engine/.tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            directory = Path(directory)
            source = Image.new("RGBA", (4, 3), (0, 0, 0, 0))
            source.putpixel((1, 1), (255, 0, 0, 255))
            source.putpixel((2, 1), (0, 0, 255, 255))
            path = directory / "control.png"
            source.save(path)
            report = compare(path, 2, directory / "first")
            self.assertEqual(report["foreground_pixels"], 2)
            self.assertEqual(report["source_contrast_pixels"], 2)
            self.assertEqual(report["input_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            for method, metrics in report["methods"].items():
                self.assertEqual(metrics["mean_absolute_rgb_error"], 0)
                self.assertEqual(metrics["source_contrast_pixels_retained"], 2)
                self.assertEqual(metrics["palette"], ["#0000ff", "#ff0000"])
                with Image.open(directory / "first" / (method + ".png")) as preview:
                    self.assertEqual(preview.getchannel("A").tobytes(), source.getchannel("A").tobytes())
            repeated = compare(path, 2, directory / "second")
            self.assertEqual(report, repeated)
            self.assertTrue(report["experiment_only"])
            self.assertFalse(report["iou_holes_text_and_physical_quality_evaluated"])
            json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
