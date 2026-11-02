"""Pruebas del arnés F con un vectorize falso: comprueban que el arnés detecta fallos, no que E funcione."""
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest

import run_eval
from embroidery_contracts import EmbroideryDocument
from embroidery_contracts import IssueCode
from embroidery_contracts.design import DesignDecision, EmbroideryObject
from embroidery_contracts.issues import ISSUE_RULES
from embroidery_contracts.results import Issue


@dataclass(frozen=True)
class FakeResult:
    document: EmbroideryDocument
    issues: tuple
    editable_svg: str
    evidence: dict
    duration_ms: int


def make_result(asset, settings, *, width=None, colors=("#112233",), kind="verified_mask", mark=True, svg="<svg/>", extra=None):
    width = settings.target.width_mm if width is None else width
    bounds = {"min_x_mm": 0, "min_y_mm": 0, "max_x_mm": width, "max_y_mm": settings.target.height_mm}
    objects, decisions = [], []
    for index, color in enumerate(colors):
        object_id = f"object_{index}"
        objects.append(EmbroideryObject(
            object_id=object_id, geometry_kind=kind, path_data_mm="M0 0 L1 0 L1 1 Z", bounds_mm=bounds, role="forma", work_color=color,
            proposed_technique="fill", effective_technique="fill", parameters={"stitch_length_mm": 3.0},
        ))
        if mark:
            decisions.append(DesignDecision(object_id=object_id, reason="provisional", field="parameters",
                                            previous_value=None, new_value={run_eval.PROVISIONAL_FLAG: True}, origin="rule"))
    document = EmbroideryDocument(
        document_id="document_eval", revision_id="revision_eval", asset_id=asset.asset_id,
        coordinates={"transform_version": "t1"}, page_bounds_mm=bounds, object_bounds_mm=bounds, objects=tuple(objects), decisions=tuple(decisions),
    )
    evidence = {run_eval.PROVISIONAL_FLAG: mark, run_eval.TIMINGS_KEY: {"total_ms": 1}}
    evidence.update(extra or {})
    rule = ISSUE_RULES[IssueCode.DENSITY_REVIEW_REQUIRED]
    issues = (Issue(code=IssueCode.DENSITY_REVIEW_REQUIRED, severity=rule.severity, stage=rule.stage, object_ids=tuple(o.object_id for o in objects),
                    description="provisional", evidence={}, suggested_correction="validar en H3"),) if mark else ()
    return FakeResult(document, issues, svg, evidence, 5)


def manifest_dir(entries):
    directory = tempfile.TemporaryDirectory()
    root = Path(directory.name)
    manifest = {"schema_version": "0.1", "set_name": "t", "images": []}
    for entry in entries:
        (root / entry["file"]).write_bytes(b"\x89PNG-no-real-image")
        manifest["images"].append(entry)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory, root / "manifest.json"


ENTRY = {"id": "logo-prueba-01", "file": "logo_prueba_01.png", "design_family": "logo-prueba-01", "category": "flat_logo", "format": "png",
         "pixel_size": {"width": 100, "height": 80}, "expected_colors": 2, "target_size_mm": {"width_mm": 50, "height_mm": 40},
         "expected_outcome": "automatic"}


class HarnessTests(unittest.TestCase):
    def evaluate(self, vectorize_fn):
        directory, path = manifest_dir([ENTRY])
        self.addCleanup(directory.cleanup)
        return run_eval.run(vectorize_fn, path)

    def failed_checks(self, report):
        return {name for name, value in report["summary"]["checks"].items() if value["passed"] != value["of"]}

    def test_a_well_behaved_vectorize_passes_every_measured_check(self):
        report = self.evaluate(lambda data, media, asset, analysis, settings, **kw: make_result(asset, settings))
        self.assertEqual(report["status"], "passed")
        self.assertEqual(self.failed_checks(report), set())
        self.assertIn("iou_vs_mask", report["not_measured"])

    def test_detects_each_kind_of_violation(self):
        cases = {
            "within_target_contain": lambda a, s: make_result(a, s, width=s.target.width_mm + 5),
            "colors_within_limit": lambda a, s: make_result(a, s, colors=("#000001", "#000002", "#000003")),
            "geometry_kinds_allowed": lambda a, s: make_result(a, s, kind="prepared_svg_path"),
            "provisional_values_marked": lambda a, s: make_result(a, s, mark=False),
        }
        for check, build in cases.items():
            with self.subTest(check):
                report = self.evaluate(lambda data, media, asset, analysis, settings, build=build, **kw: build(asset, settings))
                self.assertEqual(report["status"], "failed")
                self.assertIn(check, self.failed_checks(report))

    def test_determinism_ignores_timings_but_not_the_svg(self):
        counter = iter(range(100))
        timings_only = lambda data, media, asset, analysis, settings, **kw: make_result(asset, settings, extra={run_eval.TIMINGS_KEY: {"total_ms": next(counter)}})  # noqa: E731
        self.assertEqual(self.failed_checks(self.evaluate(timings_only)), set())
        varying_svg = lambda data, media, asset, analysis, settings, **kw: make_result(asset, settings, svg=f"<svg id='{next(counter)}'/>")  # noqa: E731
        self.assertIn("deterministic", self.failed_checks(self.evaluate(varying_svg)))

    def test_a_raised_error_is_reported_not_hidden(self):
        def failing(*args, **kwargs):
            raise RuntimeError("no se pudo leer")
        report = self.evaluate(failing)
        self.assertEqual((report["status"], report["summary"]["errors"]), ("failed", 1))
        self.assertEqual(report["images"][0]["status"], "error")

    def test_static_review_flags_per_logo_literals(self):
        manifest = {"images": [ENTRY]}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "ok.py").write_text("THRESHOLD = 0.5\n", encoding="utf-8")
            self.assertEqual(run_eval.static_review(manifest, source), [])
            (source / "bad.py").write_text('if name == "logo_prueba_01.png":\n    pass\n', encoding="utf-8")
            findings = run_eval.static_review(manifest, source)
            self.assertTrue(findings)
            self.assertEqual({f["file"] for f in findings}, {"bad.py"})

    def test_reports_unavailable_vectorize_without_inventing_results(self):
        if run_eval.load_vectorize() is not None:
            self.skipTest("vectorize ya existe en este árbol")
        self.assertEqual(run_eval.main(["--only", "nada"]), 2)


if __name__ == "__main__":
    unittest.main()
