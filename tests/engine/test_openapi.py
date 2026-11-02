"""Small contract coherence checks; not an HTTP implementation or an OAS linter."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
SPEC = importlib.util.spec_from_file_location("build_openapi", ROOT / "services" / "api" / "build_openapi.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

from embroidery_contracts import Issue, IssueCode
from embroidery_contracts.http import ERROR_STATUS, ErrorCode
from embroidery_contracts.issues import ISSUE_RULES


def nodes(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


class OpenAPIContractTests(unittest.TestCase):
    def test_committed_schema_and_catalog_are_generated_from_models(self):
        for filename, generated in (
            ("openapi.json", builder.build_openapi()),
            ("issue-catalog.json", builder.build_issue_catalog()),
        ):
            with self.subTest(filename=filename):
                self.assertEqual((builder.CONTRACTS / filename).read_text(encoding="utf-8"), builder.render_json(generated))

    def test_fourteen_operations_refs_and_examples_are_coherent(self):
        document = builder.build_openapi()
        expected = {
            ("/api/v1/projects", "post"), ("/api/v1/projects/{id}/assets", "post"),
            ("/api/v1/projects/{id}/jobs", "post"), ("/api/v1/jobs/{id}", "get"),
            ("/api/v1/jobs/{id}/artifacts", "get"), ("/api/v1/jobs/{id}/cancel", "post"),
            ("/api/v1/projects/{id}/revisions", "post"), ("/api/v1/projects/{id}/sewouts", "post"),
            ("/api/v1/projects", "get"), ("/api/v1/projects/{id}", "get"),
            ("/api/v1/profiles", "get"), ("/api/v1/projects/{id}/revisions", "get"),
            ("/api/v1/jobs/{id}/analysis", "get"), ("/api/v1/jobs/{id}/analysis-decision", "post"),
        }
        self.assertEqual({(path, method) for path, entry in document["paths"].items() for method in entry}, expected)
        self._check_references(document)
        examples = self._validate_examples(document)
        for path in (builder.CONTRACTS / "fixtures").glob("*.json"):
            self.assertIn(json.loads(path.read_text(encoding="utf-8"))["payload"], examples)

    def _check_references(self, document):
        for node in nodes(document):
            if isinstance(node, dict) and "$ref" in node:
                self.assertTrue(node["$ref"].startswith("#/"))
                target = document
                for part in node["$ref"][2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]

    def _validate_examples(self, document):
        payloads = []
        for node in nodes(document["paths"]):
            if not isinstance(node, dict) or "examples" not in node or "schema" not in node:
                continue
            if "$ref" not in node["schema"]:
                continue
            model_name = node["schema"]["$ref"].rsplit("/", 1)[-1]
            for record in node["examples"].values():
                builder.FIXTURE_MODEL_NAMES[model_name].model_validate(record["value"])
                payloads.append(record["value"])
        return payloads

    def test_catalog_covers_enums_and_prevents_issue_downgrading(self):
        catalog = builder.build_issue_catalog()
        self.assertEqual(set(catalog["issues"]), set(IssueCode))
        self.assertEqual(set(ISSUE_RULES), set(IssueCode))
        self.assertEqual(set(catalog["http_errors"]), set(ErrorCode))
        self.assertEqual(set(ERROR_STATUS), set(ErrorCode))
        payload = builder.fixture("needs-review")["issues"][0]
        with self.assertRaises(ValidationError):
            Issue.model_validate(dict(payload, severity="info"))
        fallback = dict(payload, code="ENGINE_DIAGNOSTIC_UNCLASSIFIED", stage="geometry")
        self.assertEqual(Issue.model_validate(fallback).code, IssueCode.ENGINE_DIAGNOSTIC_UNCLASSIFIED)


if __name__ == "__main__":
    unittest.main()
