"""H2: decisiones sobre un análisis visual, revisión analysis_retry y continuación tras aprobar."""
import importlib.util
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
SPEC = importlib.util.spec_from_file_location("build_openapi", ROOT / "services" / "api" / "build_openapi.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

from embroidery_contracts import AnalysisDecision, JobResponse, RevisionResponse, validate_transition


class AnalysisDecisionTests(unittest.TestCase):
    def test_approve_and_change_provider_validate(self):
        approve = AnalysisDecision.model_validate({"action": "approve"})
        self.assertEqual(approve.root.flagged_region_ids, ())
        marked = AnalysisDecision.model_validate({"action": "approve", "flagged_region_ids": ["region_3", "region_6"]})
        self.assertEqual(marked.root.flagged_region_ids, ("region_3", "region_6"))
        self.assertEqual(AnalysisDecision.model_validate({"action": "change_provider", "ai_provider": "ollama"}).root.ai_provider, "ollama")

    def test_rejects_client_state_unknown_provider_and_repeated_regions(self):
        for bad in (
            {"action": "approve", "status": "ready_for_sewout"},
            {"action": "change_provider", "ai_provider": "none"},
            {"action": "change_provider"},
            {"action": "approve", "flagged_region_ids": ["region_3", "region_3"]},
            {"action": "delete"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                AnalysisDecision.model_validate(bad)

    def test_analysis_retry_revision_needs_parent_base_and_job(self):
        ok = {"revision_id": "rev_2", "project_id": "p", "base_revision_id": "rev_1", "reason": "x", "created_at": "2026-11-01T10:00:00Z",
              "kind": "analysis_retry", "parent_job_id": "job_1", "job_id": "job_2"}
        self.assertEqual(RevisionResponse.model_validate(ok).kind, "analysis_retry")
        with self.assertRaises(ValidationError):
            RevisionResponse.model_validate(dict(ok, base_revision_id=None))

    def _continuation(self, status, vectorizing):
        payload = builder.continuation_example()
        payload.update(status=status)
        for record in payload["stages"]:
            if record["stage"] == "vectorizing":
                record["outcome"] = vectorizing
        return JobResponse.model_validate(payload)

    def test_continuation_after_approval_may_skip_analysis(self):
        previous = self._continuation("queued", "pending")
        following = self._continuation("vectorizing", "running")
        self.assertEqual(validate_transition(previous, following).status, "vectorizing")

    def test_other_jobs_still_cannot_skip_analysis(self):
        payload = builder.continuation_example()
        payload.update(status="queued", parent_job_id=None)
        previous = JobResponse.model_validate(payload)
        running = dict(payload, status="vectorizing")
        running["stages"] = [dict(r, outcome="running") if r["stage"] == "vectorizing" else r for r in payload["stages"]]
        with self.assertRaises(ValueError):
            validate_transition(previous, JobResponse.model_validate(running))
        analysis_not_skipped = dict(running, parent_job_id="job_mock_1")
        analysis_not_skipped["stages"] = [dict(r, outcome="completed", reason=None) if r["stage"] == "analyzing" else r for r in running["stages"]]
        with self.assertRaises(ValueError):
            validate_transition(self._continuation("queued", "pending"), JobResponse.model_validate(analysis_not_skipped))

    SKIP_REASON = "Sin análisis de IA: la persona eligió continuar sin él"

    def _unanalyzed(self, status, vectorizing, provider="none", analysis=("skipped", SKIP_REASON), input_kind="raster_image"):
        payload = builder.continuation_example()
        payload.update(status=status, parent_job_id=None, input_kind=input_kind)
        payload["settings_snapshot"] = dict(payload["settings_snapshot"], ai_provider=provider)
        for record in payload["stages"]:
            if record["stage"] == "analyzing":
                record.update(outcome=analysis[0], reason=analysis[1])
            if record["stage"] == "vectorizing":
                record["outcome"] = vectorizing
        return JobResponse.model_validate(payload)

    def test_an_image_sent_with_ai_none_may_skip_analysis_with_a_recorded_reason(self):
        """R5: la segunda vía para saltar el análisis (sin padre) está en states.md."""
        previous, following = self._unanalyzed("queued", "pending"), self._unanalyzed("vectorizing", "running")
        self.assertEqual(validate_transition(previous, following).status, "vectorizing")

    def test_the_no_ai_skip_has_its_own_conditions(self):
        cases = {
            "otro proveedor sin padre": dict(provider="openai"),
            "análisis no omitido": dict(analysis=("completed", None)),
            "SVG preparado": dict(input_kind="prepared_svg"),
        }
        for name, changes in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                validate_transition(self._unanalyzed("queued", "pending", **changes), self._unanalyzed("vectorizing", "running", **changes))

    def test_openapi_documents_both_operations(self):
        document = builder.build_openapi()
        self.assertIn("get", document["paths"]["/api/v1/jobs/{id}/analysis"])
        decision = document["paths"]["/api/v1/jobs/{id}/analysis-decision"]["post"]
        self.assertEqual(set(decision["responses"]) & {"202", "404", "409", "422"}, {"202", "404", "409", "422"})
        self.assertIn("analysis_retry", document["components"]["schemas"]["RevisionResponse"]["properties"]["kind"]["enum"])


if __name__ == "__main__":
    unittest.main()
