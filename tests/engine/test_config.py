"""ApiConfig checks for H0-04; no server or worker is started."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from embroidery_api.config import ApiConfig

COMMON = dict(
    profiles_path=ROOT / "services" / "api" / "profiles.json",
    python_executable=Path(sys.executable),
    inkstitch_executable=Path("inkstitch.exe"),
    engine_version="v3.2.2",
    signing_key="x" * 32,
    public_base_url="http://127.0.0.1:8000",
    service_token="test-token",
)


class ConfigTests(unittest.TestCase):
    def test_inkscape_is_optional_and_explicit_paths_are_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = dict(COMMON, data_root=Path(tmp))
            self.assertIsNone(ApiConfig(**base).inkscape_executable)
            explicit = ApiConfig(**base, inkscape_executable=Path("Inkscape") / "bin" / "inkscape.com")
            self.assertEqual(explicit.inkscape_executable, (Path("Inkscape") / "bin" / "inkscape.com").resolve())

    def test_from_env_reads_optional_inkscape(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = dict(COMMON, data_root=str(Path(tmp) / "data"))
            document["profiles_path"] = str(document["profiles_path"])
            document["python_executable"] = str(document["python_executable"])
            document["inkstitch_executable"] = str(document["inkstitch_executable"])
            document["inkscape_executable"] = str(Path(tmp) / "inkscape.com")
            filename = Path(tmp) / "config.json"
            filename.write_text(json.dumps(document), encoding="utf-8")
            with patch.dict(os.environ, {"EMBROIDERY_API_CONFIG": str(filename)}):
                config = ApiConfig.from_env()
            self.assertEqual(config.inkscape_executable, (Path(tmp) / "inkscape.com").resolve())

    def test_auth_and_signing_key_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = dict(COMMON, data_root=Path(tmp), service_token=None)
            with self.assertRaises(ValueError):
                ApiConfig(**base)
            with self.assertRaises(ValueError):
                ApiConfig(**dict(COMMON, data_root=Path(tmp), signing_key="short"))


if __name__ == "__main__":
    unittest.main()
