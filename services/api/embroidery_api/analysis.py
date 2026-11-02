"""H2: análisis visual de una imagen. Interfaz de proveedores, adaptador de OpenAI y normalización.

Las claves viven solo en la configuración privada del backend. Un proveedor devuelve regiones ESTIMADAS
(cajas en píxeles del original); la salida se traduce al contrato AnalysisSpec y se vuelve a validar.
Nunca se cambia de proveedor en silencio: si el elegido falla, el trabajo informa el código del catálogo.
"""
import base64
from dataclasses import dataclass, field
import json
import re
import socket
import time
import urllib.error
import urllib.request

from embroidery_contracts import AnalysisSpec, Issue, IssueCode
from embroidery_contracts.issues import ISSUE_RULES
from embroidery_contracts.profiles import ProviderAvailability

PROMPT_VERSION = "analysis-v1"
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_REGIONS = 64
MAX_ERROR_BODY = 2000

PROMPT = (
    "Analizá este logo o dibujo para bordarlo. Devolvé las regiones visuales distintas (texto, símbolos, "
    "marcos, líneas, rellenos). Para cada una: la caja envolvente ESTIMADA en píxeles de la imagen original "
    "(origen arriba a la izquierda), su rol visual, el texto visible copiado tal cual o null, los colores "
    "dominantes en hexadecimal #RRGGBB y las dudas (trazos muy finos, texto pequeño, degradados, zonas "
    "ambiguas). No inventes elementos que no se vean. Las cajas son aproximadas."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["regions"],
    "properties": {
        "regions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["x_px", "y_px", "width_px", "height_px", "visual_role", "observed_text", "suggested_colors", "uncertainties"],
                "properties": {
                    "x_px": {"type": "number"}, "y_px": {"type": "number"},
                    "width_px": {"type": "number"}, "height_px": {"type": "number"},
                    "visual_role": {"type": "string"},
                    "observed_text": {"type": ["string", "null"]},
                    "suggested_colors": {"type": "array", "items": {"type": "string"}},
                    "uncertainties": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


class ProviderError(Exception):
    """Fallo controlado de un proveedor; `code` es un IssueCode del catálogo."""

    def __init__(self, code, detail):
        self.code = IssueCode(code)
        self.detail = detail
        super().__init__(detail)


@dataclass
class ProviderResult:
    regions: list
    model: str
    raw: dict
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    prompt_version: str = PROMPT_VERSION


class AnalysisProvider:
    """Contrato de un proveedor de visión: `analyze(...)` o ProviderError."""

    provider_id = ""
    model = ""

    def analyze(self, image, media_type, width_px, height_px, cancel=None):
        raise NotImplementedError


def default_transport(url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_ERROR_BODY * 10)


class OpenAIProvider(AnalysisProvider):
    """Responses API con entrada de imagen y salida estructurada (JSON Schema estricto)."""

    provider_id = "openai"

    def __init__(self, api_key, model, base_url="https://api.openai.com", timeout_s=60.0, transport=default_transport):
        if not api_key or not model:
            raise ValueError("OpenAIProvider requiere api_key y model de la configuración privada")
        self._api_key, self.model = api_key, model
        self._url = base_url.rstrip("/") + "/v1/responses"
        self._timeout, self._transport = timeout_s, transport

    def analyze(self, image, media_type, width_px, height_px, cancel=None):
        if cancel is not None and cancel.is_set():
            raise ProviderError(IssueCode.PROVIDER_UNAVAILABLE, "cancelled")
        data_url = f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"
        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": f"{PROMPT} Tamaño del original: {width_px} × {height_px} px."},
                {"type": "input_image", "image_url": data_url},
            ]}],
            "text": {"format": {"type": "json_schema", "name": "analysis_regions", "schema": RESPONSE_SCHEMA, "strict": True}},
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        started = time.monotonic()
        try:
            status, body = self._transport(self._url, headers, json.dumps(payload).encode("utf-8"), self._timeout)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            raise ProviderError(IssueCode.PROVIDER_UNAVAILABLE, f"connection:{type(exc).__name__}") from None
        duration_ms = int((time.monotonic() - started) * 1000)
        if status == 429:
            raise ProviderError(IssueCode.PROVIDER_RATE_LIMITED, "http_429")
        if status in (401, 403) or status >= 500:
            raise ProviderError(IssueCode.PROVIDER_UNAVAILABLE, f"http_{status}")
        if status != 200:
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, f"http_{status}")
        return self._parse(body, duration_ms)

    def _parse(self, body, duration_ms):
        try:
            document = json.loads(body)
        except ValueError:
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, "response_not_json") from None
        if not isinstance(document, dict):
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, "response_not_object")
        if document.get("status") == "incomplete":
            raise ProviderError(IssueCode.ANALYSIS_INCOMPLETE, str((document.get("incomplete_details") or {}).get("reason", "incomplete")))
        text = None
        for item in document.get("output") or []:
            for part in (item.get("content") or []) if isinstance(item, dict) else []:
                if part.get("type") == "refusal":
                    raise ProviderError(IssueCode.ANALYSIS_REFUSED, "model_refusal")
                if part.get("type") == "output_text":
                    text = part.get("text")
        if text is None:
            raise ProviderError(IssueCode.ANALYSIS_INCOMPLETE, "no_output_text")
        try:
            parsed = json.loads(text)
            regions = parsed["regions"]
        except (ValueError, KeyError, TypeError):
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, "output_not_matching_schema") from None
        usage = document.get("usage") or {}
        return ProviderResult(
            regions=regions, model=str(document.get("model") or self.model), raw=document, duration_ms=duration_ms,
            input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        )


