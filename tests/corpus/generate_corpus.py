"""Genera el corpus de prueba: el mismo diseño en varios formatos y varios tipos de diseño, con lo que se espera de cada uno.

Uso:  python tests/corpus/generate_corpus.py --out RUTA_DEL_CORPUS
Escribe los archivos y `manifest.json` (archivo, categoría, formato y resultado esperado). No hay binarios en el repositorio:
todo sale de este script. Los PDF se dibujan con Inkscape (`EMBROIDERY_INKSCAPE_EXE` o la configuración privada de la API).
"""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "services" / "api" / ".runtime" / "api-config.json"
NAVY, ORANGE, GREEN = (24, 48, 120, 255), (235, 120, 30, 255), (30, 140, 70, 255)
SIZE = (800, 600)

# Lo que se espera hoy (catálogo = PNG, JPEG y SVG). `ok`: termina en un JEF. `rechazo:CODIGO`: la API lo rechaza con ese código.
# `falla:CODIGO`: el trabajo falla por una limitación conocida y documentada. `libre`: se mide y se informa, sin juicio previo.
OK, LIBRE = "ok", "libre"


def logo(background=(255, 255, 255, 255)):
    image = Image.new("RGBA", SIZE, background)
    draw = ImageDraw.Draw(image)
    draw.ellipse((100, 60, 700, 540), fill=NAVY)
    draw.ellipse((220, 170, 580, 430), fill=ORANGE)
    draw.rectangle((330, 250, 470, 350), fill=background if background[3] else (255, 255, 255, 0))
    return image


def text_image():
    image = Image.new("RGBA", SIZE, (255, 255, 255, 255))
    try:
        font = ImageFont.load_default(size=190)
    except TypeError:  # Pillow viejo: sin tamaño
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((40, 190), "CLUB", fill=NAVY, font=font)
    return image


def line_art():
    image = Image.new("RGBA", SIZE, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for radius in (260, 200, 140, 80):
        draw.ellipse((400 - radius, 300 - radius, 400 + radius, 300 + radius), outline=NAVY, width=9)
    draw.line((120, 300, 680, 300), fill=GREEN, width=9)
    return image


def gradient():
    ramp = Image.linear_gradient("L").rotate(90).resize(SIZE)
    image = Image.merge("RGB", (ramp, ramp.point(lambda v: 255 - v), Image.new("L", SIZE, 128))).convert("RGBA")
    ImageDraw.Draw(image).ellipse((250, 150, 550, 450), fill=(255, 255, 255, 255))
    return image


def photo_like():
    base = Image.linear_gradient("L").resize(SIZE).convert("RGB")
    noise = Image.effect_noise(SIZE, 30).convert("RGB")
    return ImageChops.add(base, noise, scale=2).convert("RGBA")


def encode(image, **save):
    output = BytesIO()
    image.save(output, **save)
    return output.getvalue()


def svg_of(width=800, height=600):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            '<ellipse cx="400" cy="300" rx="300" ry="240" fill="#183078"/><ellipse cx="400" cy="300" rx="180" ry="130" fill="#eb781e"/>'
            '<rect x="330" y="250" width="140" height="100" fill="#ffffff"/></svg>').encode()


def inkscape_path():
    found = os.environ.get("EMBROIDERY_INKSCAPE_EXE") or (json.loads(CONFIG.read_text(encoding="utf-8")).get("inkscape_executable") if CONFIG.exists() else None)
    return Path(found) if found and Path(found).exists() else None


def pdf_of(svg, directory):
    inkscape = inkscape_path()
    if inkscape is None:
        return None
    source, target = Path(directory) / "_logo.svg", Path(directory) / "_logo.pdf"
    source.write_bytes(svg)
    subprocess.run([str(inkscape), str(source), "--export-type=pdf", f"--export-filename={target}"], check=True, capture_output=True, timeout=120)
    data = target.read_bytes()
    source.unlink()
    target.unlink()
    return data


