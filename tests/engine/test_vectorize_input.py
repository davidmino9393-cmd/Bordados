"""Shared raster limits and EXIF coordinate frame, without changing originals."""
import hashlib
from io import BytesIO
import threading
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from test_vectorize import asset, png, result_for, settings
from embroidery_contracts import IssueCode
from embroidery_contracts.base import BoundsPX
from vectorize import VectorizeFailure
from vectorize import segmentation
from vectorize.image_input import MAX_INPUT_BYTES, MAX_INPUT_PIXELS, decode_raster

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
ORIENTATION_TRANSFORMS = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def encoded_with_orientation(image, orientation, media_type="image/png"):
    output = BytesIO()
    exif = Image.Exif()
    exif[274] = orientation
    if media_type == "image/jpeg":
        image.convert("RGB").save(output, format="JPEG", quality=100, subsampling=0, exif=exif)
    else:
        image.save(output, format="PNG", exif=exif)
    return output.getvalue()


def visual_pixels(data, orientation):
    """Independent EXIF reference: decode once and apply the specified transpose."""
    with Image.open(BytesIO(data)) as image:
        rgba = image.convert("RGBA")
    operation = ORIENTATION_TRANSFORMS.get(orientation)
    return rgba.transpose(operation) if operation is not None else rgba


def oriented_asset(data, orientation, media_type="image/png", crop=None):
    width, height = visual_pixels(data, orientation).size
    return asset(data, media_type).model_copy(update={
        "original_width_px": width, "original_height_px": height, "crop_px": crop,
    })


def asymmetric_image():
    image = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 4, 2), fill=(18, 40, 90, 255))
    draw.rectangle((7, 3, 9, 6), fill=(240, 90, 20, 255))
    return image


