"""Política de ancho mínimo bordable: se mide y se avisa; nunca se borra ni se engrosa nada."""
from array import array
import math
import random
from types import SimpleNamespace
import unittest

from PIL import Image, ImageDraw

from test_vectorize import asset, png, result_for, settings
from embroidery_contracts import IssueCode
from vectorize.segmentation import BACKGROUND
from vectorize.thin_features import measure as measure_mask, _opening


def image_with(draw):
    image = Image.new("RGB", (200, 100), "white")
    draw(ImageDraw.Draw(image))
    return image


def measure(image, width_mm):
    # 200 px a `width_mm` mm: con 20 mm cada píxel mide 0,1 mm y el ancho mínimo (0,4 mm) son 4 px.
    data = png(image)
    return result_for(data, source=asset(data), configuration=settings(width_mm, width_mm / 2, 1))


def mask_evidence(image, mm_per_px):
    labels = array("H", (0 if pixel else BACKGROUND for pixel in image.tobytes()))
    segmented = SimpleNamespace(labels=labels, width=image.width, height=image.height, palette={0: "#14285a"})
    traced = [SimpleNamespace(color="#14285a", pixel_count=image.histogram()[255])]
    objects = [SimpleNamespace(object_id="measured_shape")]
    return measure_mask(segmented, traced, objects, mm_per_px)


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

    def test_a_shape_smaller_than_the_kernel_is_all_thin_even_at_the_page_border(self):
        image = Image.new("RGB", (8, 8), (20, 40, 90))
        data = png(image)
        feature = result_for(data, source=asset(data), configuration=settings(.08, .08, 1)).evidence["minimum_feature"]
        self.assertEqual(feature["structuring_element_px"], 40)
        self.assertEqual(feature["objects"][next(iter(feature["objects"]))]["thin_fraction"], 1)

    def test_even_width_at_the_threshold_is_not_reported_as_thinner(self):
        for width, mm_per_px in ((2, .2), (4, .1)):
            for actual_width in (width - 1, width):
                for start in (0, 5):
                    image = Image.new("L", (20, 20), 0)
                    ImageDraw.Draw(image).rectangle((0, start, 19, start + actual_width - 1), fill=255)
                    with self.subTest(width=width, actual_width=actual_width, start=start):
                        feature = mask_evidence(image, mm_per_px)
                        self.assertEqual(feature["structuring_element_px"], width)
                        self.assertAlmostEqual(feature["effective_test_width_mm"], .4)
                        self.assertEqual(feature["objects"]["measured_shape"]["thin_fraction"],
                                         1 if actual_width < width else 0)

    def test_extremely_small_scale_is_measured_without_allocating_a_giant_kernel(self):
        image = Image.new("L", (8, 8), 255)
        feature = mask_evidence(image, 1e-9)
        self.assertGreaterEqual(feature["structuring_element_px"], 400000000)
        self.assertEqual(feature["objects"]["measured_shape"]["thin_pixels"], 64)

    def test_threshold_product_prevents_division_roundoff_from_adding_a_pixel(self):
        width = 253
        mm_per_px = .4 / width
        self.assertGreater(.4 / mm_per_px, width)
        self.assertEqual(width * mm_per_px, .4)
        image = Image.new("L", (width, width), 255)
        feature = mask_evidence(image, mm_per_px)
        self.assertEqual(feature["structuring_element_px"], width)
        self.assertEqual(feature["objects"]["measured_shape"]["thin_fraction"], 0)
        below = math.nextafter(mm_per_px, 0)
        self.assertLess(width * below, .4)
        feature = mask_evidence(image, below)
        self.assertEqual(feature["structuring_element_px"], width + 1)
        self.assertEqual(feature["objects"]["measured_shape"]["thin_fraction"], 1)

    def test_opening_handles_even_kernel_without_shifting_the_shape(self):
        image = Image.new("L", (15, 12), 0)
        ImageDraw.Draw(image).rectangle((3, 4, 10, 7), fill=255)
        opened = _opening(image, 4, None)
        self.assertEqual(opened.tobytes(), image.tobytes())

    def test_opening_matches_independent_finite_mask_reference(self):
        random_source = random.Random(20261102)
        for element in (2, 3, 4, 5, 8):
            for _ in range(10):
                width, height = 8, 7
                pixels = {(x, y) for y in range(height) for x in range(width)
                          if random_source.random() < .7}
                low = (element - 1) // 2
                offsets = [(x, y) for y in range(-low, element - low)
                           for x in range(-low, element - low)]
                eroded = {(x, y) for y in range(height) for x in range(width)
                          if all((x + dx, y + dy) in pixels for dx, dy in offsets)}
                expected = {(x, y) for y in range(height) for x in range(width)
                            if any((x - dx, y - dy) in eroded for dx, dy in offsets)}
                image = Image.new("L", (width, height), 0)
                for point in pixels:
                    image.putpixel(point, 255)
                actual = _opening(image, element, None)
                found = {(x, y) for y in range(height) for x in range(width)
                         if actual.getpixel((x, y))}
                self.assertEqual(found, expected, element)


if __name__ == "__main__":
    unittest.main()
