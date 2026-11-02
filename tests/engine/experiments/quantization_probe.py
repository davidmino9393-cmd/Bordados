"""Compare Pillow quantizers on E's unchanged foreground; never select production policy."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageStat, __version__ as PILLOW_VERSION

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages/contracts"))
sys.path.insert(0, str(ROOT / "workers/embroidery"))
from vectorize.segmentation import MAX_INPUT_BYTES, MAX_INPUT_PIXELS, _foreground

METHODS = {
    "baseline_mediancut": (Image.Quantize.MEDIANCUT, 0),
    "mediancut_kmeans3": (Image.Quantize.MEDIANCUT, 3),
    "maximum_coverage": (Image.Quantize.MAXCOVERAGE, 0),
}
CONTRAST_THRESHOLD = 192


def compare(path, colors, output):
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Research probe input exceeds E's byte limit")
    data = path.read_bytes()
    with Image.open(BytesIO(data)) as source:
        if source.format not in {"PNG", "JPEG"} or source.width * source.height > MAX_INPUT_PIXELS:
            raise ValueError("Research probe requires PNG/JPEG within E's pixel limit")
        rgba = source.convert("RGBA")
    rgb, mask, segmentation = _foreground(rgba)
    visibility, pixels = mask.tobytes(), rgb.tobytes()
    selected = [index for index, visible in enumerate(visibility) if visible]
    if not selected:
        raise ValueError("No foreground pixels")
    compact = b"".join(pixels[i * 3:i * 3 + 3] for i in selected)
    foreground = Image.frombytes("RGB", (len(selected), 1), compact)
    source_luma = foreground.convert("L").tobytes()
    dark = [value < CONTRAST_THRESHOLD for value in source_luma]
    records = {}
    output.mkdir(parents=True, exist_ok=True)
    rgba.thumbnail((500, 500))
    rgba.save(output / "source.png")
    for name, (method, kmeans) in METHODS.items():
        quantized = foreground.quantize(colors=colors, method=method, kmeans=kmeans, dither=Image.Dither.NONE)
        result_rgb = quantized.convert("RGB")
        result_luma = result_rgb.convert("L").tobytes()
        records[name] = {
            "kmeans": kmeans,
            "palette": sorted({"#%02x%02x%02x" % color for _, color in result_rgb.getcolors(maxcolors=256)}),
            "mean_absolute_rgb_error": sum(ImageStat.Stat(ImageChops.difference(foreground, result_rgb)).mean) / 3,
            "output_contrast_pixels": sum(value < CONTRAST_THRESHOLD for value in result_luma),
            "source_contrast_pixels_retained": sum(was_dark and now < CONTRAST_THRESHOLD
                                                    for was_dark, now in zip(dark, result_luma)),
        }
        expanded = bytearray(len(visibility) * 4)
        rgb_bytes = result_rgb.tobytes()
        for offset, index in enumerate(selected):
            expanded[index * 4:index * 4 + 4] = rgb_bytes[offset * 3:offset * 3 + 3] + b"\xff"
        preview = Image.frombytes("RGBA", rgb.size, bytes(expanded))
        preview.thumbnail((500, 500))
        preview.save(output / (name + ".png"))
    report = {
        "experiment_only": True, "production_baseline_commit": "4a7fd6b",
        "input_sha256": hashlib.sha256(data).hexdigest(), "pillow": PILLOW_VERSION,
        "color_limit": colors, "foreground_pixels": len(selected),
        "foreground_mask_sha256": hashlib.sha256(visibility).hexdigest(),
        "background_evidence": segmentation,
        "contrast_threshold_luma_8bit": CONTRAST_THRESHOLD,
        "source_contrast_pixels": sum(dark), "methods": records,
        "mask_and_source_resolution_unchanged": True,
        "previews_resized_only_for_display": True,
        "iou_holes_text_and_physical_quality_evaluated": False,
    }
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--colors", type=int, choices=range(1, 257), required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.image, args.colors, args.output)))


if __name__ == "__main__":
    main()
