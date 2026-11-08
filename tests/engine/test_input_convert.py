"""Lo que sube la persona se lleva a algo que el motor sabe usar: formatos, seguridad y recorte, con archivos reales.

Las conversiones con Inkscape usan el del servidor (`EMBROIDERY_INKSCAPE_EXE` o `inkscape_executable` de la configuración
privada) y se omiten si no hay uno.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_api import input_convert as convert  # noqa: E402
from embroidery_api.input_convert import (  # noqa: E402
    BMP, EPS, GIF, HEIC, JPEG, PDF, PNG, SVG, TIFF, WEBP, ConversionRefused, normalize_upload, sniff,
)

CONFIG = ROOT / "services" / "api" / ".runtime" / "api-config.json"
ACCEPTED_ALL = frozenset({PNG, JPEG, SVG, WEBP, GIF, BMP, TIFF, PDF})
ACCEPTED_TODAY = frozenset({PNG, JPEG, SVG})


def inkscape_path():
    found = os.environ.get("EMBROIDERY_INKSCAPE_EXE")
    if not found and CONFIG.exists():
        found = json.loads(CONFIG.read_text(encoding="utf-8")).get("inkscape_executable")
    return Path(found) if found and Path(found).exists() else None


INKSCAPE = inkscape_path()
needs_inkscape = unittest.skipUnless(INKSCAPE, "No hay Inkscape (EMBROIDERY_INKSCAPE_EXE o inkscape_executable)")

PLAIN_SVG = (  # una hoja de 400 x 300 con el dibujo (200 x 100) en el medio: el recorte tiene que dejar solo el dibujo
    b'<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">'
    b'<rect x="100" y="100" width="200" height="100" fill="#cc2222"/><circle cx="200" cy="150" r="30" fill="#2244cc"/></svg>'
)
PREPARED_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkstitch="http://inkstitch.org/namespace" width="10mm" height="10mm">'
    b'<metadata><inkstitch:inkstitch_svg_version>3</inkstitch:inkstitch_svg_version></metadata><path id="a" d="M0 0L1 1"/></svg>'
)
ILLUSTRATOR_SVG = (  # como lo exporta Illustrator: DTD con los espacios de nombres declarados como entidades
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [\n'
    b'\t<!ENTITY ns_svg "http://www.w3.org/2000/svg">\n\t<!ENTITY ns_xlink "http://www.w3.org/1999/xlink">\n]>\n'
    b'<svg xmlns="&ns_svg;" xmlns:xlink="&ns_xlink;" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="#118833"/></svg>'
)


def refused(case, data, *, accepted=ACCEPTED_ALL, inkscape=INKSCAPE, name="x"):
    with case.assertRaises(ConversionRefused) as caught:
        normalize_upload(data, "", name, accepted=accepted, inkscape=inkscape)
    return caught.exception


def encoded(image, **save):
    output = BytesIO()
    image.save(output, **save)
    return output.getvalue()


def asymmetric(mode="RGBA", size=(40, 30)):
    image = Image.new(mode, size, (255, 255, 255, 0) if mode == "RGBA" else (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((2, 2, 15, 8), fill=(200, 30, 30, 255) if mode == "RGBA" else (200, 30, 30))
    draw.ellipse((22, 12, 36, 26), fill=(20, 60, 200, 255) if mode == "RGBA" else (20, 60, 200))
    return image


def decoded(png):
    with Image.open(BytesIO(png)) as image:
        return image.convert("RGBA")


class SniffTests(unittest.TestCase):
    def test_the_real_type_comes_from_the_content_not_from_what_the_browser_says(self):
        samples = {
            PNG: encoded(asymmetric(), format="PNG"), JPEG: encoded(asymmetric("RGB"), format="JPEG"),
            WEBP: encoded(asymmetric(), format="WEBP"), GIF: encoded(asymmetric("RGB"), format="GIF"),
            BMP: encoded(asymmetric("RGB"), format="BMP"), TIFF: encoded(asymmetric(), format="TIFF"),
            PDF: b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj", EPS: b"%!PS-Adobe-3.0 EPSF-3.0\n", HEIC: b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00",
            SVG: b'\xef\xbb\xbf  <?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>',
        }
        for expected, data in samples.items():
            with self.subTest(expected):
                self.assertEqual(sniff(data), expected)
        for data in (b"", b"texto cualquiera", b"MZ\x90\x00", b"<html><body>no soy un svg</body></html>"):
            with self.subTest(data=data[:12]):
                self.assertIsNone(sniff(data))


class PillowConversionTests(unittest.TestCase):
    def test_webp_gif_bmp_and_tiff_become_a_png_with_the_same_pixels(self):
        cases = {
            WEBP: encoded(asymmetric(), format="WEBP", lossless=True), GIF: encoded(asymmetric("RGB"), format="GIF"),
            BMP: encoded(asymmetric("RGB"), format="BMP"), TIFF: encoded(asymmetric(), format="TIFF"),
        }
        for kind, data in cases.items():
            with self.subTest(kind):
                result = normalize_upload(data, kind, "dibujo.xyz", accepted=ACCEPTED_ALL)
                self.assertEqual((result.media_type, result.filename), (PNG, "dibujo.png"))
                self.assertEqual(result.original["data"], data)  # lo que subió la persona se conserva tal cual
                self.assertEqual((result.original["media_type"], result.conversion["from"], result.conversion["tool"]), (kind, kind, "pillow"))
                reference = decoded(data)  # lectura independiente del archivo subido
                self.assertEqual(decoded(result.data).tobytes(), reference.tobytes())
                self.assertEqual(result.conversion["size_px"], [40, 30])

    def test_an_animated_gif_uses_its_first_frame_and_says_so(self):
        frames = [asymmetric("RGB"), Image.new("RGB", (40, 30), (0, 0, 0)), Image.new("RGB", (40, 30), (9, 9, 9))]
        data = encoded(frames[0], format="GIF", save_all=True, append_images=frames[1:])
        result = normalize_upload(data, GIF, "pegatina.gif", accepted=ACCEPTED_ALL)
        self.assertEqual((result.conversion["frames_in_file"], result.conversion["frame_used"]), (3, 1))
        self.assertEqual(decoded(result.data).tobytes(), decoded(encoded(frames[0], format="GIF")).tobytes())

    def test_the_exif_orientation_of_a_webp_is_applied_while_converting(self):
        exif = Image.Exif()
        exif[274] = 6  # hay que girar 90° a la derecha para verla derecha
        data = encoded(asymmetric(), format="WEBP", lossless=True, exif=exif.tobytes())
        result = normalize_upload(data, WEBP, "foto.webp", accepted=ACCEPTED_ALL)
        upright = decoded(data).transpose(Image.Transpose.ROTATE_270)  # referencia independiente
        self.assertEqual(decoded(result.data).size, (30, 40))
        self.assertEqual(decoded(result.data).tobytes(), upright.tobytes())

    def test_it_refuses_what_the_catalog_does_not_admit_and_what_cannot_be_read(self):
        webp = encoded(asymmetric(), format="WEBP", lossless=True)
        problem = refused(self, webp, accepted=ACCEPTED_TODAY)
        self.assertEqual(problem.code, "UNSUPPORTED_MEDIA_TYPE")
        self.assertIn("WebP", problem.detail)
        broken = refused(self, webp[:40])
        self.assertEqual(broken.code, "INVALID_REQUEST")
        with patch.object(convert, "MAX_INPUT_PIXELS", 100):
            big = refused(self, encoded(asymmetric(), format="WEBP", lossless=True))
        self.assertEqual(big.code, "PAYLOAD_TOO_LARGE")

    def test_png_and_jpeg_pass_through_untouched_and_unknown_content_is_refused(self):
        png = encoded(asymmetric(), format="PNG")
        result = normalize_upload(png, "image/png", "logo.png", accepted=ACCEPTED_TODAY)
        self.assertEqual((result.data, result.media_type, result.original, result.conversion), (png, PNG, None, None))
        self.assertEqual(refused(self, b"esto no es una imagen").code, "UNSUPPORTED_MEDIA_TYPE")

    def test_eps_and_heic_say_what_to_do_instead(self):
        self.assertIn("PDF", refused(self, b"%!PS-Adobe-3.0 EPSF-3.0\n").detail)
        self.assertIn("JPEG", refused(self, b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00").detail)


class SvgTests(unittest.TestCase):
    def test_a_prepared_svg_goes_straight_to_the_engine_untouched(self):
        result = normalize_upload(PREPARED_SVG, SVG, "listo.svg", accepted=ACCEPTED_TODAY)
        self.assertEqual((result.data, result.media_type, result.original), (PREPARED_SVG, SVG, None))

    def test_unsafe_svgs_are_refused_before_inkscape_ever_sees_them(self):
        def svg(body):
            return b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10">' + body + b"</svg>"

        unsafe = {
            "archivo local": svg(b'<image href="file:///C:/Windows/win.ini" width="10" height="10"/>'),
            "archivo local (xlink)": svg(b'<image xlink:href="C:\\Windows\\win.ini" width="10" height="10"/>'),
            "red": svg(b'<image xlink:href="http://example.com/a.png" width="10" height="10"/>'),
            "estilo con url": svg(b'<rect width="5" height="5" style="fill:url(http://example.com/x)"/>'),
            "@import": svg(b"<style>@import url(http://example.com/a.css);</style><rect width='5' height='5'/>"),
            "script": svg(b"<script>alert(1)</script>"),
            "foreignObject": svg(b"<foreignObject><p>hola</p></foreignObject>"),
            "entidad externa": b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///C:/Windows/win.ini">]><svg xmlns="http://www.w3.org/2000/svg">&x;</svg>',
            "entidades anidadas": b'<!DOCTYPE svg [<!ENTITY a "&b;"><!ENTITY b "hola">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
            "entidad de parámetro": b'<!DOCTYPE svg [<!ENTITY % p "x">%p;]><svg xmlns="http://www.w3.org/2000/svg"/>',
            "entidad fuera del DTD": b'<?xml version="1.0"?><!ENTITY x "y"><svg xmlns="http://www.w3.org/2000/svg"/>',
            "no es XML": b"<svg <<< roto",
            "raíz que no es svg": b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><svg xmlns="http://www.w3.org/2000/svg"/></html>',
        }
        for label, data in unsafe.items():
            with self.subTest(label):
                with patch.object(convert.subprocess, "run", side_effect=AssertionError("Inkscape no debe llamarse")):
                    problem = refused(self, data, inkscape=Path(sys.executable))
                self.assertEqual(problem.code, "INVALID_REQUEST")

    def test_a_plain_svg_needs_inkscape_and_says_so_when_there_is_none(self):
        problem = refused(self, PLAIN_SVG, inkscape=None)
        self.assertIn("Inkscape", problem.detail)

    @needs_inkscape
    def test_a_plain_svg_is_drawn_to_a_png_cropped_to_the_artwork(self):
        result = normalize_upload(PLAIN_SVG, SVG, "Logo Club.svg", accepted=ACCEPTED_TODAY, inkscape=INKSCAPE)
        self.assertEqual((result.media_type, result.filename, result.original["data"], result.conversion["tool"]), (PNG, "Logo Club.png", PLAIN_SVG, "inkscape"))
        image = decoded(result.data)
        self.assertEqual(image.size[0], 2000)  # el dibujo, no la hoja: 200 x 100 se dibuja a 2000 x 1000
        self.assertAlmostEqual(image.size[1] / image.size[0], 0.5, delta=0.01)
        self.assertEqual(image.getchannel("A").getbbox(), (0, 0, *image.size))  # sin márgenes transparentes
        red, blue = image.getpixel((100, 100)), image.getpixel((1000, 500))
        self.assertGreater(red[0], 150)
        self.assertGreater(blue[2], 150)

    @needs_inkscape
    def test_a_very_tall_drawing_is_drawn_with_its_long_side_at_the_limit(self):
        tall = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 1000"><rect width="100" height="1000" fill="#000"/></svg>'
        image = decoded(normalize_upload(tall, SVG, "alto.svg", accepted=ACCEPTED_TODAY, inkscape=INKSCAPE).data)
        self.assertEqual(image.size, (200, 2000))

    @needs_inkscape
    def test_an_illustrator_svg_with_entities_in_its_dtd_is_converted(self):
        result = normalize_upload(ILLUSTRATOR_SVG, SVG, "ai.svg", accepted=ACCEPTED_TODAY, inkscape=INKSCAPE)
        self.assertEqual(result.original["data"], ILLUSTRATOR_SVG)  # el original no se toca
        self.assertGreater(decoded(result.data).getpixel((1000, 1000))[1], 100)

    @needs_inkscape
    def test_an_embedded_image_is_allowed_and_an_empty_drawing_is_refused(self):
        import base64
        embedded = base64.b64encode(encoded(asymmetric(), format="PNG"))
        svg = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 40 30">'
               b'<image width="40" height="30" xlink:href="data:image/png;base64,' + embedded + b'"/></svg>')
        self.assertEqual(normalize_upload(svg, SVG, "e.svg", accepted=ACCEPTED_TODAY, inkscape=INKSCAPE).media_type, PNG)
        problem = refused(self, b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5" fill-opacity="0"/></svg>')
        self.assertEqual(problem.code, "INVALID_REQUEST")


@needs_inkscape
class PdfTests(unittest.TestCase):
    def test_a_pdf_and_an_ai_file_become_a_png_of_the_first_page(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "logo.svg", Path(directory) / "logo.pdf"
            source.write_bytes(PLAIN_SVG)
            subprocess.run([str(INKSCAPE), str(source), "--export-type=pdf", f"--export-filename={target}"], check=True, capture_output=True, timeout=120)
            pdf = target.read_bytes()
        for name in ("logo.pdf", "logo.ai"):  # un AI moderno es un PDF con otro nombre
            with self.subTest(name):
                result = normalize_upload(pdf, "application/pdf" if name.endswith("pdf") else "", name, accepted=ACCEPTED_ALL, inkscape=INKSCAPE)
                self.assertEqual((result.media_type, result.filename, result.conversion["from"]), (PNG, "logo.png", PDF))
                image = decoded(result.data)
                self.assertEqual(image.size[0], 2000)
                self.assertAlmostEqual(image.size[1] / image.size[0], 0.5, delta=0.02)

    def test_a_pdf_that_is_not_admitted_or_is_corrupt_is_refused(self):
        self.assertEqual(refused(self, b"%PDF-1.7\nbasura", accepted=ACCEPTED_TODAY).code, "UNSUPPORTED_MEDIA_TYPE")
        self.assertEqual(refused(self, b"%PDF-1.7\nbasura").code, "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
