"""Guía 1.3: detectar las inscripciones de una imagen para que la persona confirme la frase antes de bordarla con letras de bordado.

Lee texto recto y texto en curva (sellos circulares) con los modelos PP-OCRv5 (detección + reconocimiento latino) a través de RapidOCR
sobre onnxruntime. No se usa PaddlePaddle: Smart App Control bloquea sus binarios en Windows y onnxruntime está firmado.
Texto en curva: se buscan círculos (Hough) y el anillo junto al borde se desenrolla en una tira recta (coordenadas polares).
Es una propuesta, no un bloqueo: la cursiva y las letras muy estilizadas pueden leerse mal, por eso la frase se confirma.
"""
from dataclasses import dataclass
import math
import threading
import time
import unicodedata
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from vectorize.inkstitch import REFERENCE_PULL_COMPENSATION_MM

from .legibility import raster_box

SMALL_LETTER_MM = 5.0         # el mismo umbral del microtexto en el motor (inkstitch.py, height_below_mm)
MIN_STRAIGHT_SCORE = 0.80
MIN_RING_SCORE = 0.90         # en el anillo desenrollado aparecen lecturas basura con 0,81-0,83
MIN_TEXT_CHARS = 2
MIN_RING_TEXT_CHARS = 4
RING_BANDS = (0.70, 0.78, 0.86)  # la banda de letras va de esta fracción del radio a + RING_BAND_SPAN
RING_BAND_SPAN = 0.20
RING_FRAGMENT_ZONE = (0.60, 1.05)  # lecturas rectas en esta corona son pedazos del texto en curva
RING_ANGLE_STEPS_PER_PX = 0.7      # pasos de ángulo por píxel de circunferencia (lo probado: 1440 a r = 330)
RING_ANGLE_STEPS = (720, 2880)
RING_EDGE_TOLERANCE = 0.02     # un círculo que sale del original más que esto no es un sello
MAX_RINGS = 3
INK_ROW_SHARE = 0.05          # una fila es de la letra si tiene al menos esta fracción de la fila más cargada
METHOD = (
    "PP-OCRv5 (detección + reconocimiento latino, RapidOCR/onnxruntime); texto en curva: círculos de Hough y anillo desenrollado en "
    "coordenadas polares; altura de letra medida sobre la tinta dentro de la caja"
)


class Inscription(BaseModel):
    inscription_id: str
    text: str
    confidence: float
    layout: Literal["straight", "curved"]
    bounds_px: tuple[int, int, int, int]   # x, y, ancho, alto en el original
    letter_height_px: float
    letter_height_mm: float | None         # solo si se pidió un tamaño
    small: bool | None
    confirmed_text: str | None = None
    arc: Literal["top", "bottom"] | None = None   # texto en curva: arco de arriba (horario) o de abajo (antihorario)
    use_font: bool = False                 # la persona eligió bordarla con letras de bordado (fuente de Ink/Stitch)


class InscriptionReport(BaseModel):
    """Inscripciones detectadas para confirmar. `available` es false si el servidor no tiene el lector instalado."""
    schema_version: str = "0.1-inscriptions"
    available: bool
    unavailable_reason: str | None = None
    inscriptions: list[Inscription]
    small_below_mm: float = SMALL_LETTER_MM
    duration_ms: int = 0
    method: str = METHOD


class ConfirmedInscription(BaseModel):
    inscription_id: str = Field(pattern=r"^inscription_\d{1,3}$")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    use_font: bool = False  # solo vale para texto en curva: se borda con la fuente en lugar del trazo copiado de la imagen


class InscriptionConfirmation(BaseModel):
    """La frase exacta que la persona confirma (o corrige) para cada inscripción detectada."""
    confirmed: list[ConfirmedInscription] = Field(max_length=64)


@dataclass(frozen=True)
class Detected:
    """Una lectura en píxeles del original, independiente del tamaño pedido."""
    text: str
    confidence: float
    layout: str
    bounds_px: tuple[int, int, int, int]
    letter_height_px: float
    circle_px: tuple[float, float, float] | None = None  # sello: centro y radio del círculo en el original
    arc: str | None = None


class ReaderUnavailable(Exception):
    """El lector de texto no está instalado o no pudo cargar sus modelos."""


_engine, _engine_lock = None, threading.Lock()


