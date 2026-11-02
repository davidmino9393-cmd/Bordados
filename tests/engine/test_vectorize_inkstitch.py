"""The E adapter preserves geometry and requires an explicit H3 handoff."""
import unittest
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

from test_vectorize import SVG, png, result_for, settings
from embroidery_contracts import EmbroideryDocument, IssueCode
from embroidery_contracts.design import StitchParameters
from vectorize import VectorizeFailure
from vectorize.inkstitch import to_inkstitch_svg

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


if __name__ == "__main__":
    unittest.main()
