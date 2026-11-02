"""Pruebas de la medición de topología con máscaras de las que se conoce la respuesta."""
import unittest

import topology
from PIL import Image, ImageDraw


def mask(size, draw):
    image = Image.new("L", size, 0)
    draw(ImageDraw.Draw(image))
    return image


class TopologyTests(unittest.TestCase):
    def test_a_ring_has_one_component_and_one_hole_with_its_area(self):
        ring = mask((20, 20), lambda d: (d.rectangle((2, 2, 17, 17), fill=255), d.rectangle((6, 6, 13, 13), fill=0)))
        shape = topology.topology(ring)
        self.assertEqual(len(shape["components"]), 1)
        self.assertEqual(shape["holes"], [64])

    def test_the_background_outside_the_shape_is_not_a_hole(self):
        self.assertEqual(topology.topology(mask((10, 10), lambda d: d.rectangle((3, 3, 6, 6), fill=255)))["holes"], [])

    def test_a_shape_touching_the_border_opens_its_inside_to_the_background(self):
        c_shape = mask((10, 10), lambda d: (d.rectangle((0, 0, 9, 9), fill=255), d.rectangle((3, 3, 9, 6), fill=0)))
        self.assertEqual(topology.topology(c_shape)["holes"], [])  # el hueco llega al borde derecho

    def test_foreground_is_eight_connected_and_holes_are_four_connected(self):
        diagonal = mask((6, 6), lambda d: (d.point((1, 1), fill=255), d.point((2, 2), fill=255)))
        self.assertEqual(len(topology.topology(diagonal)["components"]), 1)
        # Un anillo cerrado solo por una diagonal deja el centro como hueco 4-conexo.
        leaky = mask((7, 7), lambda d: (d.rectangle((1, 1), fill=255) if False else None, d.polygon([(3, 1), (5, 3), (3, 5), (1, 3)], fill=255), d.point((3, 3), fill=0)))
        self.assertEqual(len(topology.topology(leaky)["holes"]), 1)

    def test_summary_counts_by_minimum_area(self):
        two_holes = mask((30, 12), lambda d: (d.rectangle((0, 0, 29, 11), fill=255), d.rectangle((2, 2, 3, 3), fill=0), d.rectangle((10, 2, 20, 9), fill=0)))
        self.assertEqual(topology.summary(topology.topology(two_holes))["holes"], {">=1px": 2, ">=4px": 2, ">=16px": 1, ">=64px": 1})


if __name__ == "__main__":
    unittest.main()
