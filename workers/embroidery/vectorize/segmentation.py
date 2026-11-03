"""Deterministic colour masks from decoded pixels, without geometry inferred by AI."""
from array import array
from collections import Counter
from dataclasses import dataclass
from itertools import compress
from io import BytesIO
import hashlib
import math
import warnings

from PIL import Image, ImageChops, ImageFilter, ImageStat, UnidentifiedImageError, __version__ as PILLOW_VERSION

from embroidery_contracts import IssueCode
from .types import check_cancel, fail

# Refinamiento k-means del MEDIANCUT: sin él, un fondo tonal casi blanco se queda con casi toda la paleta y los trazos
# oscuros desaparecen (Anime Socks: 6,35 % de los píxeles con error de color >= 64 contra 0,04 % con 3 pasadas; trazos
# oscuros conservados 0 de 34 contra 29 de 34). Ver tests/h2_eval/informes/. Es una constante global, no un ajuste por logo.
QUANTIZER_KMEANS_PASSES = 3
WHITE_DISTANCE_MAX = 3 * 255
# Cobertura mínima de un píxel suavizado: un píxel del borde es una mezcla del color del grupo con el blanco del fondo; si
# tiene menos de la mitad de ese color y toca el fondo, se lo deja en el fondo (como un trazador a 50 % de cobertura). Sin
# esto, cada línea fina sale 1-2 px más ancha que en el original. Solo con fondo blanco quitado; con transparencia manda el alfa.
COVERAGE_MIN = 0.5
COVERAGE_LEVEL = math.ceil(COVERAGE_MIN * 255)
FRINGE_PASSES = 2  # anillos de píxeles que se pueden descartar desde el fondo hacia adentro
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_INPUT_PIXELS = 4_000_000
ALPHA_THRESHOLD = 128
WHITE_THRESHOLD = 250
WHITE_BORDER_CONSENSUS = 0.95
BACKGROUND = 65535
ROW_CANCEL_INTERVAL = 32


@dataclass(frozen=True)
class Segmentation:
    labels: array
    width: int
    height: int
    origin_x: int
    origin_y: int
    palette: dict[int, str]
    evidence: dict


def decode(image, media_type, asset, cancel):
    check_cancel(cancel)
    if media_type not in {"image/png", "image/jpeg"}:
        fail(IssueCode.INPUT_UNSUPPORTED_FORMAT, "E1 acepta imágenes PNG o JPEG.", "unsupported_media_type", media_type=media_type)
    if not isinstance(image, bytes) or not image:
        fail(IssueCode.INPUT_UNREADABLE, "La imagen codificada está vacía o no son bytes.", "invalid_image_bytes")
    if len(image) > MAX_INPUT_BYTES:
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite de bytes de E1.", "byte_limit", limit=MAX_INPUT_BYTES)
    if media_type != asset.media_type or hashlib.sha256(image).hexdigest() != asset.sha256:
        fail(IssueCode.INPUT_UNREADABLE, "La imagen no coincide con el asset original.", "asset_identity_mismatch")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(image)) as decoded:
                return _decode_checked(decoded, media_type, asset, cancel)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite de píxeles.", "decoder_pixel_limit")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        fail(IssueCode.INPUT_UNREADABLE, "La imagen no pudo decodificarse.", "decode_failed", error_type=type(exc).__name__)


def _decode_checked(decoded, media_type, asset, cancel):
    expected_format = {"image/png": "PNG", "image/jpeg": "JPEG"}[media_type]
    if decoded.format != expected_format:
        fail(IssueCode.INPUT_UNREADABLE, "El formato real no coincide con el declarado.", "decoded_format_mismatch")
    width, height = decoded.size
    if width * height > MAX_INPUT_PIXELS:
        fail(IssueCode.INPUT_TOO_LARGE, "La imagen supera el límite de píxeles de E1.", "pixel_limit", limit=MAX_INPUT_PIXELS)
    if (width, height) != (asset.original_width_px, asset.original_height_px):
        fail(IssueCode.INPUT_UNREADABLE, "Las dimensiones no coinciden con el asset.", "asset_dimensions_mismatch")
    if getattr(decoded, "n_frames", 1) != 1:
        fail(IssueCode.INPUT_UNREADABLE, "E1 no admite imágenes animadas.", "animated_input")
    if decoded.getexif().get(274, 1) != 1:
        fail(IssueCode.INPUT_UNREADABLE, "La orientación EXIF debe normalizarse antes de E1.", "exif_orientation_requires_normalization")
    decoded.load()
    check_cancel(cancel)
    return decoded.convert("RGBA")


def _crop(rgba, asset):
    crop = asset.crop_px
    if crop is None:
        return rgba, 0, 0
    values = (crop.x_px, crop.y_px, crop.width_px, crop.height_px)
    if any(value != math.floor(value) for value in values):
        fail(IssueCode.GEOMETRY_REPAIR_AMBIGUOUS, "E1 necesita un recorte alineado a píxeles completos.", "fractional_crop_not_supported")
    x, y, width, height = map(int, values)
    return rgba.crop((x, y, x + width, y + height)), x, y


