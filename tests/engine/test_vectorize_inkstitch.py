"""The E adapter preserves geometry and requires an explicit H3 handoff."""
import json
import math
import unittest
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from test_vectorize import SVG, png, result_for, settings
from embroidery_contracts import EmbroideryDocument, IssueCode
from embroidery_contracts.design import StitchParameters
from vectorize import VectorizeFailure, stitchable
from vectorize.inkstitch import (
    REFERENCE_ANGLES_DEG, REFERENCE_CORRECTION, REFERENCE_MAX_STITCH_LENGTH_MM, REFERENCE_NOTICE, REFERENCE_PROFILE_ID,
    REFERENCE_PULL_COMPENSATION_MM, REFERENCE_ROW_SPACING_MM, reference_issues, to_inkstitch_svg, to_reference_inkstitch_svg,
)

INKSTITCH = "{http://inkstitch.org/namespace}"


def sample_result():
    image = Image.new("RGBA", (12, 12), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 10, 10), fill=(20, 80, 120, 255))
    draw.rectangle((4, 4, 7, 7), fill=(0, 0, 0, 0))
    return result_for(png(image), configuration=settings(60, 60, 1))


def h3_handoff(document, **parameter_changes):
    """Synthetic explicit parameters test the adapter, not physical calibration."""
    values = dict(stitch_length_mm=2.2, spacing_mm=0.45, direction_deg=30, underlay="none")
    values.update(parameter_changes)
    parameters = StitchParameters(**values)
    payload = document.model_dump()
    payload["objects"] = [dict(obj.model_dump(), parameters=parameters.model_dump()) for obj in document.objects]
    return EmbroideryDocument.model_validate(payload)


class InkstitchAdapterTests(unittest.TestCase):
    def test_provisional_parameters_cannot_be_exported_silently(self):
        value = sample_result()
        with self.assertRaises(VectorizeFailure) as caught:
            to_inkstitch_svg(value)
        self.assertEqual(caught.exception.issue.code, IssueCode.DENSITY_REVIEW_REQUIRED)

    def test_explicit_h3_handoff_preserves_mm_paths_holes_ids_and_parameters(self):
        value = sample_result()
        handoff = h3_handoff(value.document)
        output = to_inkstitch_svg(value, h3_document=handoff)
        self.assertEqual(output, to_inkstitch_svg(value, h3_document=handoff))
        root = ET.fromstring(output)
        for dimension in ("width", "height"):
            self.assertTrue(root.attrib[dimension].endswith("mm"))
            self.assertEqual(float(root.attrib[dimension][:-2]), 60)
        version = root.find(".//" + INKSTITCH + "inkstitch_svg_version")
        self.assertIsNotNone(version)
        self.assertEqual(version.text, "3")
        paths = {node.attrib["id"]: node for node in root.iter(SVG + "path")}
        self.assertEqual(set(paths), {obj.object_id for obj in handoff.objects})
        for obj in handoff.objects:
            node = paths[obj.object_id]
            self.assertEqual(node.attrib["d"], obj.path_data_mm)
            self.assertEqual(node.attrib["fill-rule"], "evenodd")
            self.assertEqual(node.attrib["fill"].lower(), obj.work_color.lower())
            self.assertEqual(float(node.attrib[INKSTITCH + "row_spacing_mm"]), 0.45)
            self.assertEqual(float(node.attrib[INKSTITCH + "max_stitch_length_mm"]), 2.2)
            self.assertEqual(float(node.attrib[INKSTITCH + "angle"]), 30)

    def test_h3_cannot_replace_geometry_or_document_identity(self):
        value = sample_result()
        valid = h3_handoff(value.document)
        changed_object = valid.objects[0].model_copy(update={"path_data_mm": "M0 0 L1 0 L1 1 Z"})
        cases = (
            valid.model_copy(update={"revision_id": "different_revision"}),
            valid.model_copy(update={"objects": (changed_object,)}),
            valid.model_copy(update={"coordinates": valid.coordinates.model_copy(update={"source_px_to_mm": (1, 0, 0, 1, 0, 0)})}),
        )
        for handoff in cases:
            with self.subTest(revision=handoff.revision_id), self.assertRaises(VectorizeFailure) as caught:
                to_inkstitch_svg(value, h3_document=handoff)
            self.assertEqual(caught.exception.issue.code, IssueCode.GEOMETRY_INVALID)

    def test_adapter_does_not_guess_missing_or_unsupported_parameters(self):
        value = sample_result()
        for changes in ({"spacing_mm": None}, {"direction_deg": None}, {"pull_compensation_mm": 0.2}):
            with self.subTest(changes=changes), self.assertRaises(VectorizeFailure) as caught:
                to_inkstitch_svg(value, h3_document=h3_handoff(value.document, **changes))
            self.assertEqual(caught.exception.issue.code, IssueCode.DENSITY_REVIEW_REQUIRED)

    def test_adapter_does_not_convert_fill_masks_to_unverified_running_or_satin(self):
        value = sample_result()
        valid = h3_handoff(value.document)
        for technique, code in (("running", IssueCode.GEOMETRY_REPAIR_AMBIGUOUS),
                                ("satin", IssueCode.SATIN_RAILS_UNVERIFIED)):
            payload = valid.model_dump()
            payload["objects"][0]["effective_technique"] = technique
            if technique == "satin":
                payload["objects"][0]["satin"] = {
                    "correspondence": "paired_nodes",
                    "left_rail_mm": [{"x_mm": 5, "y_mm": 5}, {"x_mm": 5, "y_mm": 55}],
                    "right_rail_mm": [{"x_mm": 55, "y_mm": 5}, {"x_mm": 55, "y_mm": 55}],
                }
            with self.subTest(technique=technique), self.assertRaises(VectorizeFailure) as caught:
                to_inkstitch_svg(value, h3_document=EmbroideryDocument.model_validate(payload))
            self.assertEqual(caught.exception.issue.code, code)


