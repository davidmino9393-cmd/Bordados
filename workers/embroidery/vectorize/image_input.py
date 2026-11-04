"""Shared, bounded PNG/JPEG decoding in the visual EXIF coordinate frame."""
from dataclasses import dataclass
import hashlib
from io import BytesIO
import struct
import warnings

from PIL import Image, UnidentifiedImageError

from embroidery_contracts import IssueCode
from .types import check_cancel, fail

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_INPUT_PIXELS = 20_000_000
FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG"}
EXIF_ORIENTATION_TAG = 274
EXIF_TRANSFORMS = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


@dataclass(frozen=True)
class DecodedRaster:
    rgba: Image.Image
    raw_size: tuple[int, int]
    orientation: int
    sha256: str

    @property
    def size(self) -> tuple[int, int]:
        return self.rgba.size

    def analysis_png(self, cancel=None) -> bytes:
        """Lossless oriented pixels, without EXIF or inherited encoder metadata."""
        check_cancel(cancel)
        clean = Image.new("RGBA", self.size)
        clean.paste(self.rgba)
        output = BytesIO()
        clean.save(output, format="PNG")
        check_cancel(cancel)
        return output.getvalue()


def _validate_encoded(data, media_type, cancel):
    check_cancel(cancel)
    if media_type not in FORMATS:
        fail(IssueCode.INPUT_UNSUPPORTED_FORMAT, "Solo se admiten imágenes PNG o JPEG.",
             "unsupported_media_type", media_type=media_type)
    if not isinstance(data, bytes) or not data:
        fail(IssueCode.INPUT_UNREADABLE, "La imagen está vacía o no son bytes.", "invalid_image_bytes")
    if len(data) > MAX_INPUT_BYTES:
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite compartido de bytes.",
             "byte_limit", limit=MAX_INPUT_BYTES)


def _validate_exif_header(raw):
    """Reject truncated or out-of-bounds root TIFF data before Pillow can ignore it."""
    if not raw:
        return
    tiff = raw[6:] if raw.startswith(b"Exif\0\0") else raw
    if len(tiff) < 8 or tiff[:4] not in (b"II*\0", b"MM\0*"):
        raise ValueError("invalid EXIF TIFF header")
    order = "little" if tiff[:2] == b"II" else "big"
    offset = int.from_bytes(tiff[4:8], order)
    if offset < 8 or offset + 2 > len(tiff):
        raise ValueError("EXIF root directory outside metadata")
    entries = int.from_bytes(tiff[offset:offset + 2], order)
    if offset + 2 + entries * 12 + 4 > len(tiff):
        raise ValueError("truncated EXIF root directory")


def _orientation(image):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            _validate_exif_header(image.info.get("exif"))
            orientation = image.getexif().get(EXIF_ORIENTATION_TAG, 1)
        if type(orientation) is not int or orientation not in range(1, 9):
            raise ValueError("EXIF orientation must be an integer from 1 to 8")
        return orientation
    except (OSError, ValueError, SyntaxError, TypeError, IndexError, struct.error, UserWarning) as exc:
        fail(IssueCode.INPUT_UNREADABLE, "Los metadatos EXIF están dañados o la orientación no es válida.",
             "invalid_exif", error_type=type(exc).__name__)


def _decode_checked(image, media_type, cancel):
    if image.format != FORMATS[media_type]:
        fail(IssueCode.INPUT_UNREADABLE, "El formato real no coincide con el declarado.", "decoded_format_mismatch")
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_INPUT_PIXELS:
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite compartido de píxeles.",
             "pixel_limit", limit=MAX_INPUT_PIXELS)
    if getattr(image, "n_frames", 1) != 1:
        fail(IssueCode.INPUT_UNREADABLE, "No se admiten imágenes animadas.", "animated_input")
    orientation = _orientation(image)
    image.load()
    check_cancel(cancel)
    rgba = image.convert("RGBA")
    operation = EXIF_TRANSFORMS.get(orientation)
    if operation is not None:
        rgba = rgba.transpose(operation)
    rgba.info.clear()
    check_cancel(cancel)
    return rgba, orientation


def decode_raster(data: bytes, media_type: str, cancel=None) -> DecodedRaster:
    """Decode original bytes once; crop/analysis dimensions use the returned visual size."""
    _validate_encoded(data, media_type, cancel)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            warnings.filterwarnings("error", message=r".*(EXIF|TIFF).*", category=UserWarning)
            with Image.open(BytesIO(data)) as image:
                raw_size = image.size
                rgba, orientation = _decode_checked(image, media_type, cancel)
        return DecodedRaster(rgba, raw_size, orientation, hashlib.sha256(data).hexdigest())
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite de descompresión.", "decoder_pixel_limit")
    except UserWarning as exc:
        fail(IssueCode.INPUT_UNREADABLE, "Los metadatos EXIF están dañados.",
             "invalid_exif", error_type=type(exc).__name__)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, struct.error) as exc:
        fail(IssueCode.INPUT_UNREADABLE, "La imagen no pudo decodificarse.",
             "decode_failed", error_type=type(exc).__name__)
