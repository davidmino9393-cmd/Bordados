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

    def __post_init__(self):
        for name in ("data_root", "profiles_path", "python_executable", "inkstitch_executable", "worker_script"):
            object.__setattr__(self, name, Path(getattr(self, name)).resolve())
        object.__setattr__(self, "worker_python_paths", tuple(Path(p).resolve() for p in self.worker_python_paths))
        if not self.service_token and not (self.basic_username and self.basic_password):
            raise ValueError("Configure service_token or basic_username/basic_password")
        if len(self.signing_key.encode()) < 32:
            raise ValueError("A private signing_key of at least 32 bytes is required")
        if not self.public_base_url.startswith(("http://", "https://")):
            raise ValueError("public_base_url must be an explicit HTTP(S) origin")
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