def _read_with_rapidocr(image):
    """[(cuatro puntos, texto, confianza)] de una imagen BGR. El motor se crea una vez y se usa de a una lectura."""
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
                _engine = RapidOCR(params={
                    "Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.MOBILE,
                    "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.MOBILE, "Rec.lang_type": LangRec.LATIN,
                })
            except Exception as exc:  # paquete ausente, DLL bloqueada o modelos sin descargar
                raise ReaderUnavailable(f"{type(exc).__name__}: {exc}") from None
        result = _engine(image)
    return list(zip(result.boxes if result.boxes is not None else (), result.txts or (), result.scores or ()))


def _key(text):
    """Clave para agrupar lecturas de la misma frase: sin tildes, sin espacios ni signos, en mayúsculas."""
    plain = unicodedata.normalize("NFKD", text)
    return "".join(c for c in plain if c.isalnum() and not unicodedata.combining(c)).upper()


def _ink_height(gray):
    """Alto de la tinta (px) dentro de un recorte: Otsu, la clase minoritaria es la tinta, filas con tinta de la primera a la última."""
    import cv2
    import numpy as np
    if gray.size == 0:
        return 0.0
    _, mask = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if mask.mean() > 0.5:
        mask = 1 - mask
    rows = mask.sum(axis=1)
    if rows.max() == 0:
        return 0.0
    filled = np.flatnonzero(rows >= INK_ROW_SHARE * rows.max())
    return float(filled[-1] - filled[0] + 1)


def _box(points):
    xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _decode(data):
    """BGR sobre blanco: un PNG con transparencia no puede dejar el fondo en negro (las letras oscuras desaparecerían)."""
    import cv2
    import numpy as np
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError("La imagen no se pudo leer.")
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        return (image[:, :, :3] * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return image


def _circles(image):
    """Sellos candidatos: círculos de Hough que entran enteros en el original."""
    import cv2
    h, w = image.shape[:2]
    gray = cv2.medianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 5)
    found = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.5, minDist=min(h, w) // 4, param1=120, param2=90,
                             minRadius=min(h, w) // 10, maxRadius=min(h, w) // 2)
    if found is None:
        return []
    inside = []
    for cx, cy, r in found[0]:
        slack = RING_EDGE_TOLERANCE * r
        if cx - r >= -slack and cy - r >= -slack and cx + r <= w + slack and cy + r <= h + slack:
            inside.append((float(cx), float(cy), float(r)))
    return inside[:MAX_RINGS]


def _arc(x, width, steps, mirrored):
    """Arco de una lectura por su posición, no por el volteo: el lector endereza también el texto girado 180°.

    En la tira (dos vueltas) la columna es el paso de ángulo de `warpPolar`, que crece en sentido horario desde +x; con y
    hacia abajo, de 180° a 360° es la mitad de arriba del sello.
    """
    angle = ((width - x if mirrored else x) / steps * 360) % 360
    return "top" if angle > 180 else "bottom"


def _ring_readings(image, circle, read):
    """Frases del anillo de un sello: varias bandas, arco de arriba (horario) y de abajo (antihorario), agrupadas por frase."""
    import cv2
    import numpy as np
    cx, cy, r = circle
    outer = int(r) + 10
    steps = int(min(max(round(2 * math.pi * r * RING_ANGLE_STEPS_PER_PX), RING_ANGLE_STEPS[0]), RING_ANGLE_STEPS[1]))
    polar = cv2.warpPolar(image, (outer, steps), (cx, cy), outer, cv2.WARP_POLAR_LINEAR)
    groups = {}
    for start in RING_BANDS:
        ring = polar[:, int(r * start):min(outer, int(r * (start + RING_BAND_SPAN)))]
        strip = cv2.transpose(np.vstack([ring, ring]))  # dos vueltas: ninguna palabra queda cortada en 0°
        for mirrored, band in ((False, cv2.flip(strip, 0)), (True, cv2.flip(strip, 1))):
            gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
            for points, text, score in read(band):
                key = _key(text)
                if score < MIN_RING_SCORE or len(key) < MIN_RING_TEXT_CHARS:
                    continue
                left, top, right, bottom = (int(round(v)) for v in _box(points))
                height = _ink_height(gray[max(0, top):max(0, bottom), max(0, left):max(0, right)])
                arc = _arc((left + right) / 2, band.shape[1], steps, mirrored)
                groups.setdefault(key, []).append((text.strip(), float(score), height, arc))
    # Una lectura parcial (una palabra suelta de la frase) no es otra inscripción.
    keys = [k for k in groups if not any(k != other and k in other for other in groups)]
    phrases = []
    for key in keys:
        # Se prefiere la lectura con espacios y tildes ("EL FORTÍN - CORDOBA" antes que "ELFORTIN-CORDOBA").
        text, score, height, arc = max(groups[key], key=lambda item: (len(item[0].split()), any(ord(c) > 127 for c in item[0]), item[1]))
        phrases.append((text, max(s for _t, s, _h, _a in groups[key]), height, arc))
    return phrases


