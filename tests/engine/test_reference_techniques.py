"""Measured reference selection, skeleton topology, omissions and JEF integrity."""
import json
import unittest
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from test_vectorize import png, result_for, settings, inside_path, path_polygons
from test_vectorize_inkstitch import INKSTITCH, SVG, h3_handoff
from embroidery_contracts import IssueCode
from vectorize import VectorizeFailure, stitchable
from vectorize import reference_geometry as geometry
from vectorize.inkstitch import to_reference_inkstitch_svg, to_inkstitch_svg, reference_issues


def stroke(width):
    image = Image.new("RGBA", (240, 100))
    height = round(width / 0.05)
    ImageDraw.Draw(image).rectangle((20, 40, 219, 40 + height - 1), fill=(20, 40, 90))
    return result_for(png(image), configuration=settings(12, 5, 1))


class ReferenceTechniqueTests(unittest.TestCase):
    def test_width_fixtures_select_real_techniques_and_scaled_parameters(self):
        for width, technique in ((.3, "running"), (.5, "running"), (.8, "running"), (1.5, "fill"), (3., "fill")):
            with self.subTest(width=width):
                value = stroke(width)
                obj = value.document.objects[0]
                ring, = obj.reference_rings
                self.assertAlmostEqual(ring["width"]["median_mm"], width)
                self.assertEqual(ring["technique"], technique)
                self.assertEqual(obj.effective_technique, technique)
                node, = ET.fromstring(to_reference_inkstitch_svg(value)).iter(SVG + "path")
                if technique == "running":
                    self.assertNotIn(INKSTITCH + "auto_fill", node.attrib)
                    self.assertNotIn(INKSTITCH + "pull_compensation_mm", node.attrib)
                    self.assertEqual(ring["pull_compensation_mm"], 0)
                    self.assertEqual(node.get("d"), obj.stitch_path_mm)
                    self.assertNotIn("Z", obj.stitch_path_mm)
                    self.assertNotEqual(obj.stitch_path_mm, obj.path_data_mm)
                else:
                    self.assertEqual(node.get(INKSTITCH + "auto_fill"), "true")
                    self.assertEqual(float(node.get(INKSTITCH + "pull_compensation_mm")), min(.2, .25 * width))
                    self.assertEqual(float(node.get(INKSTITCH + "row_spacing_mm")), .35 if width < 2 else .45)
                    self.assertEqual(bool(ring["satin_limitation"]), width < 2)

    def test_boundaries_use_median_not_minimum_and_wide_fill_keeps_reference_parameters(self):
        for width, technique, spacing in ((.9, "fill", .35), (2., "fill", .45), (3., "fill", .45)):
            ring, = stroke(width).document.objects[0].reference_rings
            self.assertEqual((ring["technique"], ring["row_spacing_mm"]), (technique, spacing))

    def test_mixed_widths_of_one_colour_are_selected_per_ring(self):
        image = Image.new("RGBA", (300, 120))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 209, 15), fill=(20, 40, 90))
        draw.rectangle((10, 40, 209, 99), fill=(20, 40, 90))
        value = result_for(png(image), configuration=settings(15, 6, 1))
        obj, = value.document.objects
        self.assertEqual({r["technique"] for r in obj.reference_rings}, {"running", "fill"})
        nodes = list(ET.fromstring(to_reference_inkstitch_svg(value)).iter(SVG + "path"))
        self.assertEqual({n.get("data-technique") for n in nodes}, {"running", "fill"})
        self.assertTrue(all(n.get("data-source-object-id") == obj.object_id for n in nodes))

    def test_mask_paths_checker_policy_and_thin_measurement_remain_unchanged(self):
        value = stroke(.3)
        before = value.document.model_dump_json()
        original_plan = stitchable.evidence(stitchable.plan(value.document))
        to_reference_inkstitch_svg(value)
        self.assertEqual(value.document.model_dump_json(), before)
        self.assertEqual(stitchable.evidence(stitchable.plan(value.document)), original_plan)
        self.assertEqual(value.evidence["minimum_feature"]["policy"], "measure_and_report_never_remove_or_thicken")
        self.assertEqual(value.evidence["minimum_feature"]["objects"][value.document.objects[0].object_id]["thin_fraction"], 1)

    def test_skeleton_stays_in_mask_and_preserves_hole_as_a_cycle(self):
        image = Image.new("RGBA", (160, 160))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 139, 139), fill=(20, 40, 90))
        draw.rectangle((26, 26, 133, 133), fill=(0, 0, 0, 0))
        value = result_for(png(image), configuration=settings(8, 8, 1))
        obj, = value.document.objects
        points = stitchable._points(obj.stitch_path_mm)
        self.assertEqual(points[0], points[-1])
        self.assertTrue(all(inside_path(p, path_polygons(obj.path_data_mm)) for p in points))
        self.assertEqual(len(points), len(set(points)) + 1)

    def test_legibility_issue_is_localized_measured_and_not_calibrated(self):
        value = stroke(.3)
        issue, = [i for i in value.issues if i.code == IssueCode.LEGIBILITY_RISK]
        self.assertEqual(issue.severity, "review_required")
        self.assertEqual(issue.object_ids, (value.document.objects[0].object_id,))
        self.assertEqual(issue.evidence["fraction_below_mm"]["0.4"], 1)
        self.assertAlmostEqual(issue.evidence["median_mm"], .3)
        self.assertAlmostEqual(issue.evidence["minimum_scale_for_80pct_above_0.8mm"], .8 / .3)
        self.assertEqual(issue.evidence["technique"], "running")
        self.assertFalse([i for i in stroke(.5).issues if i.code == IssueCode.LEGIBILITY_RISK])

    def test_one_point_two_five_mm2_fill_is_omitted_with_measured_warning(self):
        value = stroke(3)
        obj = value.document.objects[0].model_copy(update={
            "path_data_mm": "M0,0 L1.25,0 L1.25,1 L0,1 Z", "reference_rings": (), "stitch_path_mm": None})
        from dataclasses import replace
        value = replace(value, document=value.document.model_copy(update={"objects": (obj,)}))
        self.assertIsNotNone(stitchable.plan(value.document)[0].path_data_mm)
        with self.assertRaises(VectorizeFailure):
            to_reference_inkstitch_svg(value)
        omitted = [i for i in reference_issues(value) if "reference_omitted_rings" in i.evidence]
        self.assertEqual(omitted[0].object_ids, (obj.object_id,))
        ring, = omitted[0].evidence["reference_omitted_rings"]
        self.assertAlmostEqual(ring["area_mm2"], 1.25)

    def test_attested_h3_still_rejects_running_and_no_readiness_is_claimed(self):
        value = stroke(.5)
        with self.assertRaises(VectorizeFailure):
            to_inkstitch_svg(value, h3_document=h3_handoff(value.document))
        root = ET.fromstring(to_reference_inkstitch_svg(value))
        metadata = json.loads(root.find(".//" + SVG + "desc").text)
        self.assertFalse(metadata["digital_readiness_evaluated"])
        self.assertEqual(metadata["physical_approval"], "untested")

    def test_jef_reread_rejects_a_trailing_empty_colour_block(self):
        from jef_audit import measure
        import pyembroidery as pe
        pattern = pe.EmbPattern()
        pattern.add_thread("red")
        pattern.add_thread("blue")
        pattern.stitches = [[0, 0, pe.STITCH], [10, 0, pe.STITCH], [10, 0, pe.COLOR_CHANGE], [10, 0, pe.END]]
        raw = {"counts": {"stitch": 2}, "thread_entries": 2,
               "events_01mm": [["stitch", 0, 0], ["stitch", 10, 0], ["color_change", 10, 0], ["end", 10, 0]]}
        with self.assertRaisesRegex(ValueError, r"needle stitches per block=\[2, 0\]"):
            measure(pattern, raw)

    def test_a_residual_one_point_two_five_mm2_colour_cannot_become_a_phantom_running_thread(self):
        from dataclasses import replace
        value = stroke(3)
        obj = value.document.objects[0].model_copy(update={
            "path_data_mm": "M0,0 L5,0 L5,0.25 L0,0.25 Z", "reference_rings": (), "stitch_path_mm": None})
        value = replace(value, document=value.document.model_copy(update={"objects": (obj,)}))
        with self.assertRaises(VectorizeFailure) as caught:
            to_reference_inkstitch_svg(value)
        ring, = caught.exception.issue.evidence["reference_rings"][obj.object_id]
        self.assertEqual(ring["technique"], "running")
        self.assertEqual(ring["omitted"], "reference_object_below_2mm2")
        self.assertAlmostEqual(ring["object_kept_area_mm2"], 1.25)


if __name__ == "__main__":
    unittest.main()