def two_colour_result():
    image = Image.new("RGB", (40, 20), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 17, 17), fill=(20, 40, 90))
    draw.rectangle((22, 2, 37, 17), fill=(220, 120, 20))
    return result_for(png(image), configuration=settings(60, 30, 2))


class ReferenceAdapterTests(unittest.TestCase):
    """El perfil de referencia no calibra nada: usa los valores de Anime Socks y lo dice."""

    def test_the_reference_svg_keeps_ids_and_geometry_and_uses_the_reference_values(self):
        value = sample_result()
        output = to_reference_inkstitch_svg(value)
        self.assertEqual(output, to_reference_inkstitch_svg(value))
        root = ET.fromstring(output)  # un espacio de nombres declarado dos veces no se parsea
        self.assertEqual(root.find(".//" + INKSTITCH + "inkstitch_svg_version").text, "3")
        paths = {node.attrib["id"]: node for node in root.iter(SVG + "path")}
        self.assertEqual(set(paths), {obj.object_id for obj in value.document.objects})
        for index, obj in enumerate(value.document.objects):
            node = paths[obj.object_id]
            self.assertEqual(node.attrib["d"], obj.path_data_mm)
            self.assertIn(f"fill:{obj.work_color}", node.attrib["style"])
            self.assertIn("fill-rule:evenodd", node.attrib["style"])
            self.assertEqual(float(node.attrib[INKSTITCH + "row_spacing_mm"]), REFERENCE_ROW_SPACING_MM)
            self.assertEqual(float(node.attrib[INKSTITCH + "max_stitch_length_mm"]), REFERENCE_MAX_STITCH_LENGTH_MM)
            self.assertEqual(float(node.attrib[INKSTITCH + "pull_compensation_mm"]), REFERENCE_PULL_COMPENSATION_MM)
            self.assertEqual(node.attrib[INKSTITCH + "fill_underlay"].lower(), "true")
            self.assertEqual(float(node.attrib[INKSTITCH + "angle"]), REFERENCE_ANGLES_DEG[index % len(REFERENCE_ANGLES_DEG)])

    def test_the_svg_declares_that_nothing_is_calibrated_or_approved(self):
        root = ET.fromstring(to_reference_inkstitch_svg(sample_result()))
        declared = json.loads(root.find(".//" + SVG + "desc").text)
        self.assertEqual(declared["physical_approval"], "untested")
        self.assertIs(declared["digital_readiness_evaluated"], False)
        self.assertEqual(declared["parameters"]["profile_id"], REFERENCE_PROFILE_ID)
        self.assertIs(declared["parameters"]["calibrated"], False)

    def test_neighbouring_colours_get_different_angles(self):
        root = ET.fromstring(to_reference_inkstitch_svg(two_colour_result()))
        angles = [float(node.attrib[INKSTITCH + "angle"]) for node in root.iter(SVG + "path")]
        self.assertEqual(len(angles), 2)
        self.assertEqual(len(set(angles)), 2)

    def test_only_the_parameter_notice_is_rewritten_and_the_thin_feature_evidence_survives(self):
        value = sample_result()
        issues = reference_issues(value)
        density = [issue for issue in issues if issue.code == IssueCode.DENSITY_REVIEW_REQUIRED]
        self.assertEqual(len(density), 1)
        self.assertEqual(density[0].description, REFERENCE_NOTICE)
        self.assertEqual(density[0].suggested_correction, REFERENCE_CORRECTION)
        self.assertEqual(density[0].object_ids, next(i for i in value.issues if i.code == IssueCode.DENSITY_REVIEW_REQUIRED).object_ids)
        self.assertIs(density[0].evidence["parameters_calibrated"], False)
        self.assertEqual(density[0].evidence["parameter_source"], REFERENCE_PROFILE_ID)
        self.assertIn("thin_feature_fraction_by_object", density[0].evidence)
        others = lambda items: [i for i in items if i.code != IssueCode.DENSITY_REVIEW_REQUIRED]  # noqa: E731
        self.assertEqual(others(issues), others(value.issues))

    def test_the_original_result_is_not_modified(self):
        value = sample_result()
        before = value.document.model_dump_json(), [issue.model_dump_json() for issue in value.issues]
        to_reference_inkstitch_svg(value)
        reference_issues(value)
        self.assertEqual((value.document.model_dump_json(), [issue.model_dump_json() for issue in value.issues]), before)