def detect(data, read=None):
    """Lecturas de la imagen (bytes PNG/JPEG): primero los sellos en curva, después el texto recto que no es un pedazo de ellos."""
    try:
        import cv2  # noqa: F401  (si falta, no hay lector)
        import numpy  # noqa: F401
    except ImportError as exc:
        raise ReaderUnavailable(f"ImportError: {exc}") from None
    read = read or _read_with_rapidocr
    image = _decode(data)
    found, seals = [], []
    for circle in _circles(image):
        cx, cy, r = circle
        box = (int(cx - r), int(cy - r), int(2 * r), int(2 * r))
        phrases = _ring_readings(image, circle, read)
        if phrases:  # solo un círculo con texto en el anillo es un sello; Hough también toma flores o aros
            seals.append(circle)
        found += [Detected(text, round(score, 3), "curved", box, height, (float(cx), float(cy), float(r)), arc)
                  for text, score, height, arc in phrases]
    import cv2
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    for points, text, score in read(image):
        text = text.strip()
        if score < MIN_STRAIGHT_SCORE or len(_key(text)) < MIN_TEXT_CHARS:
            continue
        left, top, right, bottom = _box(points)
        mid_x, mid_y = (left + right) / 2, (top + bottom) / 2
        if any(RING_FRAGMENT_ZONE[0] * r <= math.hypot(mid_x - cx, mid_y - cy) <= RING_FRAGMENT_ZONE[1] * r for cx, cy, r in seals):
            continue
        crop = gray[max(0, int(top)):int(math.ceil(bottom)), max(0, int(left)):int(math.ceil(right))]
        box = (int(left), int(top), int(round(right - left)), int(round(bottom - top)))
        found.append(Detected(text, round(float(score), 3), "straight", box, _ink_height(crop)))
    return found


def mm_per_px(width_mm, height_mm, size):
    """Escala del original al tamaño pedido, como la aplica el runner a una imagen (cuadro raster y descuento de compensación)."""
    width_mm, height_mm = raster_box(width_mm, height_mm)
    inset = 2 * REFERENCE_PULL_COMPENSATION_MM
    if min(width_mm, height_mm) > 2 * inset:
        width_mm, height_mm = width_mm - inset, height_mm - inset
    return min(width_mm / size[0], height_mm / size[1])


def report(detected, size=None, width_mm=None, height_mm=None, confirmed=None, duration_ms=0):
    """Informe para la web. Una confirmación guardada vale solo si la lectura sigue siendo la misma que se confirmó."""
    scale = mm_per_px(width_mm, height_mm, size) if size and width_mm and height_mm else None
    confirmed = confirmed or {}
    items = []
    for number, item in enumerate(detected, start=1):
        inscription_id = f"inscription_{number}"
        letter_mm = round(item.letter_height_px * scale, 1) if scale else None
        saved = confirmed.get(inscription_id) or {}
        current = saved.get("detected") == item.text
        items.append(Inscription(
            inscription_id=inscription_id, text=item.text, confidence=item.confidence, layout=item.layout, bounds_px=item.bounds_px,
            letter_height_px=round(item.letter_height_px, 1), letter_height_mm=letter_mm,
            small=None if letter_mm is None else letter_mm < SMALL_LETTER_MM,
            confirmed_text=saved.get("confirmed") if current else None, arc=item.arc,
            use_font=bool(current and saved.get("use_font")),
        ))
    return InscriptionReport(available=True, inscriptions=items, duration_ms=duration_ms)


def unavailable(reason):
    return InscriptionReport(available=False, unavailable_reason=reason, inscriptions=[])


def timed_detect(data, read=None):
    started = time.monotonic()
    found = detect(data, read)
    return found, int((time.monotonic() - started) * 1000)
