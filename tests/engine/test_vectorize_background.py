"""Un fondo de color (papel beige, gris, un color liso) no se borda: es la tela, igual que un fondo blanco.

Caso real que salió mal: un logo de tres colores sobre papel beige con grano; con 3 hilos, el beige se llevó uno, el celeste
quedó afuera y el 81 % de las puntadas rellenaban el fondo.
"""
from pathlib import Path
import random
import sys
import unittest

from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_vectorize import asset, path_polygons, png, result_for, settings  # noqa: E402

BLACK, YELLOW, TEAL = (10, 10, 10), (232, 192, 106), (104, 170, 182)
PAPER = (211, 204, 195)
SVG = "{http://www.w3.org/2000/svg}"


def textured(color, size=(240, 320), grain=14, seed=7):
    """Un fondo de papel: el color con grano, como el de un archivo escaneado o un mockup."""
    rng = random.Random(seed)
    image = Image.new("RGB", size, color)
    pixels = image.load()
    for y in range(size[1]):
        for x in range(size[0]):
            shift = rng.randint(-grain, grain)
            pixels[x, y] = tuple(max(0, min(255, channel + shift)) for channel in color)
    return image


def logo_on(background, size=(240, 320)):
    """Una «D» de tres colores: contorno negro, mitad amarilla y mitad celeste, con el hueco de la D sobre el fondo."""
    image = textured(background, size) if isinstance(background, tuple) else background
    hole = image.getpixel((5, 5))
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 90, 190, 230), fill=BLACK)
    draw.rectangle((60, 100, 120, 220), fill=YELLOW)
    draw.rectangle((120, 100, 180, 220), fill=TEAL)
    draw.rectangle((100, 140, 140, 180), fill=hole)  # el hueco: se ve el fondo
    return image


def colors_of(result):
    return {tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) for value in result.evidence["segmentation"]["output_colours"]}


def distance(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


class BackgroundTests(unittest.TestCase):
    def run_e1(self, image, colors=3):
        data = png(image)
        return result_for(data, source=asset(data), configuration=settings(80, 80, colors))

    def test_a_beige_textured_background_is_not_stitched_and_the_three_real_colours_are_kept(self):
        result = self.run_e1(logo_on(PAPER))
        evidence = result.evidence["segmentation"]
        self.assertEqual(evidence["background_method"], "border_color_consensus")
        self.assertLessEqual(distance(tuple(evidence["background_color"]), PAPER), 6)
        found = colors_of(result)
        for wanted in (BLACK, YELLOW, TEAL):  # los tres hilos son los del diseño
            self.assertTrue(any(distance(color, wanted) <= 12 for color in found), f"falta {wanted}: {sorted(found)}")
        self.assertFalse(any(distance(color, PAPER) <= 40 for color in found), f"el fondo quedó como hilo: {sorted(found)}")
        self.assertEqual(len(found), 3)

    def test_what_is_stitched_is_the_design_and_not_the_whole_picture(self):
        result = self.run_e1(logo_on(PAPER))
        points = [point for element in ET.fromstring(result.editable_svg).iter(SVG + "path")
                  for polygon in path_polygons(element.get("d")) for point in polygon]
        xs, ys = [point[0] for point in points], [point[1] for point in points]
        # 240 x 320 px a 0,25 mm/px: la imagen entera mediría 60 x 80 mm; el cuadrado del diseño, 35 x 35 mm.
        self.assertLessEqual(max(xs) - min(xs), 37)
        self.assertLessEqual(max(ys) - min(ys), 37)
        foreground = result.evidence["segmentation"]["foreground_pixels"]
        self.assertTrue(17500 <= foreground <= 18800, f"{foreground} píxeles de diseño (la imagen entera tiene {240 * 320})")  # sin el fondo ni el hueco

    def test_other_flat_backgrounds_behave_the_same(self):
        for name, background in (("gris", (150, 150, 150)), ("celeste claro", (190, 215, 235)), ("negro", (12, 12, 12))):
            with self.subTest(name):
                image = logo_on(background)
                ImageDraw.Draw(image).rectangle((50, 90, 190, 230), fill=(240, 240, 240) if name == "negro" else BLACK)  # sobre negro, un cuadrado claro
                result = self.run_e1(image, colors=3)
                self.assertEqual(result.evidence["segmentation"]["background_method"], "border_color_consensus")
                self.assertFalse(any(distance(color, background) <= 40 for color in colors_of(result)))

    def test_a_white_background_is_handled_as_before(self):
        flat_white = Image.new("RGB", (240, 320), (255, 255, 255))
        result = self.run_e1(logo_on(flat_white))
        self.assertEqual(result.evidence["segmentation"]["background_method"], "white_border_consensus")

    def test_a_design_that_fills_the_picture_keeps_its_colour_as_a_colour(self):
        """Si el color del borde no es parejo (el diseño llega hasta el borde) no se toma nada por fondo."""
        image = Image.new("RGB", (240, 320), YELLOW)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 120, 320), fill=TEAL)  # la mitad del borde es de cada color: no hay consenso
        draw.rectangle((60, 100, 180, 220), fill=BLACK)
        result = self.run_e1(image)
        self.assertEqual(result.evidence["segmentation"]["background_method"], "no_background_removed")

    def test_it_does_not_erase_a_design_that_is_almost_the_background_colour(self):
        image = textured(PAPER, grain=3)
        ImageDraw.Draw(image).rectangle((60, 100, 180, 220), fill=(214, 207, 198))  # casi igual al fondo
        data = png(image)
        result = result_for(data, source=asset(data), configuration=settings(80, 80, 3))  # no falla por «sin píxeles de diseño»
        self.assertNotEqual(result.evidence["segmentation"]["background_method"], "border_color_consensus")


if __name__ == "__main__":
    unittest.main()
