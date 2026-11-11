"""Guía 1.3: la frase en curva de un sello se borda con una fuente de Ink/Stitch en lugar del trazo copiado (El Fortín).

Las pruebas de composición necesitan la fuente instalada con Ink/Stitch; usan el sello sintético de las pruebas de inscripciones.
"""
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_api import lettering
from embroidery_api.inscriptions import _arc
from embroidery_api.runner import JobRunner
from test_inscriptions import seal_png
from test_vectorize import result_for, settings
from vectorize.inkstitch import to_reference_inkstitch_svg

ENGINE = Path.home() / "AppData/Roaming/inkscape/extensions/inkstitch/inkstitch/bin/inkstitch.exe"
FONT = lettering.font_directory(ENGINE)
SVG = "{http://www.w3.org/2000/svg}"
PHRASE = "ESCUELA DE BORDADO"
CIRCLE_PX = (450, 450, 378)  # el aro exterior de seal_png (900 px): centro y radio exterior


class ArcTests(unittest.TestCase):
    def test_the_arc_comes_from_the_position_in_the_unrolled_ring_not_from_the_flip(self):
        steps = 1000  # la tira tiene dos vueltas: 2000 columnas
        self.assertEqual(_arc(750, 2000, steps, False), "top")       # 270°: arriba del centro (y hacia abajo)
        self.assertEqual(_arc(250, 2000, steps, False), "bottom")    # 90°
        self.assertEqual(_arc(2000 - 750, 2000, steps, True), "top")  # la tira volteada en horizontal cuenta al revés
        self.assertEqual(_arc(1750, 2000, steps, False), "top")      # segunda vuelta


@unittest.skipUnless((FONT / "font.json").is_file(), "La fuente de Ink/Stitch no está instalada")
class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = result_for(seal_png(), configuration=settings(80, 104, 2))
        cls.svg = to_reference_inkstitch_svg(cls.result)
        cls.circle = lettering.circle_to_mm(cls.result.document, CIRCLE_PX)

    def test_the_phrase_is_replaced_by_glyphs_inside_the_free_band_at_a_font_scale(self):
        found = lettering.find_arc_text(self.result.document, self.circle, "top")
        svg, evidence = lettering.apply(self.svg, self.result.document, [(PHRASE, self.circle, "top")], FONT)
        (item,) = evidence
        self.assertGreaterEqual(item["pieces_replaced"], len(PHRASE.replace(" ", "")) - 2)
        self.assertTrue(.5 <= item["scale"] <= 1.5, item)
        root = ET.fromstring(svg)
        kept = [p for p in root.iter(f"{SVG}path") if p.get("data-source-object-id") == found.object_id
                and p.get("data-source-ring-index") in found.rings]
        self.assertEqual(kept, [])  # no queda trazo copiado de la frase
        glyphs = [p for p in root.iter(f"{SVG}path") if p.get("data-lettering-font") == lettering.FONT_ID]
        self.assertEqual(len(glyphs), item["glyph_paths"])
        self.assertTrue(any(p.get("data-technique") == "satin" for p in glyphs))
        for path in glyphs:
            for x, y in (tuple(map(float, xy.split(","))) for xy in re.findall(r"-?\d+\.\d+,-?\d+\.\d+", path.get("d"))):
                r = math.dist(found.centre, (x, y))
                self.assertTrue(found.free_inner_mm - 1e-6 <= r <= found.free_outer_mm + 1e-6, (r, found))

    def test_an_arc_without_letters_is_reported_and_the_svg_is_left_alone(self):
        with self.assertRaises(lettering.LetteringUnavailable):
            lettering.apply(self.svg, self.result.document, [(PHRASE, self.circle, "bottom")], FONT)

    def test_a_character_the_font_lacks_is_refused(self):
        with self.assertRaisesRegex(lettering.LetteringUnavailable, "caracteres"):
            lettering.apply(self.svg, self.result.document, [("ESCUELA ☃", self.circle, "top")], FONT)

    def test_the_runner_uses_only_curved_phrases_chosen_for_letters_and_says_so(self):
        saved = {"inscription_1": {"detected": PHRASE, "confirmed": PHRASE, "use_font": True, "layout": "curved",
                                   "arc": "top", "circle_px": list(CIRCLE_PX), "letter_height_px": 40.0},
                 "inscription_2": {"detected": "TALLER 2026", "confirmed": "TALLER 2026", "use_font": False}}
        store = SimpleNamespace(get=lambda kind, key: {"private": {"inscriptions": saved}})
        runner = SimpleNamespace(store=store, config=SimpleNamespace(inkstitch_executable=ENGINE))
        previous = SimpleNamespace(asset_id="asset_1")
        svg, issues = JobRunner._lettering(runner, self.svg, self.result, previous)
        self.assertNotEqual(svg, self.svg)
        (issue,) = issues
        self.assertEqual(issue.code, "LEGIBILITY_RISK")
        self.assertIn(lettering.FONT_ID, issue.description)
        self.assertIn("hilo 60", issue.description)
        saved["inscription_1"]["arc"] = "bottom"  # sin letras en ese arco: queda el trazo copiado y se avisa por qué
        svg, issues = JobRunner._lettering(runner, self.svg, self.result, previous)
        self.assertEqual(svg, self.svg)
        self.assertIn("no se bordaron con letras", issues[0].description)
        saved["inscription_1"]["use_font"] = False
        self.assertEqual(JobRunner._lettering(runner, self.svg, self.result, previous), (self.svg, ()))


if __name__ == "__main__":
    unittest.main()
