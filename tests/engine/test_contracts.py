"""Minimal Tanda A checks, without running the original embroidery scripts."""
import copy
import json
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))

from embroidery_contracts import JobCreate, JobResponse, JobStatus, RevisionCreate, SewoutRecord, validate_transition

FIXTURES = ROOT / "packages" / "contracts" / "fixtures"
MODELS = {model.__name__: model for model in (JobCreate, JobResponse, SewoutRecord)}


def fixture(case):
    return json.loads((FIXTURES / f"{case}.json").read_text(encoding="utf-8"))


class ContractTests(unittest.TestCase):
    def test_six_versioned_simulated_examples_validate(self):
        cases = sorted(FIXTURES.glob("*.json"))
        self.assertEqual(len(cases), 6)
        for path in cases:
            with self.subTest(case=path.stem):
                document = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(document["schema_version"], "0.1")
                self.assertIs(document["simulated"], True)
                MODELS[document["model"]].model_validate(document["payload"])
        initial = RevisionCreate.model_validate({
            "base_revision_id": None, "reason": "Initial project revision",
            "settings": fixture("generation-from-svg")["payload"]["settings"],
        })
        self.assertIsNone(initial.base_revision_id)

    def test_invalid_size_and_client_assigned_states_are_rejected(self):
        payload = fixture("generation-from-svg")["payload"]
        for field, value in (("width_mm", 0), ("height_mm", float("nan"))):
            invalid = copy.deepcopy(payload)
            invalid["settings"]["target"][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                JobCreate.model_validate(invalid)
        with self.assertRaises(ValidationError):
            JobCreate.model_validate(dict(payload, status="ready_for_sewout"))
        with self.assertRaises(ValidationError):
            JobCreate.model_validate(dict(payload, physical_status="approved"))

    def test_ready_requires_coherent_digital_evidence_references(self):
        payload = fixture("valid-result")["payload"]
        for change in ("missing_report", "wrong_revision", "unresolved_satin", "missing_raw_commands"):
            invalid = copy.deepcopy(payload)
            if change == "missing_report":
                invalid["validation_report"] = None
            elif change == "wrong_revision":
                invalid["artifact_manifest"]["revision_id"] = "rev_other"
            elif change == "missing_raw_commands":
                invalid["artifact_manifest"]["artifacts"] = [
                    a for a in invalid["artifact_manifest"]["artifacts"] if a["kind"] != "raw_commands_json"
                ]
            else:
                invalid["issues"] = fixture("needs-review")["payload"]["issues"]
            with self.subTest(change=change), self.assertRaises(ValidationError):
                JobResponse.model_validate(invalid)

    def test_transitions_reject_skip_and_terminal_restart(self):
        ready = JobResponse.model_validate(fixture("valid-result")["payload"])
        queued = JobResponse.model_validate(dict(ready.model_dump(), status="queued", validation_report=None, artifact_manifest=None))
        with self.assertRaises(ValueError):
            validate_transition(queued, ready)
        with self.assertRaises(ValueError):
            validate_transition(ready, queued)
        digitizing = JobResponse.model_validate(dict(queued.model_dump(), status="digitizing"))
        self.assertEqual(validate_transition(queued, digitizing).status, JobStatus.DIGITIZING)
        invalid_skip = JobResponse.model_validate(dict(digitizing.model_dump(), stages=[]))
        with self.assertRaises(ValueError):
            validate_transition(queued, invalid_skip)

    def test_physical_approval_is_not_a_digital_state(self):
        ready = fixture("valid-result")["payload"]
        with self.assertRaises(ValidationError):
            JobResponse.model_validate(dict(ready, status="approved"))
        record = fixture("physical-sewout")["payload"]
        self.assertEqual(SewoutRecord.model_validate(record).status, "approved")
        with self.assertRaises(ValidationError):
            SewoutRecord.model_validate(dict(record, tested_at=None))


if __name__ == "__main__":
    unittest.main()
