"""Regenerate input evidence with an independent EXIF transpose reference."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests/engine"))
from test_vectorize_input import asymmetric_image, encoded_with_orientation, visual_pixels
from test_vectorize import png
from vectorize.image_input import MAX_INPUT_BYTES, MAX_INPUT_PIXELS, decode_raster
from vectorize import VectorizeFailure
from PIL import Image, __version__ as pillow_version


def matrix():
    rows = []
    for media_type in ("image/png", "image/jpeg"):
        for orientation in range(1, 9):
            data = encoded_with_orientation(asymmetric_image(), orientation, media_type)
            before = hashlib.sha256(data).hexdigest()
            expected = visual_pixels(data, orientation)
            value = decode_raster(data, media_type)
            with Image.open(BytesIO(value.analysis_png())) as analysis:
                analysis_pixels = analysis.convert("RGBA").tobytes()
            row = {"media_type": media_type, "orientation": orientation, "size": value.size,
                   "original_before": before, "original_after": hashlib.sha256(data).hexdigest(),
                   "expected_pixels": hashlib.sha256(expected.tobytes()).hexdigest(),
                   "observed_pixels": hashlib.sha256(value.rgba.tobytes()).hexdigest(),
                   "analysis_pixels": hashlib.sha256(analysis_pixels).hexdigest()}
            assert row["original_before"] == row["original_after"] == value.sha256
            assert row["expected_pixels"] == row["observed_pixels"] == row["analysis_pixels"]
            rows.append(row)
    return rows


def controlled_failures():
    rows = []
    broken = (b"Exif\0\0bad", b"Exif\0\0II*\0\xff\xff\xff\x7f", b"Exif\0\0II*\0\x08\0\0\0\x01\0")
    for media_type, image_format in (("image/png", "PNG"), ("image/jpeg", "JPEG")):
        for index, exif in enumerate(broken):
            output = BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)  # malformed fixture encoding, not the decoder
                asymmetric_image().convert("RGB").save(output, format=image_format, exif=exif)
            data = output.getvalue()
            before = hashlib.sha256(data).hexdigest()
            try:
                decode_raster(data, media_type)
                raise AssertionError("Corrupt EXIF was accepted")
            except VectorizeFailure as failure:
                assert failure.issue.evidence["reason"] == "invalid_exif"
                rows.append({"media_type": media_type, "corrupt_case": index,
                             "code": failure.issue.code, "reason": failure.issue.evidence["reason"],
                             "original_before": before, "original_after": hashlib.sha256(data).hexdigest()})
    return rows


if __name__ == "__main__":
    output = {"simulated": False, "fixture": "synthetic asymmetric decoded pixels; no AI", "pillow": pillow_version,
              "max_bytes": MAX_INPUT_BYTES, "max_pixels": MAX_INPUT_PIXELS,
              "orientations": matrix(), "corrupt_exif": controlled_failures()}
    Path(__file__).with_name("matrix.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print("16 orientation cases and 6 corrupt EXIF cases verified; original SHA preserved")
