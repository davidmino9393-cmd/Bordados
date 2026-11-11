"""Measured reference selection, skeleton topology, omissions and JEF integrity."""
import json
import unittest
from unittest import mock
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from test_vectorize import ROOT, png, result_for, settings, inside_path, path_polygons
from test_vectorize_inkstitch import INKSTITCH, SVG, h3_handoff
from embroidery_contracts import IssueCode
from vectorize import VectorizeFailure, stitchable
from vectorize import local_columns, reference_geometry as geometry
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

    def test_the_catalog_fabrics_get_the_compensation_the_guide_gives_them(self):
        """Los ids reales del catálogo: piqué y polar son de elasticidad media (0,35 mm); el resto, estables (0,25 mm)."""
        catalog = json.loads((ROOT / "services" / "api" / "profiles.json").read_text(encoding="utf-8"))
        expected = {"pique": .35, "polar": .35}
        image = Image.new("RGBA", (240, 100))
        ImageDraw.Draw(image).rectangle((20, 40, 219, 69), fill=(20, 40, 90))
        for fabric in catalog["fabrics"]:
            with self.subTest(fabric=fabric["profile_id"]):
                config = settings(12, 5, 1).model_copy(update={"fabric_profile": fabric["profile_id"]})
                rings = result_for(png(image), configuration=config).document.objects[0].reference_rings
                satin = [r["pull_compensation_mm"] for r in rings if r["technique"] == "satin"]
                self.assertTrue(satin)
                self.assertEqual(set(satin), {expected.get(fabric["profile_id"], .25)})

    def test_micro_satin_keeps_the_centre_run_only_on_elastic_fabrics(self):
        """Guía 6.3: en microtexto el refuerzo se decide por la tela; nunca contorno ni zigzag."""
        image = Image.new("RGBA", (240, 100))
        ImageDraw.Draw(image).rectangle((20, 40, 219, 63), fill=(20, 40, 90))  # 24 px a 0,05 mm/px = trazo de 1,2 mm: satén micro
        for fabric, expected in (("gabardina", "false"), ("pique", "true")):
            with self.subTest(fabric=fabric):
                config = settings(12, 5, 1).model_copy(update={"fabric_profile": fabric})
                root = ET.fromstring(to_reference_inkstitch_svg(result_for(png(image), configuration=config)))
                satin = [n for n in root.iter(SVG + "path") if n.get(INKSTITCH + "satin_column") == "true"]
                self.assertTrue(satin)
                for node in satin:
                    self.assertEqual(float(node.get(INKSTITCH + "zigzag_spacing_mm")), .55)
                    self.assertEqual(node.get(INKSTITCH + "center_walk_underlay"), expected)
                    self.assertEqual((node.get(INKSTITCH + "contour_underlay"), node.get(INKSTITCH + "zigzag_underlay")), ("false", "false"))

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



class SatinFallbackTests(unittest.TestCase):
    """El Fortín: satin pieces too short to bisect were dropped and the C lost axis between units."""

    def samples(self, count):
        return [{"technique": "satin", "center": (float(i), 0.), "width": 1.2} for i in range(count)]

    def test_an_invalid_satin_run_keeps_every_sample_as_running(self):
        run = self.samples(9)
        with mock.patch.object(local_columns, "_satin", return_value=None):
            parts = list(local_columns._valid_parts(run, mask=None))
        self.assertTrue(parts)
        self.assertTrue(all(local is None and {s["technique"] for s in part} == {"running"} for part, local in parts))
        kept = {s["center"] for part, _ in parts for s in part}
        self.assertEqual(kept, {s["center"] for s in run})  # no sample of the axis is dropped
        self.assertEqual({s["technique"] for s in run}, {"satin"})  # the input run is not mutated

    def test_valid_satin_parts_are_still_kept_as_satin(self):
        run = self.samples(4)
        with mock.patch.object(local_columns, "_satin", return_value={"path": "M 0 0"}):
            parts = list(local_columns._valid_parts(run, mask=None))
        self.assertEqual([(len(part), local) for part, local in parts], [(4, {"path": "M 0 0"})])