def _white_mask(rgb):
    red, green, blue = rgb.split()
    darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
    return darkest.point(lambda value: 255 if value >= WHITE_THRESHOLD else 0)


def _border_white_fraction(white):
    width, height = white.size
    border = list(white.crop((0, 0, width, 1)).tobytes())
    if height > 1:
        border.extend(white.crop((0, height - 1, width, height)).tobytes())
    if height > 2:
        border.extend(white.crop((0, 1, 1, height - 1)).tobytes())
        if width > 1:
            border.extend(white.crop((width - 1, 1, width, height - 1)).tobytes())
    return sum(value == 255 for value in border) / len(border)


def _foreground(rgba):
    rgb = rgba.convert("RGB")
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    partial = sum(histogram[1:255])
    visible = alpha.point(lambda value: 255 if value >= ALPHA_THRESHOLD else 0)
    white = _white_mask(rgb)
    border_fraction = _border_white_fraction(white)
    transparent = alpha.getextrema()[0] < 255
    remove_white = not transparent and border_fraction >= WHITE_BORDER_CONSENSUS
    if remove_white:
        visible = ImageChops.subtract(visible, white)
    return rgb, visible, {
        "background_method": "alpha_threshold" if transparent else "white_border_consensus" if remove_white else "no_background_removed",
        "alpha_threshold": ALPHA_THRESHOLD,
        "partial_alpha_pixels": partial,
        "white_threshold": WHITE_THRESHOLD,
        "white_border_fraction": border_fraction,
        "white_removed_globally": remove_white,
        "background_is_assumption": not transparent,
    }