NEAR_WHITE = (243, 241, 240)


def specks_result():
    """Un rectángulo grande y cinco manchas de 2 × 2 px (0,16 mm² a 0,2 mm por píxel)."""
    image = Image.new("RGB", (200, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 119, 79), fill=(20, 40, 90))
    for x, y in ((150, 10), (160, 30), (170, 50), (180, 70), (190, 90)):
        draw.rectangle((x, y, x + 1, y + 1), fill=(20, 40, 90))
    return result_for(png(image), configuration=settings(40, 20, 1))


def near_white_result(with_blue=True):
    image = Image.new("RGB", (120, 60), "white")
    draw = ImageDraw.Draw(image)
    if with_blue:
        draw.rectangle((5, 5, 54, 54), fill=(20, 40, 90))
    draw.rectangle((65, 5, 114, 54), fill=NEAR_WHITE)
    return result_for(png(image), configuration=settings(60, 30, 2 if with_blue else 1))


class StitchablePlanTests(unittest.TestCase):
    """Lo que ninguna aguja puede formar no entra al SVG, pero queda contado y avisado."""

    def test_specks_below_the_minimum_area_are_dropped_and_the_large_shape_is_kept(self):
        value = specks_result()
        (item,) = stitchable.plan(value.document)
        self.assertEqual((item.loops, item.removed_loops), (6, 5))
        self.assertAlmostEqual(item.removed_area_mm2, 5 * 0.16, delta=0.05)
        self.assertIsNone(item.omitted)
        root = ET.fromstring(to_reference_inkstitch_svg(value))
        (path,) = root.iter(SVG + "path")
        self.assertEqual(path.attrib["d"].count("M"), 1)

    def test_a_near_white_layer_is_taken_as_background_and_not_stitched(self):
        value = near_white_result()
        planned = {item.object_id: item for item in stitchable.plan(value.document)}
        omitted = [item for item in planned.values() if item.omitted]
        self.assertEqual([item.omitted for item in omitted], [stitchable.OMITTED_NEAR_WHITE])
        root = ET.fromstring(to_reference_inkstitch_svg(value))
        stitched = {node.attrib["id"] for node in root.iter(SVG + "path")}
        self.assertEqual(stitched, set(planned) - {omitted[0].object_id})

    def test_changes_are_reported_as_a_localized_review_issue_with_numbers(self):
        value = specks_result()
        issues = [issue for issue in reference_issues(value) if issue.code == IssueCode.VISUAL_MISMATCH]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].object_ids, tuple(obj.object_id for obj in value.document.objects))
        self.assertEqual(issues[0].severity, "review_required")
        counts = issues[0].evidence["stitchable"]["objects"][value.document.objects[0].object_id]
        self.assertEqual((counts["loops"], counts["removed_loops"]), (6, 5))
        json.dumps(issues[0].evidence)  # serializable tal cual

    def test_an_untouched_design_adds_no_removal_issue(self):
        self.assertFalse([issue for issue in reference_issues(sample_result()) if issue.code == IssueCode.VISUAL_MISMATCH])

    def test_a_fine_ring_is_simplified_keeping_every_original_point_within_the_tolerance(self):
        ring = [(20 * math.cos(2 * math.pi * i / 4000), 20 * math.sin(2 * math.pi * i / 4000)) for i in range(4000)]
        simple = stitchable.simplify_ring(ring)
        self.assertLess(len(simple), 80)
        self.assertEqual(simple, stitchable.simplify_ring(ring))
        edges = list(zip(simple, simple[1:] + simple[:1]))

        def distance(point, edge):
            (x1, y1), (x2, y2) = edge
            dx, dy = x2 - x1, y2 - y1
            along = max(0, min(1, ((point[0] - x1) * dx + (point[1] - y1) * dy) / (dx * dx + dy * dy)))
            return math.hypot(point[0] - (x1 + along * dx), point[1] - (y1 + along * dy))

        self.assertLessEqual(max(min(distance(p, e) for e in edges) for p in ring[::7]), stitchable.SIMPLIFY_TOLERANCE_MM + 1e-9)
        self.assertAlmostEqual(stitchable.ring_area_mm2(simple), stitchable.ring_area_mm2(ring), delta=0.01 * stitchable.ring_area_mm2(ring))

    def test_a_square_and_a_triangle_are_not_changed_by_the_simplification(self):
        for ring in ([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (10, 0), (5, 8)]):
            self.assertEqual(stitchable.simplify_ring(ring), ring)

    def test_the_stair_edges_of_a_pixel_disc_lose_most_of_their_points(self):
        image = Image.new("RGB", (200, 200), "white")
        ImageDraw.Draw(image).ellipse((20, 20, 179, 179), fill=(20, 40, 90))
        value = result_for(png(image), configuration=settings(40, 40, 1))
        (item,) = stitchable.plan(value.document)
        self.assertGreater(item.points, 300)
        self.assertLess(item.kept_points, item.points / 2)
        json.dumps(stitchable.evidence((item,)))
        self.assertAlmostEqual(stitchable.ring_area_mm2(stitchable._points(item.path_data_mm)), item.total_area_mm2, delta=0.02 * item.total_area_mm2)

    def test_a_simplification_alone_is_a_change_reported_with_points_before_after_and_the_tolerance(self):
        """R3: aunque no se quite nada, que el contorno cambie dentro de una tolerancia se avisa y se mide."""
        image = Image.new("RGB", (200, 200), "white")
        ImageDraw.Draw(image).ellipse((20, 20, 179, 179), fill=(20, 40, 90))
        value = result_for(png(image), configuration=settings(40, 40, 1))
        (item,) = stitchable.plan(value.document)
        self.assertEqual((item.removed_loops, item.omitted), (0, None))
        self.assertTrue(item.simplified and item.changed)
        self.assertLess(item.kept_points, item.kept_points_before)
        issue = next(i for i in reference_issues(value) if i.code == IssueCode.VISUAL_MISMATCH)
        self.assertEqual(issue.object_ids, (item.object_id,))
        counts = issue.evidence["stitchable"]["objects"][item.object_id]
        self.assertEqual((counts["kept_points_before_simplification"], counts["kept_points"]), (item.kept_points_before, item.kept_points))
        self.assertTrue(counts["simplified"])
        self.assertEqual(counts["simplify_tolerance_mm"], round(item.tolerance_mm, 4))
        self.assertEqual(issue.evidence["stitchable"]["simplify_tolerance_mm"], round(item.tolerance_mm, 4))

    def test_a_design_with_nothing_to_remove_or_simplify_is_not_a_change(self):
        (item,) = stitchable.plan(sample_result().document)[:1]
        self.assertFalse(item.changed or item.simplified)

    def test_the_distance_is_to_the_segment_not_to_the_infinite_line(self):
        """R4: el punto (10, 0) está sobre la recta de la cuerda (0,0)-(5,0) pero a 5 mm del segmento: no se puede perder."""
        chain = [(0.0, 0.0), (10.0, 0.0), (5.0, 0.0)]
        self.assertEqual(stitchable._simplify_chain(chain, 0.1 ** 2), chain)
        self.assertAlmostEqual(stitchable._distance_squared((10, 0), (0, 0), (5, 0)), 25.0)
        self.assertAlmostEqual(stitchable._distance_squared((-3, 4), (0, 0), (5, 0)), 25.0)  # más allá del otro extremo
        self.assertAlmostEqual(stitchable._distance_squared((2, 3), (0, 0), (5, 0)), 9.0)  # dentro del segmento: perpendicular
        self.assertAlmostEqual(stitchable._distance_squared((3, 4), (0, 0), (0, 0)), 25.0)  # segmento sin largo

    def test_nothing_stitchable_is_a_localized_review_failure_not_an_empty_embroidery(self):
        value = near_white_result(with_blue=False)
        with self.assertRaises(VectorizeFailure) as caught:
            to_reference_inkstitch_svg(value)
        issue = caught.exception.issue
        self.assertEqual(issue.code, IssueCode.GEOMETRY_INVALID)
        self.assertEqual(issue.object_ids, tuple(obj.object_id for obj in value.document.objects))


if __name__ == "__main__":
    unittest.main()
