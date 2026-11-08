"""Lleva lo que sube la persona a algo que el motor sabe usar: PNG, JPEG o un SVG preparado para Ink/Stitch.

El motor digitaliza píxeles (E1) o un SVG que ya trae los parámetros de Ink/Stitch. Todo lo demás se convierte al subir:
- un SVG común (sin esos parámetros, como el que exporta Illustrator) y un PDF o AI se dibujan con Inkscape a un PNG;
- WebP, GIF, BMP y TIFF se pasan a PNG con Pillow (primer cuadro o página, orientación aplicada).
El archivo que se sube se conserva aparte; el asset que se publica es el convertido y su SHA256 es el de ese PNG.
Solo se convierte lo que el catálogo de la API admite (`accepted`), así que ampliar formatos es una decisión de configuración.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import subprocess
import tempfile
from threading import BoundedSemaphore
import warnings
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps, UnidentifiedImageError

from vectorize.image_input import MAX_INPUT_PIXELS

PNG, JPEG, SVG = "image/png", "image/jpeg", "image/svg+xml"
WEBP, GIF, BMP, TIFF = "image/webp", "image/gif", "image/bmp", "image/tiff"
PDF, EPS, HEIC = "application/pdf", "application/postscript", "image/heic"
NAMES = {PNG: "PNG", JPEG: "JPEG", SVG: "SVG", WEBP: "WebP", GIF: "GIF", BMP: "BMP", TIFF: "TIFF", PDF: "PDF o AI", EPS: "EPS", HEIC: "HEIC"}
RASTER_CONVERTED_WITH_PILLOW = {WEBP, GIF, BMP, TIFF}
ORIGINAL_SUFFIX = {SVG: ".svg", PDF: ".pdf", WEBP: ".webp", GIF: ".gif", BMP: ".bmp", TIFF: ".tiff"}

INKSCAPE_TIMEOUT_S = 60
INKSCAPE_LONG_SIDE_PX = 2000  # un logo se dibuja a 2000 px de ancho; más píxeles solo hacen más lento a E1 sin más detalle bordable
INKSCAPE_MAX_PIXELS = 4_000_000
_INKSCAPE_SLOTS = BoundedSemaphore(2)

SVG_NS = "{http://www.w3.org/2000/svg}"
INKSTITCH_VERSION = "{http://inkstitch.org/namespace}inkstitch_svg_version"
ACTIVE_ELEMENTS = {SVG_NS + "script", SVG_NS + "foreignObject"}
SAFE_DATA_URI = re.compile(r"^data:image/(png|jpeg|gif|webp);base64,", re.IGNORECASE)
EXTERNAL_CSS = re.compile(r"@import|url\(\s*['\"]?(?!#|data:image/)", re.IGNORECASE)
HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}
DOCTYPE = re.compile(rb"<!DOCTYPE[^>\[]*(\[.*?\])?\s*>", re.DOTALL | re.IGNORECASE)
ENTITY = re.compile(rb"<!ENTITY\s+([A-Za-z_][\w.-]*)\s+(\"[^\"]*\"|'[^']*')\s*>")
MAX_ENTITY_USES = 1000


class ConversionRefused(Exception):
    """El archivo no se puede usar; `code` es el código de error de la API y `detail` lo que se le dice a la persona."""

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Normalized:
    data: bytes
    media_type: str
    filename: str
    original: dict | None  # lo que subió la persona, cuando hubo conversión: data, media_type, filename
    conversion: dict | None  # cómo se convirtió: de qué, con qué herramienta y qué se tomó


def sniff(data):
    """El tipo real por el contenido: el que declara el navegador a veces falta (.ai, .eps) o no es de fiar."""
    head = data[:4096]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    if head[:2] == b"BM" and int.from_bytes(head[14:18], "little") in (12, 40, 52, 56, 64, 108, 124):
        return BMP
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return TIFF
    if b"%PDF-" in head[:1024]:
        return PDF
    if head.startswith(b"%!PS-Adobe") or head.startswith(b"\xc5\xd0\xd3\xc6"):
        return EPS
    if head[4:8] == b"ftyp" and head[8:12] in HEIC_BRANDS:
        return HEIC
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if text.startswith((b"<?xml", b"<svg", b"<!--", b"<!DOCTYPE")) and b"<svg" in head:
        return SVG
    return None


def normalize_upload(data, declared_type, filename, *, accepted, inkscape=None):
    kind = sniff(data)
    if kind is None:
        raise ConversionRefused("UNSUPPORTED_MEDIA_TYPE", "No se reconoce el tipo de archivo. Se admiten " + _names(accepted) + ".")
    if kind in (PNG, JPEG):
        # Pasan tal cual; si lo declarado no coincide con el contenido lo dice la validación de la imagen.
        return Normalized(data, declared_type if declared_type in (PNG, JPEG) else kind, filename, None, None)
    if kind not in accepted:
        raise ConversionRefused("UNSUPPORTED_MEDIA_TYPE", f"El tipo de archivo no está admitido ({NAMES[kind]}). Se admiten {_names(accepted)}.")
    if kind == EPS:
        raise ConversionRefused("UNSUPPORTED_MEDIA_TYPE", "EPS necesita Ghostscript y el servidor no lo tiene: exportá el diseño como PDF o SVG.")
    if kind == HEIC:
        raise ConversionRefused("UNSUPPORTED_MEDIA_TYPE", "HEIC todavía no está soportado: exportá la foto como JPEG o PNG.")
    source = data
    if kind == SVG:
        source = _without_dtd(data)
        root = _parse_svg(source)
        if any(element.tag == INKSTITCH_VERSION for element in root.iter()):
            return Normalized(data, SVG, filename, None, None)  # ya trae los parámetros de Ink/Stitch: va directo al motor
        _refuse_external_references(root)
    png, evidence = _with_inkscape(source, kind, inkscape) if kind in (SVG, PDF) else _with_pillow(data, kind)
    original = {"data": data, "media_type": kind, "filename": filename}
    return Normalized(png, PNG, f"{Path(filename).stem or 'imagen'}.png", original, {"from": kind, **evidence})


def _names(accepted):
    return ", ".join(NAMES.get(mime, mime) for mime in sorted(accepted, key=lambda m: NAMES.get(m, m)))


def _without_dtd(data):
    """Illustrator declara sus espacios de nombres como entidades en un DTD. Se admiten solo entidades de texto fijo:
    se reemplazan en el documento y se quita el DTD; cualquier otra cosa en él (entidades externas, anidadas) se rechaza."""
    found = DOCTYPE.search(data)
    if found is None:
        if b"<!ENTITY" in data.upper():
            raise ConversionRefused("INVALID_REQUEST", "El SVG declara entidades fuera de un DTD que se admita.")
        return data
    subset = found.group(1) or b""
    if re.search(rb"<!(?!ENTITY\b)", ENTITY.sub(b"", subset), re.IGNORECASE) or b"%" in subset:
        raise ConversionRefused("INVALID_REQUEST", "El SVG usa un DTD que no se admite: guardalo como SVG simple desde Inkscape.")
    body = data[:found.start()] + data[found.end():]
    for name, value in ENTITY.findall(subset):
        if b"&" in value or body.count(b"&" + name + b";") > MAX_ENTITY_USES:
            raise ConversionRefused("INVALID_REQUEST", "El SVG usa entidades anidadas o demasiadas veces: guardalo como SVG simple desde Inkscape.")
        body = body.replace(b"&" + name + b";", value[1:-1])
    return body


def _parse_svg(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        raise ConversionRefused("INVALID_REQUEST", "El SVG no es XML válido.") from None
    if root.tag != SVG_NS + "svg":
        raise ConversionRefused("INVALID_REQUEST", "El archivo no tiene una raíz SVG.")
    if any(element.tag in ACTIVE_ELEMENTS for element in root.iter()):
        raise ConversionRefused("INVALID_REQUEST", "El SVG contiene contenido activo no admitido.")
    return root


def _refuse_external_references(root):
    """Inkscape dibuja lo que el SVG referencia, también archivos del servidor: solo se admiten imágenes incrustadas."""
    for element in root.iter():
        for name, value in element.attrib.items():
            if name.endswith("href") and not (value.startswith("#") or SAFE_DATA_URI.match(value)):
                raise ConversionRefused("INVALID_REQUEST", "El SVG referencia archivos externos: incrustá las imágenes o convertilas a trazos.")
            if EXTERNAL_CSS.search(value):
                raise ConversionRefused("INVALID_REQUEST", "El SVG referencia archivos externos desde sus estilos.")
        if element.tag == SVG_NS + "style" and element.text and EXTERNAL_CSS.search(element.text):
            raise ConversionRefused("INVALID_REQUEST", "El SVG referencia archivos externos desde sus estilos.")


def _with_pillow(data, kind):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_INPUT_PIXELS:
                    raise ConversionRefused("PAYLOAD_TOO_LARGE", "La imagen supera el límite de píxeles configurado.")
                frames = getattr(image, "n_frames", 1)
                image.seek(0)
                oriented = ImageOps.exif_transpose(image)
                rgba = oriented.convert("RGBA")
    except ConversionRefused:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ConversionRefused("INVALID_REQUEST", f"La imagen {NAMES[kind]} no pudo decodificarse.") from None
    output = BytesIO()
    rgba.save(output, format="PNG")
    return output.getvalue(), {"tool": "pillow", "frames_in_file": frames, "frame_used": 1, "size_px": list(rgba.size)}


def _with_inkscape(data, kind, inkscape):
    if inkscape is None or not Path(inkscape).exists():
        raise ConversionRefused("INVALID_REQUEST", f"Este archivo ({NAMES[kind]}) se convierte con Inkscape y el servidor no lo tiene configurado.")
    with _INKSCAPE_SLOTS, tempfile.TemporaryDirectory(prefix="convert-") as directory:
        source, target = Path(directory) / ("entrada" + ORIGINAL_SUFFIX[kind]), Path(directory) / "salida.png"
        source.write_bytes(data)

        def export(*size):
            command = [str(inkscape), str(source), "--export-type=png", f"--export-filename={target}", "--export-area-drawing",
                       "--export-background-opacity=0", *size]
            if kind == PDF:
                command.append("--pages=1")
            target.unlink(missing_ok=True)
            try:
                done = subprocess.run(command, capture_output=True, timeout=INKSCAPE_TIMEOUT_S, cwd=directory)
            except subprocess.TimeoutExpired:
                raise ConversionRefused("INVALID_REQUEST", f"El archivo tardó más de {INKSCAPE_TIMEOUT_S} s en convertirse.") from None
            if done.returncode != 0 or not target.exists():
                raise ConversionRefused("INVALID_REQUEST", f"No se pudo convertir el archivo {NAMES[kind]}: está dañado o usa algo que no se admite.")
            with Image.open(target) as image:
                return image.size

        width, height = export(f"--export-width={INKSCAPE_LONG_SIDE_PX}")
        if width * height > INKSCAPE_MAX_PIXELS:  # un diseño muy alto: se vuelve a dibujar con el lado largo en el máximo
            width, height = export(f"--export-height={INKSCAPE_LONG_SIDE_PX}")
        with Image.open(target) as image:
            rgba = image.convert("RGBA")
        if rgba.getchannel("A").getbbox() is None:
            raise ConversionRefused("INVALID_REQUEST", "El dibujo está vacío: no hay nada para bordar.")
        output = BytesIO()
        rgba.save(output, format="PNG")
        return output.getvalue(), {"tool": "inkscape", "size_px": [width, height], "page": 1 if kind == PDF else None}