@dataclass
class NormalizedAnalysis:
    spec: AnalysisSpec
    incoherent_region_ids: list = field(default_factory=list)


def normalize(result, provider_id, job_id, asset_id, width_px, height_px):
    """Traduce la salida del proveedor a AnalysisSpec. Los `region_id` los asigna el backend (estables y únicos).

    Datos imposibles (números no finitos, caja sin área, colores mal formados) invalidan la respuesta entera
    (ANALYSIS_SCHEMA_INVALID). Una caja que sale del original es una región incoherente: se conserva y se marca.
    """
    if not isinstance(result.regions, list) or not result.regions or len(result.regions) > MAX_REGIONS:
        raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, "regions_count")
    regions, incoherent = [], []
    for number, raw in enumerate(result.regions, start=1):
        try:
            box = [float(raw[key]) for key in ("x_px", "y_px", "width_px", "height_px")]
            colors = [str(c) for c in raw["suggested_colors"]]
            uncertainties = [str(u) for u in raw["uncertainties"]]
            role, text = str(raw["visual_role"]).strip(), raw["observed_text"]
        except (KeyError, TypeError, ValueError):
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, f"region_{number}_fields") from None
        x, y, width, height = box
        if not all(abs(v) < 1e9 and v == v for v in box) or width <= 0 or height <= 0 or x < 0 or y < 0:
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, f"region_{number}_box")
        if not role or any(not HEX_COLOR.match(c) for c in colors):
            raise ProviderError(IssueCode.ANALYSIS_SCHEMA_INVALID, f"region_{number}_values")
        region_id = f"region_{number}"
        if x + width > width_px or y + height > height_px:
            incoherent.append(region_id)
        regions.append({
            "region_id": region_id,
            "bounds_px": {"x_px": x, "y_px": y, "width_px": width, "height_px": height},
            "representation": "estimated_bbox", "visual_role": role,
            "observed_text": None if text is None else str(text),
            "suggested_colors": colors, "uncertainties": uncertainties,
        })
    spec = AnalysisSpec.model_validate({
        "analysis_id": f"analysis_{job_id}", "asset_id": asset_id, "provider": provider_id, "model": result.model,
        "prompt_version": result.prompt_version, "original_response_artifact_id": f"{job_id}_provider_raw_json",
        "regions": regions, "duration_ms": result.duration_ms,
        "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
    })
    return NormalizedAnalysis(spec=spec, incoherent_region_ids=incoherent)


def region_incoherent_issue(spec, region_id):
    """Aviso de revisión localizado (ANALYSIS_REGION_INCOHERENT) para una caja que sale del original."""
    region = next(r for r in spec.regions if r.region_id == region_id)
    rule = ISSUE_RULES[IssueCode.ANALYSIS_REGION_INCOHERENT]
    return Issue(
        code=IssueCode.ANALYSIS_REGION_INCOHERENT, severity=rule.severity, stage=rule.stage,
        region_ids=(region_id,), description="Una zona detectada por la IA no cabe dentro de la imagen original.",
        evidence={"reason": "box_outside_original", "bounds_px": region.bounds_px.model_dump(mode="json")},
        suggested_correction="Revisá esta zona del original o probá con otro proveedor de IA.",
    )


UNAVAILABLE_REASONS = {
    "openai": "OpenAI no está configurado en el servidor (clave y modelo).",
    "ollama": "El adaptador de modelo local todavía no está disponible.",
}


def configured_providers(config):
    """Proveedores realmente configurados en el backend; nunca hay un proveedor de reemplazo."""
    providers = {}
    if config.openai_api_key and config.openai_model:
        providers["openai"] = OpenAIProvider(
            config.openai_api_key, config.openai_model, config.openai_base_url, config.analysis_timeout_s,
        )
    return providers


def provider_availability(providers):
    return tuple(
        ProviderAvailability(provider_id=pid, available=pid in providers,
                             unavailable_reason=None if pid in providers else UNAVAILABLE_REASONS[pid])
        for pid in ("openai", "ollama")
    )
