"""Private runtime configuration. Executables and secrets are never API inputs."""
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path

from . import ROOT


@dataclass(frozen=True)
class ApiConfig:
    data_root: Path
    profiles_path: Path
    python_executable: Path
    inkstitch_executable: Path
    engine_version: str
    signing_key: str
    public_base_url: str
    inkscape_executable: Path | None = None
    service_token: str | None = None
    basic_username: str | None = None
    basic_password: str | None = None
    principal_id: str = "h0_user"
    timeout_s: float = 180
    max_workers: int = 1
    max_queued_jobs: int = 8
    dimension_tolerance_mm: float = 0.2
    worker_python_paths: tuple[Path, ...] = field(default_factory=tuple)
    worker_script: Path = ROOT / "workers" / "embroidery" / "worker.py"
    # Una imagen termina en un JEF con los parámetros de referencia (sin calibrar). Falso: se queda en la geometría de E1.
    raster_digitizing: bool = True
    # Ink/Stitch corre dos veces el plan de puntadas (diagnóstico y exportación): un diseño con flores y letras tarda minutos.
    digitizing_timeout_s: float = 600
    # H2: proveedores de visión. Las claves solo viven en esta configuración privada.
    # Sin `database_url` los datos van a SQLite dentro de `data_root`; con una URL `postgresql://` van a PostgreSQL. Es un secreto.
    database_url: str | None = field(default=None, repr=False)
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str | None = None
    openai_base_url: str = "https://api.openai.com"
    analysis_timeout_s: float = 60
    # H2: modelo de visión local (Ollama). Sin `ollama_model` el proveedor figura no disponible.
    ollama_model: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_s: float = 120

    def __post_init__(self):
        for name in ("data_root", "profiles_path", "python_executable", "inkstitch_executable", "worker_script"):
            object.__setattr__(self, name, Path(getattr(self, name)).resolve())
        if self.inkscape_executable is not None:
            object.__setattr__(self, "inkscape_executable", Path(self.inkscape_executable).resolve())
        object.__setattr__(self, "worker_python_paths", tuple(Path(p).resolve() for p in self.worker_python_paths))
        if not self.service_token and not (self.basic_username and self.basic_password):
            raise ValueError("Configure service_token or basic_username/basic_password")
        if bool(self.openai_api_key) != bool(self.openai_model):
            raise ValueError("openai_api_key and openai_model must be configured together")
        if not math.isfinite(self.analysis_timeout_s) or self.analysis_timeout_s <= 0:
            raise ValueError("analysis_timeout_s must be positive")
        if not math.isfinite(self.digitizing_timeout_s) or self.digitizing_timeout_s <= 0:
            raise ValueError("digitizing_timeout_s must be positive")
        if not math.isfinite(self.ollama_timeout_s) or self.ollama_timeout_s <= 0:
            raise ValueError("ollama_timeout_s must be positive")
        if not self.ollama_base_url.startswith(("http://", "https://")):
            raise ValueError("ollama_base_url must be an explicit HTTP(S) origin")
        if len(self.signing_key.encode()) < 32:
            raise ValueError("A private signing_key of at least 32 bytes is required")
        if not self.public_base_url.startswith(("http://", "https://")):
            raise ValueError("public_base_url must be an explicit HTTP(S) origin")
        if self.database_url is not None and not self.database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("database_url must be a postgresql:// URL")
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0 or self.max_workers < 1 or self.max_queued_jobs < 1:
            raise ValueError("Timeout and worker/queue bounds must be positive")
        if not math.isfinite(self.dimension_tolerance_mm) or self.dimension_tolerance_mm < 0:
            raise ValueError("dimension_tolerance_mm must be finite and nonnegative")

    @classmethod
    def from_env(cls):
        filename = os.environ.get("EMBROIDERY_API_CONFIG")
        if not filename:
            raise ValueError("EMBROIDERY_API_CONFIG must name a private configuration JSON")
        return cls(**json.loads(Path(filename).read_text(encoding="utf-8")))
