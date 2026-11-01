"""Three focused checks for the approved web-contract additions."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
SPEC = importlib.util.spec_from_file_location("build_openapi_b2", ROOT / "services" / "api" / "build_openapi.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

from embroidery_contracts import AuthorizedArtifactManifest, JobCreate, JobResponse, ProfileCatalog, ProjectDetail, RevisionRequest


def example_value(document, path, method, status, name="simulated"):
    return document["paths"][path][method]["responses"][status]["content"]["application/json"]["examples"][name]["value"]


class B2ContractTests(unittest.TestCase):
    def test_profile_reads_history_and_typed_revisions(self):
        document = builder.build_openapi()
        profiles = ProfileCatalog.model_validate(example_value(document, "/api/v1/profiles", "get", "200"))
        self.assertTrue(profiles.thread_profiles)
        self.assertTrue(all(not item.available and item.unavailable_reason for item in profiles.providers))
        detail = example_value(document, "/api/v1/projects/{id}", "get", "200")
        self.assertEqual(len(ProjectDetail.model_validate(detail).jobs), 2)
        foreign = copy.deepcopy(detail)
        foreign["assets"][0]["project_id"] = "foreign_project"
        with self.assertRaises(ValidationError):
            ProjectDetail.model_validate(foreign)
        for kind in ("size_variant", "correction"):
            entry = document["paths"]["/api/v1/projects/{id}/revisions"]["post"]
            request = entry["requestBody"]["content"]["application/json"]["examples"][kind]["value"]
            self.assertEqual(RevisionRequest.model_validate(request).root.kind, kind)
            child = JobResponse.model_validate(example_value(document, "/api/v1/projects/{id}/revisions", "post", "202", kind))
            self.assertEqual(child.parent_job_id, request["parent_job_id"])
            self.assertNotEqual(child.job_id, child.parent_job_id)
            self.assertNotEqual(child.revision_id, "rev_mock_1")
        correction = {"kind": "correction", "parent_job_id": "job_mock_1", "corrections": [{"action": "exclude_region", "region_id": "region_mock_1"}]}
        self.assertEqual(RevisionRequest.model_validate(correction).root.corrections[0].region_id, "region_mock_1")
        for target in ({}, {"object_id": "object_mock_1", "region_id": "region_mock_1"}):
            invalid = dict(correction, corrections=[dict(action="exclude_region", **target)])
            with self.subTest(target=target), self.assertRaises(ValidationError):
                RevisionRequest.model_validate(invalid)
        revisions = document["paths"]["/api/v1/projects/{id}/revisions"]["post"]
        initial = revisions["requestBody"]["content"]["application/json"]["examples"]["simulated"]["value"]
        with self.assertRaises(ValidationError):
            RevisionRequest.model_validate(dict(initial, base_revision_id="rev_mock_1"))
        response = example_value(document, "/api/v1/projects/{id}/revisions", "post", "201", "initial")
        with self.assertRaises(ValidationError):
            builder.RevisionResponse.model_validate(dict(response, base_revision_id="rev_mock_1", parent_job_id="job_mock_1", job_id="job_mock_2"))

    def test_server_views_hoop_and_artifact_guards(self):
        request = builder.fixture("generation-from-svg")
        request["settings"]["hoop_profile"] = "wrong_hoop"
        with self.assertRaises(ValidationError):
            JobCreate.model_validate(request)
        ready = builder.fixture("valid-result")
        for mutation in ("foreign_artifact", "missing_vector", "physical_approval", "contradictory_url"):
            invalid = copy.deepcopy(ready)
            if mutation == "foreign_artifact":
                invalid["artifact_manifest"]["artifacts"][0]["job_id"] = "foreign_job"
            elif mutation == "missing_vector":
                invalid["artifact_manifest"]["artifacts"] = [a for a in invalid["artifact_manifest"]["artifacts"] if a["kind"] != "editable_svg"]
            elif mutation == "physical_approval":
                invalid["sewout_status"] = "approved"
            else:
                invalid["artifact_manifest"]["artifacts"][0]["download_url"] = "https://example.invalid/wrong"
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                JobResponse.model_validate(invalid)
        failure = builder.fixture("failure")
        failure["failure"]["code"] = "WORKER_TIMEOUT"
        with self.assertRaises(ValidationError):
            JobResponse.model_validate(failure)
        physical = copy.deepcopy(ready)
        physical["sewout_status"] = "approved"
        physical["sewout_record"] = dict(builder.fixture("physical-sewout"), sewout_id="sewout_mock_1")
        physical["sewout_record"].pop("schema_version")
        for field in ("fabric_profile", "stabilizer", "thread"):
            physical["sewout_record"].pop(field)
        self.assertEqual(JobResponse.model_validate(physical).status.value, "ready_for_sewout")
        physical["sewout_record"]["revision_id"] = "foreign_revision"
        with self.assertRaises(ValidationError):
            JobResponse.model_validate(physical)

    def test_initial_flow_auth_cancel_and_download_policy(self):
        document = builder.build_openapi()
        steps = document["x-initial-flow"]["steps"]
        self.assertEqual([step["response_status"] for step in steps], [201, 201, 201, 202])
        self.assertEqual(steps[2]["request_body"]["base_revision_id"], None)
        self.assertEqual(steps[3]["request_body"]["revision_id"], steps[2]["response_body"]["revision_id"])
        missing_revision = builder.fixture("generation-from-svg")
        missing_revision.pop("revision_id")
        with self.assertRaises(ValidationError):
            JobCreate.model_validate(missing_revision)
        self.assertEqual(document["security"], [{"BasicAuth": []}, {"ServiceBearer": []}])
        cancel = document["paths"]["/api/v1/jobs/{id}/cancel"]["post"]
        self.assertEqual([code for code in cancel["responses"] if code.startswith("2")], ["202"])
        manifest = document["paths"]["/api/v1/jobs/{id}/artifacts"]["get"]
        self.assertEqual(manifest["responses"]["200"]["headers"]["Cache-Control"]["example"], "no-store")
        self.assertEqual(document["x-download-policy"]["ttl_seconds"], 300)
        manifest_payload = copy.deepcopy(builder.fixture("valid-result")["artifact_manifest"])
        for field in ("download", "download_url", "expires_at"):
            manifest_payload["artifacts"][0][field] = None
        with self.assertRaises(ValidationError):
            AuthorizedArtifactManifest.model_validate(manifest_payload)
        ready = builder.fixture("valid-result")
        download = ready["artifact_manifest"]["artifacts"][0]["download"]
        download["expires_at"] = "2026-11-01T12:00:01Z"
        with self.assertRaises(ValidationError):
            JobResponse.model_validate(ready)
        for entry in document["paths"].values():
            if "post" in entry:
                self.assertIn({"$ref": "#/components/parameters/IdempotencyKey"}, entry["post"]["parameters"])


if __name__ == "__main__":
    unittest.main()