def build(out):
    out.mkdir(parents=True, exist_ok=True)
    flat, clear = logo(), logo((0, 0, 0, 0))
    entries = []

    def add(name, category, fmt, data, expect, note=""):
        (out / name).write_bytes(data)
        entries.append({"file": name, "category": category, "format": fmt, "expect": expect, "note": note})

    for fmt, save, ext in (("png", {"format": "PNG"}, "png"), ("jpeg", {"format": "JPEG", "quality": 92}, "jpg"),
                           ("webp", {"format": "WEBP", "lossless": True}, "webp"), ("gif", {"format": "GIF"}, "gif"),
                           ("bmp", {"format": "BMP"}, "bmp"), ("tiff", {"format": "TIFF"}, "tiff")):
        image = flat.convert("RGB") if fmt in ("jpeg", "bmp", "gif") else flat
        add(f"logo_plano.{ext}", "logo de colores planos", fmt, encode(image, **save), OK if fmt in ("png", "jpeg") else "rechazo:UNSUPPORTED_MEDIA_TYPE",
            "" if fmt in ("png", "jpeg") else "el catálogo todavía no admite este formato")
    add("logo_plano.svg", "logo de colores planos", "svg (común)", svg_of(), OK, "SVG sin parámetros de Ink/Stitch: se dibuja a imagen")
    pdf = pdf_of(svg_of(), out)
    if pdf:
        add("logo_plano.pdf", "logo de colores planos", "pdf", pdf, "rechazo:UNSUPPORTED_MEDIA_TYPE", "el catálogo todavía no admite este formato")
    add("logo_transparente.png", "logo con fondo transparente", "png", encode(clear, format="PNG"), OK)
    add("logo_transparente.webp", "logo con fondo transparente", "webp", encode(clear, format="WEBP", lossless=True), "rechazo:UNSUPPORTED_MEDIA_TYPE",
        "el catálogo todavía no admite este formato")
    add("texto.png", "texto", "png", encode(text_image(), format="PNG"), OK)
    add("dibujo_de_linea.png", "dibujo de línea fina", "png", encode(line_art(), format="PNG"), OK)
    add("degradado.png", "degradado", "png", encode(gradient(), format="PNG"), LIBRE, "un degradado no se borda bien: se mide qué hace")
    add("foto_simulada.jpg", "foto", "jpeg", encode(photo_like().convert("RGB"), format="JPEG", quality=85), LIBRE, "una foto no es un diseño de bordado: se mide qué hace")
    add("baja_resolucion.png", "baja resolución (64 px)", "png", encode(flat.resize((64, 48), Image.Resampling.NEAREST), format="PNG"), LIBRE)
    huge = Image.new("RGBA", (5000, 4000), (255, 255, 255, 255))
    ImageDraw.Draw(huge).ellipse((600, 400, 4400, 3600), fill=NAVY)
    add("alta_resolucion_20mp.png", "alta resolución (20 megapíxeles)", "png", encode(huge, format="PNG"), LIBRE, "en el límite de 20 MP")
    upright = flat.convert("RGB").transpose(Image.Transpose.ROTATE_90)  # píxeles guardados de costado + EXIF 6: se ve horizontal
    exif = Image.Exif()
    exif[274] = 6
    add("foto_girada_exif6.jpg", "foto con orientación EXIF 6", "jpeg", encode(upright, format="JPEG", quality=92, exif=exif.tobytes()),
        OK, "medido el 2026-11-08: la orientación EXIF ya se aplica de punta a punta")
    add("no_es_una_imagen.png", "archivo roto", "png", b"esto no es un PNG", "rechazo:UNSUPPORTED_MEDIA_TYPE")
    add("png_cortado.png", "archivo roto", "png", encode(flat, format="PNG")[:300], "rechazo:INVALID_REQUEST")
    (out / "manifest.json").write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    made = build(arguments.out)
    print(f"{len(made)} archivos en {arguments.out}", file=sys.stderr)
