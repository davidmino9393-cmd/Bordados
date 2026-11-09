"""The boundary-only Zhang-Suen thinning must delete exactly what the full scan deletes."""
from pathlib import Path
import random
import sys
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "workers/embroidery")]
from vectorize.reference_geometry import _thin

OFFSETS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))


def full_scan(image):
    """Previous implementation, kept verbatim as the reference."""
    width = image.width
    pixels = {(i % width, i // width) for i, value in enumerate(image.tobytes()) if value}
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            remove = set()
            for x, y in pixels:
                n = [int((x + dx, y + dy) in pixels) for dx, dy in OFFSETS]
                if not 2 <= sum(n) <= 6 or sum(not n[i] and n[(i + 1) % 8] for i in range(8)) != 1:
                    continue
                triples = ((0, 2, 4), (2, 4, 6)) if step == 0 else ((0, 2, 6), (0, 4, 6))
                if all(not n[a] * n[b] * n[c] for a, b, c in triples):
                    remove.add((x, y))
            pixels.difference_update(remove)
            changed |= bool(remove)
    return pixels


def shapes():
    solid = Image.new("L", (90, 70), 0)
    ImageDraw.Draw(solid).ellipse((5, 5, 85, 65), fill=255)
    ring = Image.new("L", (80, 80), 0)
    draw = ImageDraw.Draw(ring)
    draw.ellipse((4, 4, 76, 76), fill=255)
    draw.ellipse((22, 22, 58, 58), fill=0)
    yield "solid", solid
    yield "ring", ring
    generator = random.Random(6)
    for number in range(4):
        noisy = Image.new("L", (70, 60), 0)
        draw = ImageDraw.Draw(noisy)
        for _ in range(12):
            x, y = generator.randrange(60), generator.randrange(50)
            draw.rectangle((x, y, x + generator.randrange(2, 14), y + generator.randrange(2, 14)), fill=255)
            draw.line((x, y, generator.randrange(70), generator.randrange(60)), fill=255, width=generator.randrange(1, 5))
        yield f"noisy-{number}", noisy


class ThinEquivalenceTests(unittest.TestCase):
    def test_boundary_scan_equals_full_scan(self):
        for name, image in shapes():
            with self.subTest(shape=name):
                self.assertEqual(_thin(image, None), full_scan(image))


if __name__ == "__main__":
    unittest.main()