class RasterInputTests(unittest.TestCase):
    def test_engine_imports_the_shared_helper_limits(self):
        # The API catalogue integration belongs to Claude; this test verifies the delivered engine boundary.
        self.assertEqual((MAX_INPUT_BYTES, MAX_INPUT_PIXELS), (MAX_BYTES, MAX_PIXELS))
        self.assertEqual((segmentation.MAX_INPUT_BYTES, segmentation.MAX_INPUT_PIXELS), (MAX_BYTES, MAX_PIXELS))

    def test_upload_one_byte_over_the_shared_limit_is_rejected_before_decoding(self):
        original = png(Image.new("RGB", (2, 2), "blue"))
        data = original + b"\0" * (MAX_BYTES + 1 - len(original))
        source = asset(original).model_copy(update={"sha256": hashlib.sha256(data).hexdigest()})
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, source=source)
        self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_TOO_LARGE)
        self.assertEqual(caught.exception.issue.evidence["reason"], "byte_limit")

    def test_pixel_limit_is_inclusive_and_checked_before_expensive_vectorization(self):
        data = png(Image.new("RGB", (4000, 5000), "blue"))
        self.assertEqual(segmentation.decode(data, "image/png", asset(data), None).size, (4000, 5000))
        # A genuine one-bit PNG keeps this 20,000,001-pixel boundary fixture small in memory and on disk.
        data = png(Image.new("1", (MAX_PIXELS + 1, 1), 1))
        source = asset(data)
        with patch("PIL.PngImagePlugin.PngImageFile.load", side_effect=AssertionError("pixels loaded before cap")) as loaded:
            with self.assertRaises(VectorizeFailure) as caught:
                segmentation.decode(data, "image/png", source, None)
            loaded.assert_not_called()
        self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_TOO_LARGE)
        self.assertEqual(caught.exception.issue.evidence["reason"], "pixel_limit")
        self.assertEqual(caught.exception.issue.evidence["limit"], MAX_PIXELS)

    def test_all_exif_orientations_preserve_decoded_pixels_without_a_lossy_roundtrip(self):
        for media_type in ("image/png", "image/jpeg"):
            for orientation in range(1, 9):
                with self.subTest(media_type=media_type, orientation=orientation):
                    data = encoded_with_orientation(asymmetric_image(), orientation, media_type)
                    source = oriented_asset(data, orientation, media_type)
                    original_hash = hashlib.sha256(data).hexdigest()
                    original_metadata = source.model_dump()
                    expected = visual_pixels(data, orientation)
                    normalized = segmentation.decode(data, media_type, source, None)
                    self.assertEqual(normalized.mode, "RGBA")
                    self.assertEqual(normalized.size, expected.size)
                    self.assertEqual(normalized.tobytes(), expected.tobytes())
                    self.assertEqual(hashlib.sha256(data).hexdigest(), original_hash)
                    self.assertEqual(source.model_dump(), original_metadata)

    def test_analysis_png_has_identical_oriented_pixels_and_no_orientation_tag(self):
        for media_type in ("image/png", "image/jpeg"):
            for orientation in range(1, 9):
                with self.subTest(media_type=media_type, orientation=orientation):
                    data = encoded_with_orientation(asymmetric_image(), orientation, media_type)
                    original_sha = hashlib.sha256(data).hexdigest()
                    value = decode_raster(data, media_type)
                    expected = visual_pixels(data, orientation)
                    self.assertIsNone(value.rgba.getexif().get(274))
                    analysis = value.analysis_png()
                    self.assertEqual(analysis, value.analysis_png())
                    with Image.open(BytesIO(analysis)) as observed:
                        self.assertEqual(observed.format, "PNG")
                        self.assertIsNone(observed.getexif().get(274))
                        self.assertEqual(observed.size, expected.size)
                        self.assertEqual(observed.convert("RGBA").tobytes(), expected.tobytes())
                    second = decode_raster(analysis, "image/png")
                    self.assertEqual(second.rgba.tobytes(), expected.tobytes())
                    self.assertEqual(value.sha256, original_sha)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), original_sha)

    def test_without_exif_defaults_to_identity_and_does_not_mutate_pixels(self):
        data = png(asymmetric_image())
        value = decode_raster(data, "image/png")
        self.assertEqual((value.raw_size, value.size, value.orientation), ((12, 8), (12, 8), 1))
        self.assertEqual(value.rgba.tobytes(), asymmetric_image().tobytes())

    def test_corrupt_exif_is_a_controlled_failure_in_both_formats(self):
        broken = (
            b"Exif\0\0bad",
            b"Exif\0\0II*\0\xff\xff\xff\x7f",
            b"Exif\0\0II*\0\x08\0\0\0\x01\0",
        )
        for media_type, image_format in (("image/png", "PNG"), ("image/jpeg", "JPEG")):
            for exif in broken:
                with self.subTest(media_type=media_type, exif=exif):
                    output = BytesIO()
                    asymmetric_image().convert("RGB").save(output, format=image_format, exif=exif)
                    data = output.getvalue()
                    original_sha = hashlib.sha256(data).hexdigest()
                    with self.assertRaises(VectorizeFailure) as caught:
                        decode_raster(data, media_type)
                    self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNREADABLE)
                    self.assertEqual(caught.exception.issue.evidence["reason"], "invalid_exif")
                    self.assertEqual(hashlib.sha256(data).hexdigest(), original_sha)

    def test_invalid_orientation_is_rejected_instead_of_guessing(self):
        for orientation in (0, 9):
            data = encoded_with_orientation(asymmetric_image(), orientation)
            with self.assertRaises(VectorizeFailure) as caught:
                decode_raster(data, "image/png")
            self.assertEqual(caught.exception.issue.evidence["reason"], "invalid_exif")

    def test_unsupported_types_including_webp_are_rejected_before_pillow(self):
        for media_type in ("image/webp", "image/svg+xml", "image/gif", "application/octet-stream"):
            with self.subTest(media_type=media_type), patch("vectorize.image_input.Image.open") as opened:
                with self.assertRaises(VectorizeFailure) as caught:
                    decode_raster(b"unsupported", media_type)
                self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNSUPPORTED_FORMAT)
                self.assertEqual(caught.exception.issue.evidence["reason"], "unsupported_media_type")
                self.assertEqual(caught.exception.issue.evidence["media_type"], media_type)
                opened.assert_not_called()

    def test_byte_limit_precedes_pillow_and_accepts_the_exact_boundary(self):
        original = png(asymmetric_image())
        exact = original + b"\0" * (MAX_BYTES - len(original))
        self.assertEqual(decode_raster(exact, "image/png").size, (12, 8))
        with patch("vectorize.image_input.Image.open") as opened:
            with self.assertRaises(VectorizeFailure) as caught:
                decode_raster(exact + b"\0", "image/png")
            self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_TOO_LARGE)
            opened.assert_not_called()

    def test_decoder_bomb_protection_is_not_disabled(self):
        data = png(Image.new("RGB", (4, 4), "blue"))
        for warning_threshold in (8, 2):
            with self.subTest(warning_threshold=warning_threshold), patch.object(Image, "MAX_IMAGE_PIXELS", warning_threshold):
                with self.assertRaises(VectorizeFailure) as caught:
                    decode_raster(data, "image/png")
                self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_TOO_LARGE)
                self.assertEqual(caught.exception.issue.evidence["reason"], "decoder_pixel_limit")

    def test_animation_and_mime_mismatch_remain_controlled(self):
        output = BytesIO()
        first = Image.new("RGBA", (3, 3), "blue")
        first.save(output, "PNG", save_all=True, append_images=[Image.new("RGBA", (3, 3), "red")])
        for data, media_type, reason in ((output.getvalue(), "image/png", "animated_input"),
                                        (png(first), "image/jpeg", "decoded_format_mismatch")):
            with self.subTest(reason=reason), self.assertRaises(VectorizeFailure) as caught:
                decode_raster(data, media_type)
            self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNREADABLE)
            self.assertEqual(caught.exception.issue.evidence["reason"], reason)

    def test_vectorization_uses_visual_frame_for_geometry_and_contain_after_exif(self):
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                data = encoded_with_orientation(asymmetric_image(), orientation)
                expected = result_for(png(visual_pixels(data, orientation)), configuration=settings(60, 80, 2))
                actual = result_for(data, source=oriented_asset(data, orientation), configuration=settings(60, 80, 2))
                self.assertEqual(actual.document.objects, expected.document.objects)
                self.assertEqual(actual.document.coordinates, expected.document.coordinates)
                self.assertEqual(actual.document.object_bounds_mm, expected.document.object_bounds_mm)

    def test_crop_coordinates_are_applied_after_exif_normalization(self):
        data = encoded_with_orientation(asymmetric_image(), 6)
        crop = BoundsPX(x_px=1, y_px=2, width_px=6, height_px=8)
        source = oriented_asset(data, 6, crop=crop)
        normalized = png(visual_pixels(data, 6))
        expected = result_for(normalized, source=asset(normalized, crop=crop), configuration=settings(60, 80, 2))
        actual = result_for(data, source=source, configuration=settings(60, 80, 2))
        self.assertEqual(actual.document.objects, expected.document.objects)
        self.assertEqual(actual.document.coordinates, expected.document.coordinates)
        self.assertEqual(actual.document.object_bounds_mm, expected.document.object_bounds_mm)

    def test_raw_dimensions_are_rejected_if_exif_swaps_the_visual_dimensions(self):
        data = encoded_with_orientation(asymmetric_image(), 6)
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, source=asset(data))
        self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNREADABLE)
        self.assertEqual(caught.exception.issue.evidence["reason"], "asset_dimensions_mismatch")

    def test_cancellation_precedes_normalization_and_retains_original_identity_checks(self):
        data = encoded_with_orientation(asymmetric_image(), 8)
        source = oriented_asset(data, 8)
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, source=source, cancel=cancel)
        self.assertEqual(caught.exception.issue.code, IssueCode.JOB_CANCELLED)
        with self.assertRaises(VectorizeFailure) as caught:
            result_for(data, source=source.model_copy(update={"sha256": "0" * 64}))
        self.assertEqual(caught.exception.issue.code, IssueCode.INPUT_UNREADABLE)
        self.assertEqual(caught.exception.issue.evidence["reason"], "asset_identity_mismatch")


if __name__ == "__main__":
    unittest.main()
