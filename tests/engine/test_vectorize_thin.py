"""Política de ancho mínimo bordable: se mide y se avisa; nunca se borra ni se engrosa nada."""
import unittest

from PIL import Image, ImageDraw

from test_vectorize import asset, png, result_for, settings
from embroidery_contracts import IssueCode


def image_with(draw):
    image = Image.new("RGB", (200, 100), "white")
    draw(ImageDraw.Draw(image))
    return image


def measure(image, width_mm):
    # 200 px a `width_mm` mm: con 20 mm cada píxel mide 0,1 mm y el ancho mínimo (0,4 mm) son 4 px.
    data = png(image)
    return result_for(data, source=asset(data), configuration=settings(width_mm, width_mm / 2, 1))


class ThinFeatureTests(unittest.TestCase):
    def test_a_line_thinner_than_the_minimum_is_all_thin_and_a_wide_block_is_not(self):
        thin_line = image_with(lambda d: d.rectangle((10, 48, 190, 49), fill=(20, 40, 90)))        # 2 px = 0,2 mm
        wide_block = image_with(lambda d: d.rectangle((20, 20, 180, 80), fill=(20, 40, 90)))       # 160 x 60 px
        thin = measure(thin_line, 20).evidence["minimum_feature"]
        wide = measure(wide_block, 20).evidence["minimum_feature"]
        self.assertTrue(thin["measurable"] and wide["measurable"])
        self.assertEqual((thin["min_width_mm"], thin["min_width_mm_is_calibrated"]), (0.4, False))
        (thin_object,), (wide_object,) = thin["objects"].values(), wide["objects"].values()
        self.assertEqual(thin_object["thin_fraction"], 1.0)
        self.assertEqual(wide_object["thin_fraction"], 0.0)

    def test_nothing_is_removed_or_thickened_by_the_measurement(self):
        thin_line = image_with(lambda d: d.rectangle((10, 48, 190, 49), fill=(20, 40, 90)))
        result = measure(thin_line, 20)
        self.assertEqual(result.evidence["minimum_feature"]["policy"], "measure_and_report_never_remove_or_thicken")
        self.assertEqual(result.evidence["segmentation"]["pixels_discarded_by_size_filter"], 0)
        self.assertEqual(result.evidence["masks"][0]["pixel_count"], 181 * 2)  # los píxeles de la línea, sin tocar

    def test_the_review_issue_carries_the_fractions_per_object(self):
        thin_line = image_with(lambda d: d.rectangle((10, 48, 190, 49), fill=(20, 40, 90)))
        result = measure(thin_line, 20)
        issue = next(i for i in result.issues if i.code == IssueCode.DENSITY_REVIEW_REQUIRED)
        self.assertEqual(issue.evidence["minimum_feature_mm"], 0.4)
        self.assertFalse(issue.evidence["minimum_feature_is_calibrated"])
        self.assertEqual(set(issue.evidence["thin_feature_fraction_by_object"]), set(issue.object_ids))
        self.assertIn(1.0, issue.evidence["thin_feature_fraction_by_object"].values())

    def test_a_resolution_too_coarse_to_measure_says_so_instead_of_guessing(self):
        coarse = image_with(lambda d: d.rectangle((50, 20, 150, 80), fill=(20, 40, 90)))
        feature = measure(coarse, 2000).evidence["minimum_feature"]  # 10 mm por píxel
        self.assertFalse(feature["measurable"])
        self.assertEqual(feature["objects"], {})


if __name__ == "__main__":
    unittest.main()
