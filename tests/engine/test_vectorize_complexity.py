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
                # Con la paleta sin refinar eran 425078 aristas (casi todo era ruido dentro de tres tonos casi blancos).
                self.assertEqual(sum(m["boundary_edges"] for m in evidence["masks"]), 110028)
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

    def test_reference_keeps_its_dark_strokes_in_the_palette(self):
        # Sin refinamiento k-means el fondo tonal casi blanco se quedaba con los tres colores y los trazos malva desaparecían.
        data = (ROOT / "tests/fixtures/h2/Anime_Socks.png").read_bytes()
        segmentation = result_for(data, source=asset(data), configuration=settings(150, 142.8, 3)).evidence["segmentation"]
        luma = [0.299 * int(c[1:3], 16) + 0.587 * int(c[3:5], 16) + 0.114 * int(c[5:7], 16) for c in segmentation["output_colours"]]
        self.assertLess(min(luma), 160)
        self.assertIn("kmeans=3", segmentation["quantizer"])

    def test_flat_colour_survives_anti_aliased_edges_exactly(self):
        # El promedio del grupo mezcla el azul con los píxeles suavizados del borde y lo aclara; la mediana conserva el color real.
        navy = (20, 40, 90)
        big = Image.new("RGB", (400, 400), "white")
        from PIL import ImageDraw
        ImageDraw.Draw(big).ellipse((40, 40, 360, 360), fill=navy)
        image = big.resize((100, 100), Image.Resampling.LANCZOS)  # bordes suavizados
        result = result_for(png(image), configuration=settings(colors=1))
        self.assertEqual([o.work_color for o in result.document.objects], ["#14285a"])
        self.assertIn("median member", result.evidence["segmentation"]["quantizer"])

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
