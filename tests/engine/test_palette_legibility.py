"""Orden 3: paleta honesta (3.1) y aviso de legibilidad antes de generar (3.2/3.4). Sin red ni worker real."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from PIL import Image, ImageDraw

from embroidery_api import legibility
from embroidery_api.palette import clean_palette
from embroidery_api.runner import JobRunner
from embroidery_contracts import JobSettings, SourceAsset
import json
from vectorize import vectorize

RED, BLUE = (236, 4, 2), (20, 60, 200)
SETTINGS = json.loads((ROOT / "packages" / "contracts" / "fixtures" / "generation-from-svg.json").read_text(encoding="utf-8"))["payload"]["settings"]


def antialiased(draw_shapes, size=(400, 300), factor=4):
    """Dibuja a 4x y reduce con LANCZOS: deja el borde suavizado (mezclas tinta->blanco) de un logo real."""
    big = Image.new("RGB", (size[0] * factor, size[1] * factor), "white")
    draw_shapes(ImageDraw.Draw(big), factor)
    return big.resize(size, Image.Resampling.LANCZOS)


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def one_ink_logo():
    def shapes(draw, k):
        draw.ellipse((40 * k, 30 * k, 360 * k, 270 * k), outline=RED, width=14 * k)
        draw.rectangle((150 * k, 100 * k, 250 * k, 200 * k), fill=RED)
    return png(antialiased(shapes))


def two_ink_logo():
    def shapes(draw, k):
        draw.ellipse((40 * k, 30 * k, 360 * k, 270 * k), outline=RED, width=14 * k)
        draw.rectangle((150 * k, 100 * k, 250 * k, 200 * k), fill=BLUE)
    return png(antialiased(shapes))


def thin_text_logo(line=2):
    def shapes(draw, k):
        for row in range(8):
            draw.line((20 * k, (30 + row * 30) * k, 380 * k, (30 + row * 30) * k), fill=RED, width=line * k)
    return png(antialiased(shapes))


def asset_for(data, size):
    return SourceAsset(asset_id="asset_x", project_id="p", sha256=hashlib.sha256(data).hexdigest(), media_type="image/png",
                       original_filename="l.png", original_width_px=size[0], original_height_px=size[1])


def settings(limit, width=100.0, height=75.0):
    values = dict(SETTINGS, color_limit=limit, target={"width_mm": width, "height_mm": height, "fit": "contain"})
    return JobSettings.model_validate(values)


def engine_colours(data, limit):
    """Colores que el motor deja con la imagen tal cual (sin limpiar): el comportamiento anterior."""
    result = vectorize(data, "image/png", asset_for(data, (400, 300)), None, settings(limit), job_id="job_x", revision_id="rev_x")
    return result.evidence["segmentation"]["output_colours"], sum(m["subpaths"] for m in result.evidence["masks"])


class PaletteTests(unittest.TestCase):
    def test_antialias_halos_cost_threads_before_and_not_after(self):
        data = one_ink_logo()
        before_colours, before_rings = engine_colours(data, 3)
        self.assertGreaterEqual(len(before_colours), 2, before_colours)  # los halos compiten con la tinta por los 3 lugares
        self.assertGreater(before_rings, 100)
        cleaning = clean_palette(data, "image/png", 3)
        self.assertTrue(cleaning.applied)
        self.assertEqual(len(cleaning.inks), 1)
        after_colours, after_rings = engine_colours(cleaning.png, 1)
        self.assertEqual(len(after_colours), 1)
        self.assertLess(after_rings, before_rings / 10)
        self.assertLess(after_rings, 10)  # el anillo exterior e interior, el rectángulo: sin motas

    def test_the_report_declares_rule_threshold_and_counts_and_says_it_is_noise_cleanup(self):
        data = one_ink_logo()
        report = clean_palette(data, "image/png", 3).report
        self.assertTrue(report["is_noise_cleanup_not_geometry_removal"])
        self.assertIn("mezcla tinta->blanco", report["rule"])
        self.assertEqual(report["thresholds"]["blend_tolerance_rgb"], 30.0)
        self.assertGreater(report["distinct_foreground_colours_before"], 50)
        self.assertEqual(report["ink_count_after"], 1)
        self.assertEqual(report["colours_merged_into_inks"], report["distinct_foreground_colours_before"] - 1)
        self.assertGreater(report["colours_merged_by_rule"]["blend"], 0)
        self.assertEqual(report["source_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(report["foreground_pixels_before"] - report["foreground_pixels_returned_to_background"],
                         report["foreground_pixels_after"])
        self.assertEqual(sum(report["pixels_per_ink"].values()), report["foreground_pixels_after"])

    def test_only_the_fringe_goes_back_to_the_background_the_body_of_every_stroke_stays(self):
        data = one_ink_logo()
        cleaning = clean_palette(data, "image/png", 3)
        report = cleaning.report
        lost = report["foreground_pixels_returned_to_background"] / report["foreground_pixels_before"]
        self.assertLess(lost, 0.15)  # solo el borde suavizado: una fracción chica de la figura
        cleaned = Image.open(io.BytesIO(cleaning.png)).convert("RGB")
        self.assertEqual({c for _n, c in cleaned.getcolors()}, {(255, 255, 255), tuple(int(cleaning.inks[0][i:i + 2], 16) for i in (1, 3, 5))})
        self.assertEqual(cleaned.getpixel((200, 150)), tuple(int(cleaning.inks[0][i:i + 2], 16) for i in (1, 3, 5)))  # el cuerpo del cuadrado

    def test_a_second_real_ink_is_kept_and_the_limit_is_still_of_threads(self):
        data = two_ink_logo()
        cleaning = clean_palette(data, "image/png", 3)
        self.assertEqual(len(cleaning.inks), 2, cleaning.inks)
        limited = clean_palette(data, "image/png", 1)
        self.assertEqual(len(limited.inks), 1)
        self.assertEqual(limited.report["inks_merged"][0]["reason"], "colour_limit")

    def test_the_limit_is_not_inflated_and_the_original_asset_is_not_touched(self):
        data = one_ink_logo()
        asset = asset_for(data, (400, 300))
        previous = SimpleNamespace(settings_snapshot=settings(3), job_id="job_x", revision_id="rev_x")
        result, stitching = JobRunner._vectorize_for_stitching(None, data, asset, None, previous, None)
        self.assertEqual(stitching["colour_limit_requested"], 3)
        self.assertEqual(stitching["colour_limit_used"], 1)  # hilos reales, no capas de halo
        self.assertLessEqual(stitching["colour_limit_used"], stitching["colour_limit_requested"])
        self.assertEqual(stitching["engine_quantizer_slots"], 1)
        self.assertEqual(stitching["near_white_layers_omitted"], 0)
        self.assertEqual(len(result.evidence["segmentation"]["output_colours"]), 1)
        cleaning = stitching["palette_cleaning"]
        self.assertTrue(cleaning["applied"])
        self.assertEqual(asset.sha256, hashlib.sha256(data).hexdigest())  # el asset del job sigue siendo el original
        self.assertNotEqual(cleaning["cleaned_sha256"], asset.sha256)
        self.assertEqual(result.evidence["input_sha256"], cleaning["cleaned_sha256"])  # lo que vio el motor queda declarado

    def test_a_transparent_image_is_left_alone_with_the_reason(self):
        image = Image.new("RGBA", (60, 40), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((10, 10, 50, 30), fill=(200, 0, 0, 255))
        cleaning = clean_palette(png(image), "image/png", 3)
        self.assertFalse(cleaning.applied)
        self.assertIn("transparencia", cleaning.report["reason"])
        self.assertIsNone(cleaning.png)

    def test_a_real_pale_layer_is_not_merged_into_a_dark_ink_and_does_not_count_as_a_thread(self):
        image = Image.new("RGB", (120, 60), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((5, 5, 55, 55), fill=RED)
        draw.rectangle((65, 5, 115, 55), fill=(243, 241, 240))
        cleaning = clean_palette(png(image), "image/png", 1)
        self.assertEqual(cleaning.report["thread_inks_after"], 1)
        self.assertEqual(cleaning.report["near_white_layers_kept_for_the_engine_to_omit"], ["#f3f1f0"])


class LegibilityTests(unittest.TestCase):
    def test_thin_strokes_warn_with_numbers_and_say_when_the_minimum_size_does_not_fit_the_hoop(self):
        data = thin_text_logo(line=2)
        result = legibility.check(data, "image/png", 100, 75, 3, hoop_mm=(100, 75))  # bastidor del tamaño pedido
        self.assertTrue(result.warn)
        self.assertGreater(result.thin_share_below_0_6_mm, 0.30)
        self.assertRegex(result.message, r"^El \d+% del trazo mide menos de 0,6 mm; a \d+ mm las letras no van a quedar legibles\.")
        self.assertFalse(result.minimum_size.already_legible)
        self.assertFalse(result.minimum_size.fits_in_hoop)
        self.assertIn("no entra en el bastidor (100 x 75 mm)", result.message)
        self.assertIn("no hay un tamaño útil", result.message)

    def test_a_fitting_minimum_size_is_offered_as_a_number(self):
        data = thin_text_logo(line=2)
        result = legibility.check(data, "image/png", 100, 75, 3, hoop_mm=(400, 400))
        self.assertTrue(result.minimum_size.fits_in_hoop)
        self.assertRegex(result.message, r"El tamaño mínimo para que el 80% del trazo supere 0,8 mm es de ~\d+ x \d+ mm\.")

    def test_thick_strokes_do_not_warn_and_the_message_is_absent(self):
        data = one_ink_logo()
        result = legibility.check(data, "image/png", 100, 75, 3, hoop_mm=(140, 140))
        self.assertFalse(result.warn)
        self.assertIsNone(result.message)
        self.assertLess(result.thin_share_below_0_6_mm, 0.30)

    def test_the_share_grows_when_the_same_image_is_made_smaller(self):
        data = one_ink_logo()
        big = legibility.check(data, "image/png", 100, 75, 3)
        small = legibility.check(data, "image/png", 12, 9, 3)  # el anillo de 14 px pasa a medir ~0,4 mm
        self.assertGreater(small.thin_share_below_0_6_mm, big.thin_share_below_0_6_mm + 0.3)
        self.assertTrue(small.warn)

    def test_white_margin_is_offered_as_an_option_with_the_number_and_without_claiming_to_fix_letters(self):
        def shapes(draw, k):  # la tinta ocupa la mitad central: margen blanco de un cuarto por lado
            draw.rectangle((100 * k, 75 * k, 300 * k, 225 * k), fill=RED)
        data = png(antialiased(shapes))
        result = legibility.check(data, "image/png", 100, 75, 3)
        self.assertIsNotNone(result.margin_option)
        self.assertGreater(result.margin_option.gain_percent, 50)
        self.assertGreater(result.margin_option.ink_width_mm_cropped, result.margin_option.ink_width_mm_now)
        self.assertIn("no resuelve el problema de las letras finas", result.margin_option.message)
        self.assertEqual(result.margin_option.ink_bbox_px[0], 100)

    def test_an_image_without_margin_has_no_margin_option(self):
        solid = png(Image.new("RGBA", (100, 75), RED + (255,)))  # la tinta llena toda la imagen: no hay margen que recortar
        self.assertIsNone(legibility.check(solid, "image/png", 100, 75, 3).margin_option)


if __name__ == "__main__":
    unittest.main()