def segment(rgba, asset, color_limit, cancel):
    rgba, x, y = _crop(rgba, asset)
    rgb, mask, evidence = _foreground(rgba)
    width, height = rgb.size
    mask_bytes = mask.tobytes()
    rgb_bytes = rgb.tobytes()
    compact, positions = bytearray(), []
    for row in range(height):
        if row % ROW_CANCEL_INTERVAL == 0:
            check_cancel(cancel)
        for index in range(row * width, (row + 1) * width):
            if mask_bytes[index]:
                compact.extend(rgb_bytes[index * 3:index * 3 + 3])
                positions.append(index)
    if not compact:
        fail(IssueCode.GEOMETRY_INVALID, "No se encontraron píxeles de diseño.", "empty_foreground")
    check_cancel(cancel)
    foreground = Image.frombytes("RGB", (len(compact) // 3, 1), bytes(compact))
    quantized = foreground.quantize(
        colors=color_limit, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE, kmeans=QUANTIZER_KMEANS_PASSES,
    )
    check_cancel(cancel)
    quantized.putpalette(_median_member_palette(foreground, quantized))
    keep = None
    if evidence["white_removed_globally"]:
        # Se descarta el borde suavizado y los colores se recalculan con los píxeles que quedan (el núcleo del trazo).
        keep = _fringe_keep(rgb, mask, positions, quantized)
        quantized.putpalette(_median_member_palette(foreground, quantized, keep))
        keep = _fringe_keep(rgb, mask, positions, quantized)
    check_cancel(cancel)
    palette_bytes = quantized.getpalette()
    indices = quantized.tobytes()
    keep_bytes = keep.tobytes() if keep is not None else None
    kept_indices = indices if keep_bytes is None else bytes(compress(indices, keep_bytes))
    if not kept_indices:
        fail(IssueCode.GEOMETRY_INVALID, "No se encontraron píxeles de diseño.", "empty_foreground")
    palette = {index: "#" + bytes(palette_bytes[index * 3:index * 3 + 3]).hex() for index in sorted(set(kept_indices))}
    # Merge equal RGB entries: Pillow can return duplicate palette colours.
    by_color = {}
    remap = {index: by_color.setdefault(color, index) for index, color in palette.items()}
    palette = {index: color for color, index in by_color.items()}
    labels = array("H", [BACKGROUND]) * (width * height)
    source_index = 0
    for row in range(height):
        if row % ROW_CANCEL_INTERVAL == 0:
            check_cancel(cancel)
        for index in range(row * width, (row + 1) * width):
            if mask_bytes[index]:
                if keep_bytes is None or keep_bytes[source_index]:
                    labels[index] = remap[indices[source_index]]
                source_index += 1
    evidence.update({
        "pillow_version": PILLOW_VERSION,
        "quantizer": f"Pillow MEDIANCUT kmeans={QUANTIZER_KMEANS_PASSES}; no dithering; foreground pixels only; cluster colour = median member by distance from white",
        "foreground_pixels": len(kept_indices), "colour_limit": color_limit,
        "coverage_threshold": COVERAGE_MIN if keep is not None else None,
        "fringe_rule": f"coverage < {COVERAGE_MIN} and touching background, {FRINGE_PASSES} passes" if keep is not None else None,
        "fringe_pixels_removed": len(indices) - len(kept_indices),
        "output_colours": sorted(palette.values()),
        "quantization_is_lossy": True,
        **_quantization_evidence(foreground, quantized, keep),
        "source_mask_sha256": hashlib.sha256(mask_bytes).hexdigest(),
        "crop_box_px": [x, y, width, height],
        "pixels_discarded_by_size_filter": 0,
    })
    return Segmentation(labels, width, height, x, y, palette, evidence)


def _median_member_palette(foreground, quantized, keep=None):
    """Color de cada grupo = su miembro mediano por distancia al blanco, en lugar del promedio.

    El promedio mezcla el color del diseño con los píxeles suavizados del borde (que son una mezcla con el fondo) y deja
    todo más pálido: un azul 14285a salía 172a5c y una línea fina oscura, gris. Se elige la mediana ponderada por frecuencia
    tras ordenar por distancia al blanco y RGB; no necesariamente el color más frecuente. En las 14 imágenes, el error medio se reduce a la
    mitad en los logos planos (tests/h2_eval/informes/). Es determinista: se ordena por (distancia, RGB).
    """
    pixels = foreground.tobytes()
    pairs = zip(quantized.tobytes(), zip(pixels[0::3], pixels[1::3], pixels[2::3]))
    counts = Counter(pairs if keep is None else compress(pairs, keep.tobytes()))
    members = {}
    for (index, color), count in counts.items():
        members.setdefault(index, []).append((WHITE_DISTANCE_MAX - sum(color), color, count))
    palette = list(quantized.getpalette())
    for index, colours in members.items():
        colours.sort()
        half, seen = sum(count for _, _, count in colours) / 2, 0
        for _, color, count in colours:
            seen += count
            if seen >= half:
                palette[index * 3:index * 3 + 3] = color
                break
    return palette


def _low_coverage(rgb, index_image, palette):
    """Máscara 'L' (255) de los píxeles con cobertura < COVERAGE_MIN del color de su propio grupo.

    Un píxel p mezclado con blanco es p = blanco - a * (blanco - color); la cobertura `a` se obtiene por mínimos cuadrados
    sobre los tres canales. Se calcula con operaciones de imagen (una conversión lineal por grupo), sin recorrer píxeles.
    """
    low = Image.new("L", rgb.size, 0)
    for index in sorted(set(index_image.tobytes())):
        weights = [255 - channel for channel in palette[index * 3:index * 3 + 3]]
        denominator = sum(weight * weight for weight in weights)
        if denominator == 0:  # un grupo blanco puro no puede ser una mezcla
            continue
        scale = 255 / denominator
        # 255 * a = (255 / D) * (255 * sum(w) - sum(w * p)): coeficientes -w * scale y término constante 255 * sum(w) * scale.
        matrix = (-weights[0] * scale, -weights[1] * scale, -weights[2] * scale, 255 * sum(weights) * scale)
        weak = rgb.convert("L", matrix).point(lambda value: 255 if value < COVERAGE_LEVEL else 0)
        in_group = index_image.point(lambda value, wanted=index: 255 if value == wanted else 0)
        low = ImageChops.lighter(low, ImageChops.darker(weak, in_group))
    return low


def _fringe_keep(rgb, mask, positions, quantized):
    """Máscara compacta 'L' (255 = se queda): se descarta solo el borde suavizado.

    Un píxel sale si su cobertura es menor a COVERAGE_MIN **y toca el fondo** (vecindad de 8, FRINGE_PASSES anillos). Los
    píxeles débiles que quedan dentro de una forma, por ruido de JPEG o por un diseño casi blanco, se conservan: borrarlos
    abriría agujeros dentro del diseño.
    """
    palette = quantized.getpalette()
    width, height = rgb.size
    compact_indices = quantized.tobytes()
    scattered = bytearray(width * height)
    for offset, position in enumerate(positions):
        scattered[position] = compact_indices[offset]
    index_image = Image.frombytes("L", rgb.size, bytes(scattered))
    low = _low_coverage(rgb, index_image, palette)
    kept = mask
    for _ in range(FRINGE_PASSES):
        touches_background = ImageChops.darker(ImageChops.invert(kept).filter(ImageFilter.MaxFilter(3)), kept)
        dropped = ImageChops.darker(low, touches_background)
        if dropped.getbbox() is None:
            break
        kept = ImageChops.subtract(kept, dropped)
    kept_bytes = kept.tobytes()
    return Image.frombytes("L", (len(positions), 1), bytes(kept_bytes[position] for position in positions))


def _quantization_evidence(foreground, quantized, keep=None):
    difference = ImageChops.difference(foreground, quantized.convert("RGB"))
    red, green, blue = difference.split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    histogram = maximum.histogram(mask=keep)
    kept = sum(histogram)
    unique = foreground.getcolors(maxcolors=256)
    return {
        "changed_rgb_pixels": kept - histogram[0],
        "max_channel_error_rgb": max((value for value, count in enumerate(histogram) if count), default=0),
        "mean_absolute_channel_error_rgb": sum(ImageStat.Stat(difference, mask=keep).mean) / 3,
        "source_colour_count_up_to_256": len(unique) if unique is not None else None,
        "source_more_than_256_colours": unique is None,
    }
