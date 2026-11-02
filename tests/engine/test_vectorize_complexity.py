"""Regression for F's real complexity finding; no original scripts are run."""
import unittest

from PIL import Image

from test_vectorize import ROOT, asset, png, result_for, settings
from vectorize import VectorizeFailure
from embroidery_contracts import IssueCode


class ComplexityTests(unittest.TestCase):
    def test_reference_can_be_traced_at_both_sizes_without_dropping_edges(self):
        data = (ROOT / "tests/fixtures/h2/Anime_Socks.png").read_bytes()
        masks = []
        for width, height in ((150, 142.8), (126.2, 120)):
            with self.subTest(target=(width, height)):
                result = result_for(data, source=asset(data), configuration=settings(width, height, 3))
                evidence = result.evidence
                self.assertEqual(sum(m["boundary_edges"] for m in evidence["masks"]), 425078)
                self.assertEqual(sum(m["pixel_count"] for m in evidence["masks"]),
                                 evidence["segmentation"]["foreground_pixels"])
                self.assertEqual(evidence["segmentation"]["pixels_discarded_by_size_filter"], 0)
                self.assertIn(IssueCode.DENSITY_REVIEW_REQUIRED, {i.code for i in result.issues})
                self.assertIn(IssueCode.VISUAL_MISMATCH, {i.code for i in result.issues})
                self.assertTrue(evidence["h3_validation_required"])
                bounds = result.document.object_bounds_mm
                self.assertLessEqual(bounds.max_x_mm, width + 1e-8)
                self.assertLessEqual(bounds.max_y_mm, height + 1e-8)
                masks.append(evidence["segmentation"]["source_mask_sha256"])
        self.assertEqual(masks[0], masks[1])

    def test_excessive_complexity_still_fails_without_simplifying_input(self):
        image = Image.new("RGBA", (512, 512))
        image.putdata([(0, 0, 255, 255) if (x + y) % 2 else (0, 0, 0, 0)
                       for y in range(image.height) for x in range(image.width)])
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(png(image), configuration=settings(colors=1))
        self.assertEqual(caught.exception.code, IssueCode.GEOMETRY_INVALID)
        self.assertEqual(caught.exception.issue.evidence["reason"], "boundary_edge_limit")


if __name__ == "__main__":
    unittest.main()
