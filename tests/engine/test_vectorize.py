"""E1 checks on decoded pixels and physical geometry, without desktop tools."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import threading
import unittest
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_contracts import AnalysisSpec, EmbroideryDocument, IssueCode, JobSettings, SourceAsset
from embroidery_contracts.base import BoundsPX
from vectorize import VectorizeFailure, vectorize

FIXTURES = ROOT / "tests" / "fixtures" / "h2"
SVG = "{http://www.w3.org/2000/svg}"


def settings(width=80, height=80, colors=3):
    data = json.loads((ROOT / "packages/contracts/fixtures/generation-from-svg.json").read_text())
    value = data["payload"]["settings"]
    value.update(target={"width_mm": width, "height_mm": height, "fit": "contain"}, color_limit=colors)
    return JobSettings.model_validate(value)


def png(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def asset(data, media_type="image/png", *, crop=None):
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
    return SourceAsset(
        asset_id="asset_e1_test", project_id="project_e1_test", sha256=hashlib.sha256(data).hexdigest(),
        media_type=media_type, original_filename="test.png" if media_type == "image/png" else "test.jpg",
        original_width_px=width, original_height_px=height, crop_px=crop,
    )


def result_for(data, *, source=None, configuration=None, analysis=None, cancel=None, media_type="image/png"):
    return vectorize(
        data, media_type, source or asset(data, media_type), analysis, configuration or settings(),
        job_id="job_e1_test", revision_id="revision_e1_test", cancel=cancel,
    )


def path_polygons(path):
    """Small independent reader for the exact polygon output promised by E1."""
    tokens = re.findall(r"[A-Za-z]|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", path)
    polygons, current, position = [], [], 0
    while position < len(tokens):
        command = tokens[position]
        position += 1
        if command == "Z":
            if not current:
                raise AssertionError("Empty contour")
            polygons.append(current)
            current = []
        elif command in ("M", "L"):
            if command == "M" and current:
                raise AssertionError("Contour is not closed")
            current.append((float(tokens[position]), float(tokens[position + 1])))
            position += 2
        else:
            raise AssertionError(f"Unexpected E1 polygon command: {command}")
    if current:
        raise AssertionError("Final contour is not closed")
    return polygons


def inside_path(point, polygons):
    x, y = point
    intersections = 0
    for polygon in polygons:
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            x0, y0 = start
            x1, y1 = end
            if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                intersections += 1
    return bool(intersections % 2)


def transformed(point, coordinates):
    a, b, c, d, e, f = coordinates.source_px_to_mm
    x, y = point
    return a * x + c * y + e, b * x + d * y + f


class VectorizeTests(unittest.TestCase):
    def test_flat_fixture_inputs_produce_real_geometry_and_reviewable_parameters(self):
        manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        selected = {"logo-sol-01", "logo-hoja-01", "logo-escudo-01", "logo-ola-01", "anillo-doble-01", "jpeg-simple-01"}
        for case in (case for case in manifest["images"] if case["id"] in selected):
            with self.subTest(case=case["id"]):
                data = (FIXTURES / case["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), case["sha256"])
                media_type = "image/jpeg" if case["format"] == "jpeg" else "image/png"
                target = case["target_size_mm"]
                value = result_for(data, media_type=media_type, configuration=settings(
                    target["width_mm"], target["height_mm"], case["expected_colors"],
                ))
                self.assertTrue(value.document.objects)
                self.assertEqual(EmbroideryDocument.model_validate_json(value.document.model_dump_json()), value.document)
                self.assertLessEqual(len({obj.work_color for obj in value.document.objects}), case["expected_colors"])
                self.assertTrue(all(obj.geometry_kind == "verified_mask" for obj in value.document.objects))
                self.assertTrue(all(obj.effective_technique != "satin" for obj in value.document.objects))
                self.assertIn(IssueCode.DENSITY_REVIEW_REQUIRED, {issue.code for issue in value.issues})
                provisional = [decision for decision in value.document.decisions
                               if decision.field == "parameters" and isinstance(decision.new_value, dict)
                               and decision.new_value.get("h3_validation_required") is True]
                self.assertEqual({item.object_id for item in provisional},
                                 {item.object_id for item in value.document.objects})
                bounds = value.document.object_bounds_mm
                self.assertGreaterEqual(bounds.min_x_mm, 0)
                self.assertGreaterEqual(bounds.min_y_mm, 0)
                self.assertLessEqual(bounds.max_x_mm, target["width_mm"] + 1e-8)
                self.assertLessEqual(bounds.max_y_mm, target["height_mm"] + 1e-8)
                self.assertGreaterEqual(value.duration_ms, 0)
                json.dumps(value.evidence, allow_nan=False)
                if case["id"] == "anillo-doble-01":
                    paths = [path_polygons(obj.path_data_mm) for obj in value.document.objects]
                    for point, expected in (((500, 500), False), ((500, 360), True),
                                            ((500, 270), False), ((500, 170), True)):
                        mm = transformed(point, value.document.coordinates)
                        self.assertEqual(any(inside_path(mm, polygons) for polygons in paths), expected, point)

    def test_pixel_mask_holes_survive_exactly_without_bbox_substitution(self):
        image = Image.new("RGBA", (16, 12), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((1, 1, 14, 10), fill=(20, 80, 120, 255))
        draw.rectangle((3, 3, 5, 5), fill=(0, 0, 0, 0))
        draw.rectangle((9, 3, 11, 7), fill=(0, 0, 0, 0))
        value = result_for(png(image), configuration=settings(80, 60, 1))
        paths = [path_polygons(obj.path_data_mm) for obj in value.document.objects]
        for y in range(image.height):
            for x in range(image.width):
                mm = transformed((x + 0.5, y + 0.5), value.document.coordinates)
                found = any(inside_path(mm, polygons) for polygons in paths)
                self.assertEqual(found, image.getpixel((x, y))[3] != 0, (x, y))
        xml = ET.fromstring(value.editable_svg)
        self.assertTrue(xml.attrib["width"].endswith("mm"))
        self.assertTrue(xml.attrib["height"].endswith("mm"))
        self.assertTrue(all(p.attrib.get("fill-rule") == "evenodd" for p in xml.iter(SVG + "path")))
        self.assertEqual({obj.object_id for obj in value.document.objects}, {p.attrib["id"] for p in xml.iter(SVG + "path")})

    def test_diagonally_touching_pixels_do_not_gain_a_bridge(self):
        image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
        image.putpixel((1, 1), (0, 0, 255, 255))
        image.putpixel((2, 2), (0, 0, 255, 255))
        value = result_for(png(image), configuration=settings(40, 40, 1))
        polygons = [p for obj in value.document.objects for p in path_polygons(obj.path_data_mm)]
        self.assertEqual(len(polygons), 2)
        for y in range(4):
            for x in range(4):
                mm = transformed((x + 0.5, y + 0.5), value.document.coordinates)
                self.assertEqual(inside_path(mm, polygons), image.getpixel((x, y))[3] != 0, (x, y))

    def test_crop_and_contain_use_original_pixel_coordinates_and_centered_mm(self):
        image = Image.new("RGB", (12, 10), "white")
        ImageDraw.Draw(image).rectangle((4, 3, 7, 6), fill="blue")
        data = png(image)
        source = asset(data, crop=BoundsPX(x_px=2, y_px=1, width_px=8, height_px=8))
        value = result_for(data, source=source, configuration=settings(80, 40, 1))
        frame = value.document.coordinates
        self.assertEqual(frame.unit, "mm")
        self.assertEqual(frame.origin, "design_top_left")
        self.assertEqual(frame.y_axis, "down")
        for actual, expected in zip(frame.source_px_to_mm, (5, 0, 0, 5, 10, -5)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(transformed((2, 1), frame), (20, 0))
        self.assertEqual(transformed((10, 9), frame), (60, 40))
        bounds = value.document.object_bounds_mm
        self.assertEqual((bounds.min_x_mm, bounds.min_y_mm, bounds.max_x_mm, bounds.max_y_mm), (30, 10, 50, 30))

    def test_color_limit_and_geometric_output_are_deterministic(self):
        image = Image.new("RGBA", (30, 20), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for offset, color in ((0, "red"), (10, "green"), (20, "blue")):
            draw.rectangle((offset, 2, offset + 7, 17), fill=color)
        data = png(image)
        first = result_for(data, configuration=settings(colors=2))
        second = result_for(data, configuration=settings(colors=2))
        self.assertLessEqual(len({obj.work_color for obj in first.document.objects}), 2)
        self.assertEqual(first.document, second.document)
        self.assertEqual(first.editable_svg, second.editable_svg)
        self.assertEqual(first.evidence, second.evidence)

    def test_tiny_valid_target_cannot_silently_collapse_output_paths(self):
        data = png(Image.new("RGB", (8, 8), "blue"))
        configuration = settings(1e-10, 1e-10, 1)
        self.assertGreater(configuration.target.width_mm, 0)
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, configuration=configuration)
        self.assertEqual(caught.exception.issue.code, IssueCode.GEOMETRY_INVALID)

    def test_quantization_measures_pastel_colour_changes_and_requests_visual_review(self):
        image = Image.new("RGB", (10, 6), "white")
        draw = ImageDraw.Draw(image)
        for start, colour in ((1, (240, 200, 200)), (3, (230, 190, 190)), (5, (220, 180, 180))):
            draw.rectangle((start, 1, start + 1, 4), fill=colour)
        value = result_for(png(image), configuration=settings(colors=1))
        evidence = value.evidence["segmentation"]
        self.assertEqual(evidence["foreground_pixels"], 24)
        self.assertGreater(evidence["changed_rgb_pixels"], 0)
        self.assertLessEqual(evidence["changed_rgb_pixels"], evidence["foreground_pixels"])
        self.assertGreater(evidence["max_channel_error_rgb"], 0)
        self.assertGreater(evidence["mean_absolute_channel_error_rgb"], 0)
        warning = next(issue for issue in value.issues if issue.code == IssueCode.VISUAL_MISMATCH)
        self.assertEqual(warning.evidence["changed_rgb_pixels"], evidence["changed_rgb_pixels"])
        self.assertEqual(set(warning.object_ids), {obj.object_id for obj in value.document.objects})

    def test_estimated_analysis_cannot_replace_pixel_geometry_or_fonts(self):
        image = Image.new("RGB", (20, 20), "white")
        ImageDraw.Draw(image).rectangle((5, 7, 12, 14), fill="blue")
        data = png(image)
        source = asset(data)
        analysis = AnalysisSpec(
            analysis_id="analysis_simulated_test", asset_id=source.asset_id,
            provider="openai", model="simulated-test-model", prompt_version="test-v1",
            original_response_artifact_id="provider_simulated_test", duration_ms=1,
            regions=({"region_id": "estimated_text", "bounds_px": {"x_px": 0, "y_px": 0, "width_px": 20, "height_px": 20},
                      "visual_role": "text", "observed_text": "TEST"},),
        )
        value = result_for(data, source=source, analysis=analysis, configuration=settings(40, 40, 1))
        xml = ET.fromstring(value.editable_svg)
        self.assertEqual(list(xml.iter(SVG + "text")), [])
        self.assertIn("TEST", json.dumps(value.evidence))
        bounds = value.document.object_bounds_mm
        self.assertEqual((bounds.min_x_mm, bounds.min_y_mm, bounds.max_x_mm, bounds.max_y_mm), (10, 14, 26, 30))

    def test_out_of_bounds_analysis_issue_is_localized_to_actual_region(self):
        data = png(Image.new("RGB", (20, 20), "blue"))
        source = asset(data)
        analysis = AnalysisSpec(
            analysis_id="analysis_simulated_test", asset_id=source.asset_id,
            provider="openai", model="simulated-test-model", prompt_version="test-v1",
            original_response_artifact_id="provider_simulated_test", duration_ms=0,
            regions=({"region_id": "outside_region", "bounds_px": {
                "x_px": 19, "y_px": 0, "width_px": 2, "height_px": 10,
            }, "visual_role": "shape"},),
        )
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, source=source, analysis=analysis)
        incidence = caught.exception.issue
        self.assertEqual(incidence.code, IssueCode.ANALYSIS_REGION_INCOHERENT)
        self.assertEqual(incidence.region_ids, ("outside_region",))
        self.assertEqual(incidence.severity.value, "review_required")

    def test_invalid_input_and_metadata_are_catalogued(self):
        data = png(Image.new("RGB", (8, 8), "blue"))
        source = asset(data)
        cases = (
            (b"not an image", source.model_copy(update={"sha256": hashlib.sha256(b"not an image").hexdigest()}), "image/png"),
            (data, source.model_copy(update={"sha256": "0" * 64}), "image/png"),
            (data, source.model_copy(update={"original_width_px": 9}), "image/png"),
            (data, source, "image/jpeg"),
        )
        for payload, metadata, media_type in cases:
            with self.subTest(media_type=media_type, sha=metadata.sha256), self.assertRaises(VectorizeFailure) as caught:
                result_for(payload, source=metadata, media_type=media_type)
            self.assertIn(caught.exception.issue.code, {IssueCode.INPUT_UNREADABLE, IssueCode.INPUT_UNSUPPORTED_FORMAT})
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(b"<svg/>", source=source, media_type="image/svg+xml")
        self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNSUPPORTED_FORMAT)

    def test_cancel_before_and_during_work_is_cooperative_and_catalogued(self):
        image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 10, 100, 100), fill="red")
        data = png(image)
        event = threading.Event()
        event.set()
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, cancel=event)
        self.assertEqual(caught.exception.issue.code, IssueCode.JOB_CANCELLED)
        calls = 0

        def cancel_after_checks():
            nonlocal calls
            calls += 1
            return calls >= 3

        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, cancel=cancel_after_checks)
        self.assertEqual(caught.exception.issue.code, IssueCode.JOB_CANCELLED)
        self.assertGreaterEqual(calls, 3)


if __name__ == "__main__":
    unittest.main()
