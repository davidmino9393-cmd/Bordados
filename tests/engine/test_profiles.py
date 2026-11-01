"""Profile catalog checks for H0-04; no HTTP or worker process is started."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))

from embroidery_contracts import JobSettings
from embroidery_api.errors import ApiProblem
from embroidery_api.profiles import load_profiles, validate_settings

CATALOG = ROOT / "services" / "api" / "profiles.json"
FIXTURE = ROOT / "packages" / "contracts" / "fixtures" / "generation-from-svg.json"


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_profiles(CATALOG)
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]
        self.settings = JobSettings.model_validate(payload["settings"])

    def test_fixture_settings_match_catalog(self):
        self.assertIs(validate_settings(self.settings, self.catalog), self.settings)
        self.assertEqual({item.profile_id for item in self.catalog.machines}, {"janome_mc550e"})
        self.assertEqual({item.profile_id for item in self.catalog.hoops}, {"sq20b"})
        self.assertEqual({item.profile_id for item in self.catalog.fabrics}, {"gabardina_inicial"})
        self.assertEqual({item.profile_id for item in self.catalog.thread_profiles}, {"embroidery_thread_initial"})

    def test_unknown_machine_is_rejected(self):
        settings = self.settings.model_copy(update={"machine_profile": "unknown_machine"})
        with self.assertRaises(ApiProblem) as caught:
            validate_settings(settings, self.catalog)
        self.assertEqual(caught.exception.code, "INVALID_REQUEST")

    def test_hoop_snapshot_must_match_catalog(self):
        settings = self.settings.model_copy(
            update={"hoop": self.settings.hoop.model_copy(update={"jef_hoop_code": 3})}
        )
        with self.assertRaises(ApiProblem) as caught:
            validate_settings(settings, self.catalog)
        self.assertEqual(caught.exception.code, "INVALID_REQUEST")

    def test_version_mismatch_is_rejected(self):
        settings = self.settings.model_copy(update={"fabric_profile_version": "9.9"})
        with self.assertRaises(ApiProblem) as caught:
            validate_settings(settings, self.catalog)
        self.assertEqual(caught.exception.code, "INVALID_REQUEST")


if __name__ == "__main__":
    unittest.main()
