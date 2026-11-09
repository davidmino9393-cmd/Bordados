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
    def test_standard_micro_and_wide_vertical_strokes_use_the_guide(self):
        for width in (1.2, 3, 5, 7):
            with self.subTest(width=width):
                image = Image.new("RGBA", (240, 300))
                ImageDraw.Draw(image).rectangle((30, 20, 30 + round(width / .05) - 1, 279), fill=(20, 40, 90))
                value = result_for(png(image), configuration=settings(12, 15, 1))
                nodes = [p for p in ET.fromstring(to_reference_inkstitch_svg(value)).iter(SVG + "path")
                         if p.get("data-technique")]
                self.assertTrue(nodes)
                for node in nodes:
                    if width <= 4:
                        self.assertEqual(node.get(INKSTITCH + "satin_column"), "true")
                        spacing = .55 if width < 1.5 else .4
                        self.assertEqual(float(node.get(INKSTITCH + "zigzag_spacing_mm")), spacing)
                        self.assertEqual(node.get(INKSTITCH + "center_walk_underlay"), "false" if width < 1.5 else "true")
                        self.assertEqual(node.get(INKSTITCH + "contour_underlay"), "false")
                        self.assertEqual(node.get(INKSTITCH + "zigzag_underlay"), "false")
                    else:
                        self.assertEqual(node.get(INKSTITCH + "auto_fill"), "true")
                        self.assertEqual(float(node.get(INKSTITCH + "row_spacing_mm")), .35)
                        self.assertEqual(node.get(INKSTITCH + "fill_underlay"), "true")
                        self.assertEqual(float(node.get(INKSTITCH + "fill_underlay_inset_mm")), 1.5)
                        self.assertEqual(float(node.get(INKSTITCH + "fill_underlay_max_stitch_length_mm")), 5)
                        self.assertEqual((float(node.get(INKSTITCH + "fill_underlay_angle")) -
                                          float(node.get(INKSTITCH + "angle"))) % 180, 90)

    def test_elastic_fabric_reaches_reference_derivation_without_api_changes(self):
        image = Image.new("RGBA", (240, 100))
        ImageDraw.Draw(image).rectangle((20, 40, 219, 69), fill=(20, 40, 90))
        config = settings(12, 5, 1).model_copy(update={"fabric_profile": "elastico"})
        value = result_for(png(image), configuration=config)
        self.assertTrue(all(r["pull_compensation_mm"] == .35 for r in value.document.objects[0].reference_rings
                            if r["technique"] == "satin"))

    def test_width_fixtures_select_real_techniques_and_guide_parameters(self):
        for width, technique in ((.3, "running"), (.5, "running"), (.8, "running"), (1.5, "satin"), (3., "satin")):
            with self.subTest(width=width):
                value = stroke(width)
                obj = value.document.objects[0]
                rings = [r for r in obj.reference_rings if not r["omitted"]]
                self.assertTrue(rings)
                self.assertAlmostEqual(rings[0]["width"]["median_mm"], width)
                self.assertEqual({r["technique"] for r in rings}, {technique})
                self.assertEqual(obj.effective_technique, technique)
                nodes = [p for p in ET.fromstring(to_reference_inkstitch_svg(value)).iter(SVG + "path")
                         if p.get("data-technique") == technique]
                self.assertTrue(nodes)
                if technique == "running":
                    for node in nodes:
                        self.assertNotIn(INKSTITCH + "auto_fill", node.attrib)
                        self.assertNotIn(INKSTITCH + "pull_compensation_mm", node.attrib)
                    self.assertTrue(all(r["pull_compensation_mm"] == 0 for r in rings))
                    self.assertNotIn("Z", obj.stitch_path_mm)
                    self.assertNotEqual(obj.stitch_path_mm, obj.path_data_mm)
                else:
                    for node in nodes:
                        self.assertEqual(node.get(INKSTITCH + "satin_column"), "true")
                        self.assertEqual(float(node.get(INKSTITCH + "pull_compensation_mm")), .25)
                        self.assertEqual(float(node.get(INKSTITCH + "zigzag_spacing_mm")), .55)
                        self.assertEqual(node.get(INKSTITCH + "center_walk_underlay"), "false")
                        self.assertEqual(float(node.get(INKSTITCH + "short_stitch_inset")), .15)
                        self.assertEqual(float(node.get(INKSTITCH + "max_stitch_length_mm")), 7)
                        self.assertTrue(node.get("d").count("M") == 3 or node.get("d").count("M") >= 5)

    def test_thresholds_distinguish_running_satin_and_wide_fill(self):
        for width, technique in ((.9, "running"), (1., "satin"), (2., "satin"), (4., "satin")):
            rings = stroke(width).document.objects[0].reference_rings
            self.assertTrue(rings)
            self.assertEqual({r["technique"] for r in rings if not r["omitted"]}, {technique})
        self.assertEqual(geometry.RUNNING_BELOW_MM, 1)
        self.assertEqual(geometry.WIDE_FILL_FROM_MM, 7)

    def test_mixed_widths_of_one_colour_are_selected_per_ring(self):
        image = Image.new("RGBA", (300, 120))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 209, 15), fill=(20, 40, 90))
        draw.rectangle((10, 40, 209, 99), fill=(20, 40, 90))
        value = result_for(png(image), configuration=settings(15, 6, 1))
        obj, = value.document.objects
        self.assertEqual({r["technique"] for r in obj.reference_rings}, {"running", "satin"})
        nodes = list(ET.fromstring(to_reference_inkstitch_svg(value)).iter(SVG + "path"))
        self.assertTrue({"running", "satin"}.issubset({n.get("data-technique") for n in nodes}))
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

    def test_local_paths_stay_in_mask_and_preserve_the_design_hole(self):
        image = Image.new("RGBA", (160, 160))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 139, 139), fill=(20, 40, 90))
        draw.rectangle((26, 26, 133, 133), fill=(0, 0, 0, 0))
        value = result_for(png(image), configuration=settings(8, 8, 1))
        obj, = value.document.objects
        points = stitchable._points(obj.stitch_path_mm)
        self.assertTrue(all(inside_path(p, path_polygons(obj.path_data_mm)) for p in points))
        self.assertFalse(inside_path((4, 4), path_polygons(obj.path_data_mm)))
        self.assertTrue(obj.reference_rings)
        self.assertTrue(all(not r["fill_path_mm"] for r in obj.reference_rings if not r["omitted"]))

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
