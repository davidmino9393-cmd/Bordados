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


HOOPS = {"sq10b": (100, 100, 0), "sq14b": (140, 140, 2), "re20b": (140, 200, 2), "sq20b": (200, 200, 4), "re28b": (200, 280, 4), "re36b": (200, 360, 4)}
FABRICS = {"gabardina_inicial", "algodon", "gabardina", "pique", "polar", "jean", "lino"}


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_profiles(CATALOG)
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))["payload"]
        self.settings = JobSettings.model_validate(payload["settings"])

    def test_fixture_settings_match_catalog(self):
        self.assertIs(validate_settings(self.settings, self.catalog), self.settings)
        self.assertEqual({item.profile_id for item in self.catalog.machines}, {"janome_mc550e"})
        self.assertEqual({item.profile_id for item in self.catalog.hoops}, set(HOOPS))
        self.assertEqual({item.profile_id for item in self.catalog.fabrics}, set(FABRICS))
        self.assertEqual({item.profile_id for item in self.catalog.thread_profiles}, {"embroidery_thread_initial"})

    def test_janome_hoops_and_codes(self):
        by_id = {item.profile_id: item for item in self.catalog.hoops}
        for hoop_id, (width, height, code) in HOOPS.items():
            self.assertEqual((by_id[hoop_id].width_mm, by_id[hoop_id].height_mm, by_id[hoop_id].jef_hoop_code), (width, height, code))
        self.assertEqual(set(self.catalog.machines[0].hoop_profile_ids), set(HOOPS))
        self.assertEqual(by_id["sq20b"].profile_version, "0.1")

    def test_new_fabrics_are_proposed_not_calibrated(self):
        for fabric in self.catalog.fabrics:
            self.assertEqual(fabric.calibration_status, "proposed")
            self.assertIsNone(fabric.calibration_record_id)

    def test_color_limit_is_twelve(self):
        self.assertEqual(self.catalog.max_colors, 12)
        self.assertEqual(self.catalog.machines[0].max_colors, 12)
        validate_settings(self.settings.model_copy(update={"color_limit": 12}), self.catalog)
        with self.assertRaises(ApiProblem):
            validate_settings(self.settings.model_copy(update={"color_limit": 13}), self.catalog)

    def test_target_cannot_exceed_the_hoop(self):
        small = next(item for item in self.catalog.hoops if item.profile_id == "sq10b")
        settings = self.settings.model_copy(update={
            "hoop_profile": "sq10b", "hoop": self.settings.hoop.model_copy(update={
                "profile_id": "sq10b", "width_mm": small.width_mm, "height_mm": small.height_mm, "jef_hoop_code": small.jef_hoop_code})})
        with self.assertRaises(ApiProblem) as caught:
            validate_settings(settings.model_copy(update={"target": settings.target.model_copy(update={"width_mm": 101, "height_mm": 50})}), self.catalog)
        self.assertEqual(caught.exception.code, "INVALID_REQUEST")
        self.assertIn("SQ10b", caught.exception.detail)
        validate_settings(settings.model_copy(update={"target": settings.target.model_copy(update={"width_mm": 100, "height_mm": 100})}), self.catalog)

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