class SeamTests(unittest.TestCase):
    """El Fortín: a 1 px blend line between two colours was rescued as a small stroke and added a thread colour."""

    def line(self):
        image = Image.new("L", (30, 1), 0)
        ImageDraw.Draw(image).line((0, 0, 29, 0), fill=255)
        return image

    def test_a_line_lying_on_another_colour_is_a_seam(self):
        others = Image.new("L", (60, 20), 0)
        ImageDraw.Draw(others).rectangle((10, 6, 39, 9), fill=255)   # the colour just below the line at y=5
        ImageDraw.Draw(others).rectangle((10, 0, 39, 4), fill=255)   # and just above it
        self.assertGreater(geometry._contact_share(self.line(), (10, 5), others), geometry.SEAM_CONTACT_SHARE)

    def test_an_isolated_line_on_fabric_is_kept(self):
        others = Image.new("L", (60, 20), 0)
        ImageDraw.Draw(others).rectangle((50, 15, 59, 19), fill=255)  # another colour, but not touching
        self.assertEqual(geometry._contact_share(self.line(), (10, 5), others), 0.)
        self.assertEqual(geometry._contact_share(self.line(), (10, 5), None), 0.)



class StableTechniqueTests(unittest.TestCase):
    """El Fortín «Con»: a ~1 mm stroke flipped 48 times between running and satin inside one C."""

    class Grid:
        def __init__(self, scale):
            self.scale = scale

        def mm(self, point):
            return (point[0] * self.scale, point[1] * self.scale)

    def samples(self, widths, scale):
        step = local_columns.SAMPLE_INTERVAL_MM / scale
        return [{"center": (i * step, 0.), "width": w,
                 "technique": "running" if w < local_columns.RUNNING_LIMIT_MM else "satin"} for i, w in enumerate(widths)]

    def test_a_stroke_hovering_at_the_limit_gets_one_technique(self):
        samples = self.samples([.95, 1.05] * 20, .14)
        self.assertEqual({s["technique"] for s in local_columns._stable_techniques(samples, self.Grid(.14))}, {"satin"})

    def test_a_crisp_narrow_stroke_stays_running(self):
        samples = self.samples([.9] * 40, .05)
        self.assertEqual({s["technique"] for s in local_columns._stable_techniques(samples, self.Grid(.05))}, {"running"})

    def test_a_thinner_stretch_of_a_satin_stroke_stays_satin_down_to_the_floor(self):
        """El Fortín «Con»: la panza de la C (0,8 mm por el borde de antialias) quedaba como un hilo suelto."""
        thin = self.samples([1.2] * 15 + [.7] * 10 + [1.2] * 15, .14)
        self.assertEqual({s["technique"] for s in local_columns._stable_techniques(thin, self.Grid(.14))}, {"satin"})
        hairline = self.samples([1.2] * 15 + [.4] * 10 + [1.2] * 15, .14)
        self.assertIn("running", {s["technique"] for s in local_columns._stable_techniques(hairline, self.Grid(.14))})

    def test_a_short_island_is_absorbed_but_a_long_one_is_kept(self):
        short = self.samples([2.] * 10 + [.5] * 3 + [2.] * 10, .05)
        self.assertEqual({s["technique"] for s in local_columns._stable_techniques(short, self.Grid(.05))}, {"satin"})
        long = self.samples([2.] * 10 + [.5] * 12 + [2.] * 10, .05)
        self.assertIn("running", {s["technique"] for s in local_columns._stable_techniques(long, self.Grid(.05))})



class RunningToleranceTests(unittest.TestCase):
    def test_running_units_ask_ink_stitch_for_a_stitch_at_every_corner(self):
        """El Fortín: con la tolerancia por defecto (0,2 mm) la esquina de una L de 2,5 mm quedaba a ~0,5 mm del vértice."""
        root = ET.fromstring(to_reference_inkstitch_svg(stroke(.5)))
        running = [p for p in root.iter(f"{SVG}path") if p.get("data-technique") == "running"]
        self.assertTrue(running)
        self.assertEqual({p.get(INKSTITCH + "running_stitch_tolerance_mm") for p in running}, {"0.05"})

    def test_every_stitched_unit_asks_for_a_minimum_stitch_and_tiny_runs_are_dropped(self):
        """El Fortín: 6,7 % de puntadas bajo 0,3 mm; 175 corridos enteros más cortos que eso."""
        root = ET.fromstring(to_reference_inkstitch_svg(stroke(.5)))
        stitched = [p for p in root.iter(f"{SVG}path") if p.get("data-technique") in ("running", "satin", "fill")]
        self.assertTrue(stitched)
        self.assertEqual({p.get(INKSTITCH + "min_stitch_length_mm") for p in stitched}, {"0.3"})
        output = []
        local_columns._keep(output, None, {"technique": "running", "length_mm": .2}, [], .1)
        self.assertEqual(output, [])
        satin = {"technique": "satin", "length_mm": .2}
        with mock.patch.object(local_columns, "_cover"):
            local_columns._keep(output, None, satin, [], .1)
        self.assertEqual(output, [satin])  # el satén corto no se descarta: su ancho cubre


if __name__ == "__main__":
    unittest.main()
