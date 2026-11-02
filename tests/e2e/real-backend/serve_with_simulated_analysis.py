"""Backend real para verificar la web con una imagen SIN clave de OpenAI.

Solo el análisis de IA es simulado (una región que cubre la imagen, modelo `simulado-solo-pruebas`).
La vectorización E1, la API, el almacenamiento y las descargas son los reales.
Uso (desde la raíz del repo):  EMBROIDERY_API_CONFIG=ruta/a/config.json python tests/e2e/real-backend/serve_with_simulated_analysis.py
"""
from pathlib import Path
import sys

import uvicorn

ROOT = Path(__file__).resolve().parents[3]
for sub in ("services/api", "packages/contracts", "workers/embroidery"):
    sys.path.insert(0, str(ROOT / sub))

from embroidery_api.analysis import AnalysisProvider, ProviderResult  # noqa: E402
from embroidery_api.app import create_app  # noqa: E402
from embroidery_api.config import ApiConfig  # noqa: E402

MODEL = "simulado-solo-pruebas"


class SimulatedProvider(AnalysisProvider):
    provider_id = "openai"
    model = MODEL

    def analyze(self, image, media_type, width_px, height_px, cancel=None):
        region = {"x_px": 0, "y_px": 0, "width_px": width_px, "height_px": height_px, "visual_role": "Imagen completa (simulado)",
                  "observed_text": None, "suggested_colors": [], "uncertainties": []}
        return ProviderResult(regions=[region], model=MODEL, raw={"simulated": True}, duration_ms=1)


if __name__ == "__main__":
    uvicorn.run(create_app(ApiConfig.from_env(), analysis_providers={"openai": SimulatedProvider()}), host="127.0.0.1", port=8000)
