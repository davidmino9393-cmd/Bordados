"""Ajuste de un SVG preparado al destino de una variante: solo cambia la hoja, nunca el dibujo ni los parámetros."""
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))

from embroidery_api.svg_fit import fit_to_target

SVG = "{http://www.w3.org/2000/svg}"
BODY = (
    '<metadata><inkstitch:inkstitch_svg_version>3</inkstitch:inkstitch_svg_version></metadata>'
    '<path id="square" stroke-width="2" d="M0 0 L20 0 L20 20 L0 20 Z" inkstitch:row_spacing_mm="0.45"/>'
)


def document(root='width="20mm" height="20mm" viewBox="0 0 20 20"', prefix=""):
    return (f'{prefix}<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="http://inkstitch.org/namespace" '
            f'{root}>{BODY}</svg>').encode()


def sheet(data):
    root = ET.fromstring(data)
    return root.get("width"), root.get("height"), root.get("viewBox")


class FitToTargetTests(unittest.TestCase):
    def test_a_larger_target_scales_the_sheet_and_keeps_the_viewbox_and_the_drawing(self):
        data = document()
        fitted, factor = fit_to_target(data, 40.0, 40.0)
        self.assertEqual((factor, sheet(fitted)), (2.0, ("40mm", "40mm", "0 0 20 20")))
        self.assertEqual(fitted.replace(b'width="40mm" height="40mm"', b'width="20mm" height="20mm"'), data)  # nada más cambió

    def test_a_smaller_target_scales_down(self):
        fitted, factor = fit_to_target(document(), 10.0, 10.0)
        self.assertEqual((factor, sheet(fitted)[:2]), (0.5, ("10mm", "10mm")))

    def test_the_aspect_ratio_is_kept_and_the_tighter_side_decides(self):
        _, factor = fit_to_target(document(), 40.0, 30.0)
        self.assertEqual(factor, 1.5)  # contain: 20 x 20 entra en 30 x 30
        fitted, _ = fit_to_target(document('width="40mm" height="20mm" viewBox="0 0 40 20"'), 20.0, 20.0)
        self.assertEqual(sheet(fitted)[:2], ("20mm", "10mm"))

    def test_other_units_are_measured_in_millimetres_and_keep_their_unit(self):
        fitted, factor = fit_to_target(document('width="2cm" height="2cm" viewBox="0 0 20 20"'), 40.0, 40.0)
        self.assertEqual((factor, sheet(fitted)[:2]), (2.0, ("4cm", "4cm")))
        fitted, factor = fit_to_target(document('width="1in" height="1in" viewBox="0 0 96 96"'), 50.8, 50.8)
        self.assertEqual((factor, sheet(fitted)[:2]), (2.0, ("2in", "2in")))
        fitted, factor = fit_to_target(document('width="100" height="100" viewBox="0 0 100 100"'), 25.4, 25.4)  # sin unidad = px
        self.assertAlmostEqual(factor, 25.4 / (100 * 25.4 / 96))
        self.assertEqual(len(sheet(fitted)[0]), len("96"))

    def test_a_comment_or_declaration_before_the_root_and_single_quotes_are_respected(self):
        data = document("width='20mm' height='20mm' viewBox='0 0 20 20'", prefix='<?xml version="1.0"?><!-- <svg width="1"> -->')
        fitted, _ = fit_to_target(data, 40.0, 40.0)
        self.assertEqual(sheet(fitted)[:2], ("40mm", "40mm"))
        self.assertTrue(fitted.startswith(b'<?xml version="1.0"?><!-- <svg width="1"> -->'))

    def test_a_stroke_width_on_the_root_is_not_taken_for_the_sheet_width(self):
        data = (b'<svg xmlns="http://www.w3.org/2000/svg" stroke-width="3" width="20mm" height="20mm" viewBox="0 0 20 20"/>')
        fitted, _ = fit_to_target(data, 40.0, 40.0)
        self.assertEqual(fitted, data.replace(b'"20mm"', b'"40mm"'))

    def test_it_refuses_a_svg_whose_size_cannot_change_and_says_why(self):
        for root, reason in (
            ('width="20mm" height="20mm"', "viewBox"),
            ('width="20mm" height="20mm" viewBox=" "', "viewBox"),
            ('width="100%" height="100%" viewBox="0 0 20 20"', "width"),
            ('width="20mm" viewBox="0 0 20 20"', "height"),
            ('width="0mm" height="20mm" viewBox="0 0 20 20"', "positivo"),
            ('width="auto" height="20mm" viewBox="0 0 20 20"', "width"),
        ):
            with self.subTest(root=root), self.assertRaises(ValueError) as caught:
                fit_to_target(document(root), 40.0, 40.0)
            self.assertIn(reason, str(caught.exception))

    def test_it_refuses_what_is_not_a_plain_svg(self):
        for data in (b"<html/>", b"no es xml", b'<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                fit_to_target(data, 40.0, 40.0)


if __name__ == "__main__":
    unittest.main()
