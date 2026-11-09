"""Regression against the actual logo exporter input and independently read JEF."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import tempfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workers/embroidery"))
from api_adapter import measured_checks
from round6_evidence import measure_jef
from process_runner import run_logged
from worker import diagnostics

EVIDENCE = ROOT / "tests/engine/evidence/round6"
SVG = "{http://www.w3.org/2000/svg}"
IS = "{http://inkstitch.org/namespace}"
ENGINE = Path(os.environ.get("EMBROIDERY_INKSTITCH_EXE", str(Path.home() /
              "AppData/Roaming/inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe")))


class HoopMarginTests(unittest.TestCase):
    def test_two_mm_margin_is_required_even_when_target_fits(self):
        job = {"settings_snapshot": {"target": {"width_mm": 140, "height_mm": 140},
                                     "hoop": {"width_mm": 140, "height_mm": 140, "jef_hoop_code": 2}}}
        for width, expected in ((136, "passed"), (136.1, "failed"), (140, "failed")):
            with self.subTest(width=width):
                result = {"metrics": {"width_mm": width, "height_mm": 136, "hoop_code": 2,
                                      "stitch_bounds_mm": [-width / 2, -68, width / 2, 68]}}
                checks, issues = measured_checks(job, result, .2)
                self.assertEqual(next(c.outcome for c in checks if c.kind == "hoop"), expected)
                self.assertEqual(bool(issues), expected == "failed")

    def test_translated_small_design_cannot_pass_on_width_alone(self):
        job = {"settings_snapshot": {"target": {"width_mm": 140, "height_mm": 140},
                                     "hoop": {"width_mm": 140, "height_mm": 140, "jef_hoop_code": 2}}}
        result = {"metrics": {"width_mm": 100, "height_mm": 100, "hoop_code": 2,
                              "stitch_bounds_mm": [0, -50, 100, 50]}}
        checks, issues = measured_checks(job, result, .2)
        self.assertEqual(next(c.outcome for c in checks if c.kind == "hoop"), "failed")
        self.assertEqual(issues[0].evidence["clearance_per_side_mm"]["right"], -30)


class RealLogoEvidenceTests(unittest.TestCase):
    @unittest.skipUnless(ENGINE.is_file(), "Installed Ink/Stitch required for fresh native regression")
    def test_current_adapter_regenerates_evidence_and_native_troubleshoot(self):
        from embroidery_contracts import EmbroideryDocument, JobSettings
        from vectorize.reference_geometry import apply
        from vectorize.inkstitch import to_reference_inkstitch_svg
        from vectorize.types import VectorizeResult
        document = EmbroideryDocument.model_validate_json((EVIDENCE / "source-e1-document.json").read_bytes())
        settings = JobSettings.model_validate_json((EVIDENCE / "settings.json").read_bytes())
        before = [o.path_data_mm for o in document.objects]
        derived, widths = apply(document, settings=settings)
        current = to_reference_inkstitch_svg(VectorizeResult(derived, (), b"", {"stroke_width": widths}, 0))
        self.assertEqual([o.path_data_mm for o in derived.objects], before)
        self.assertEqual(current, (EVIDENCE / "before-routing.svg").read_bytes(), "Regenerate real-logo evidence after adapter changes")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests/engine/.tmp") as tmp:
            source = Path(tmp) / "input.svg"
            source.write_bytes(current)
            from native_routing import route
            route(source, ENGINE, Path(tmp), 600)
            payload, _ = run_logged([str(ENGINE), "--extension=troubleshoot", str(source)], tmp, "diagnostics", 600)
        texts = [d["native_text"] for d in diagnostics(payload)]
        self.assertEqual(texts, [], "Native geometry, rung and effective underlay checks must all stay clean")

    def test_input_output_hashes_and_command_counts_are_reproducible(self):
        report = json.loads((EVIDENCE / "measurements.json").read_text(encoding="utf-8"))
        for name, expected in report["hashes"].items():
            self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(), expected)
        actual = measure_jef(EVIDENCE / "output.jef")
        for key in ("needle_stitches", "thread_blocks", "color_changes", "raw_jump_commands",
                    "interpreted_trims", "jump_travel_mm", "width_mm", "height_mm"):
            self.assertEqual(actual[key], report["after"][key], key)
        self.assertGreater(actual["needle_stitches"], 0)
        self.assertEqual((actual["thread_blocks"], actual["color_changes"]), (1, 0))
        self.assertLess(report["after"]["digitizing_s"], 600)
        self.assertGreaterEqual(min(report["after"]["hoop_margin_per_side_mm"]), 2)
        self.assertEqual(report["status"], "needs_review")
        self.assertFalse(report["parameters_calibrated"])
        self.assertFalse(report["digital_readiness_evaluated"])

    def test_real_troubleshoot_has_no_self_crossing_or_missing_rungs(self):
        report = json.loads((EVIDENCE / "measurements.json").read_text(encoding="utf-8"))
        worker = json.loads((EVIDENCE / "worker-result.json").read_text(encoding="utf-8"))
        texts = [d["native_text"] for d in worker["diagnostics"]]
        self.assertEqual(texts, report["after"]["troubleshoot"])
        self.assertEqual(texts, [])
        self.assertTrue(report["e1_paths_unchanged_by_adapter"])

    def test_real_satin_fill_and_trim_recipe_survives_serialization(self):
        paths = list(ET.parse(EVIDENCE / "input.svg").getroot().iter(SVG + "path"))
        satins = [p for p in paths if p.get(IS + "satin_column") == "true"]
        fills = [p for p in paths if p.get(IS + "auto_fill") == "true"]
        self.assertTrue(satins)
        self.assertTrue(fills)
        for path in satins:
            self.assertEqual(path.get(IS + "short_stitch_inset"), "0.15")
            self.assertEqual(float(path.get(IS + "max_stitch_length_mm")), 7)
            # 2 rails + 1 or >=3 rungs; exactly 2 is an Ink/Stitch warning.
            subpaths = path.get("d").count("M")
            self.assertTrue(subpaths == 3 or subpaths >= 5)
            spacing = float(path.get(IS + "zigzag_spacing_mm"))
            self.assertIn(spacing, (.4, .55))
            self.assertEqual(path.get(IS + "center_walk_underlay"), "true" if spacing == .4 else "false")
        for path in fills:
            self.assertTrue(.3 <= float(path.get(IS + "row_spacing_mm")) <= .35)
            self.assertEqual(path.get(IS + "fill_underlay").lower(), "true")
            self.assertIn(float(path.get(IS + "fill_underlay_row_spacing_mm")), (5, 6))
            self.assertEqual(float(path.get(IS + "fill_underlay_inset_mm")), 1.5)
            angle = float(path.get(IS + "angle"))
            underlay = float(path.get(IS + "fill_underlay_angle"))
            self.assertAlmostEqual((underlay - angle) % 180, 90)
        report = json.loads((EVIDENCE / "measurements.json").read_text(encoding="utf-8"))
        before, after = report["before"]["jump_classification"], report["after"]["jump_classification"]
        # Order 6: fewer cuts "or a justified physical minimum". The baseline's 32
        # reader trims were 31 long jumps plus 1 cut and left 7 floats over blank
        # fabric, so compare blank crossings and floats (README, section Cortes).
        self.assertEqual(after["uncut_blank_crossings"], 0, "no visible bridge over blank fabric")
        self.assertLess(after["blank_crossings"], before["blank_crossings"])
        self.assertGreaterEqual(after["blank_crossings"], report["component_topology"]["cut_lower_bound"])
        self.assertLess(report["after"]["jump_travel_mm"], report["before"]["jump_travel_mm"])


if __name__ == "__main__":
    unittest.main()
