"""Guía 1.3: detección de inscripciones (texto recto y en curva) para confirmar la frase antes de bordarla con letras de bordado.

Las pruebas del informe no necesitan el lector. Las del lector real (RapidOCR + onnxruntime + OpenCV) se omiten si no está instalado;
usan una imagen sintética, no logos de clientes.
"""
import importlib.util
import io
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from PIL import Image, ImageDraw, ImageFont
from pydantic import ValidationError

from embroidery_api.inscriptions import SMALL_LETTER_MM, ConfirmedInscription, Detected, _key, mm_per_px, report

READER = all(importlib.util.find_spec(name) for name in ("rapidocr", "onnxruntime", "cv2"))
INK = "#1F3A93"


def seal_png(phrase="ESCUELA DE BORDADO", line="TALLER 2026", size=900, transparent=False):
    """Sello: aro doble, frase en curva por arriba (letras hacia afuera) y una línea recta debajo del sello."""
    # Transparente como sale de la mayoría de los programas: negro invisible. Leído sin el canal alfa, el texto negro desaparece.
    image = Image.new("RGBA", (size, size + 260), (0, 0, 0, 0) if transparent else (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    cx, cy, r = size / 2, size / 2, size * 0.42
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK, width=14)
    draw.ellipse((cx - r * 0.66, cy - r * 0.66, cx + r * 0.66, cy + r * 0.66), outline=INK, width=8)
    font, text_r, span = ImageFont.load_default(size=round(r * 0.15)), r * 0.83, math.radians(150)
    start = -math.pi / 2 - span / 2
    for number, char in enumerate(phrase):
        angle = start + span * (number + 0.5) / len(phrase)
        tile = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((60, 60), char, font=font, fill=INK, anchor="mm")
        tile = tile.rotate(-math.degrees(angle + math.pi / 2), resample=Image.Resampling.BICUBIC)
        image.alpha_composite(tile, (round(cx + text_r * math.cos(angle) - 60), round(cy + text_r * math.sin(angle) - 60)))
    draw.text((cx, size + 120), line, font=ImageFont.load_default(size=70), fill="#000000", anchor="mm")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class ReportTests(unittest.TestCase):
    FOUND = [
        Detected("MUNICIPALIDAD DE EL FORTÍN", 0.998, "curved", (240, 349, 660, 660), 50.0),
        Detected("#ConTodos!", 0.97, "straight", (1700, 867, 996, 169), 300.0),
    ]
    SIZE = (2880, 1440)

    def test_letter_heights_are_converted_at_the_requested_size_and_small_ones_are_marked(self):
        body = report(self.FOUND, self.SIZE, 100.0, 100.0)
        scale = mm_per_px(100.0, 100.0, self.SIZE)
        self.assertEqual([i.inscription_id for i in body.inscriptions], ["inscription_1", "inscription_2"])
        self.assertEqual([i.letter_height_mm for i in body.inscriptions], [round(50 * scale, 1), round(300 * scale, 1)])
        self.assertEqual([i.small for i in body.inscriptions], [True, False])
        self.assertEqual(body.small_below_mm, SMALL_LETTER_MM)

    def test_without_a_size_there_are_no_millimetres_and_nothing_is_judged(self):
        body = report(self.FOUND, self.SIZE)
        self.assertEqual({(i.letter_height_mm, i.small) for i in body.inscriptions}, {(None, None)})

    def test_a_confirmation_counts_only_while_the_reading_is_the_one_that_was_confirmed(self):
        saved = {
            "inscription_1": {"detected": "MUNICIPALIDAD DE EL FORTÍN", "confirmed": "Municipalidad de El Fortín"},
            "inscription_2": {"detected": "#ConTodo", "confirmed": "#ConTodos!"},
        }
        body = report(self.FOUND, self.SIZE, 100.0, 100.0, saved)
        self.assertEqual([i.confirmed_text for i in body.inscriptions], ["Municipalidad de El Fortín", None])

    def test_the_grouping_key_ignores_accents_spaces_and_signs(self):
        self.assertEqual(_key("EL FORTÍN - CORDOBA"), _key("ELFORTIN-CORDOBA"))

    def test_a_confirmed_phrase_is_trimmed_and_cannot_be_empty_or_point_elsewhere(self):
        self.assertEqual(ConfirmedInscription(inscription_id="inscription_3", text="  Hola  ").text, "Hola")
        for bad in ({"inscription_id": "inscription_1", "text": "   "}, {"inscription_id": "../asset", "text": "x"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                ConfirmedInscription(**bad)


@unittest.skipUnless(READER, "lector de texto no instalado (rapidocr, onnxruntime, opencv-python-headless)")
class ReaderTests(unittest.TestCase):
    """Con el lector real: los modelos PP-OCRv5 se descargan una vez y quedan en el paquete."""

    def detect(self, data):
        from embroidery_api.inscriptions import detect
        return {(d.text, d.layout): d for d in detect(data)}

    def test_a_curved_seal_phrase_and_a_straight_line_are_both_read(self):
        found = self.detect(seal_png())
        self.assertIn(("ESCUELA DE BORDADO", "curved"), found)
        self.assertIn(("TALLER 2026", "straight"), found)
        self.assertEqual(len(found), 2, sorted(found))  # los pedazos del arco leídos como texto recto no cuentan aparte

    def test_letter_heights_follow_the_ink_not_the_reader_box(self):
        found = self.detect(seal_png())
        # Mayúsculas de la fuente a 57 px y 70 px: ~41 px y ~50 px de alto. La caja del lector es bastante más alta.
        self.assertAlmostEqual(found[("ESCUELA DE BORDADO", "curved")].letter_height_px, 41, delta=6)
        self.assertAlmostEqual(found[("TALLER 2026", "straight")].letter_height_px, 50, delta=6)

    def test_a_transparent_background_is_read_on_white_not_on_black(self):
        found = self.detect(seal_png(transparent=True))
        self.assertIn(("TALLER 2026", "straight"), found)


if __name__ == "__main__":
    unittest.main()
