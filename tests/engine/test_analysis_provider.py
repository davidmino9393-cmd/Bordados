"""H2: adaptador de OpenAI (transporte falso, sin red ni clave real) y normalización del análisis."""
import json
from pathlib import Path
import sys
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_api.analysis import (
    OpenAIProvider, ProviderError, ProviderResult, normalize, provider_availability, region_incoherent_issue,
)
from embroidery_api.config import ApiConfig
from embroidery_contracts import IssueCode

KEY = "sk-test-NOT-A-REAL-KEY"


def region(**overrides):
    base = {"x_px": 10, "y_px": 10, "width_px": 50, "height_px": 20, "visual_role": "Texto principal",
            "observed_text": "LOGO", "suggested_colors": ["#1F3A93"], "uncertainties": []}
    return {**base, **overrides}


def response(regions, **extra):
    text = json.dumps({"regions": regions})
    document = {"status": "completed", "model": "modelo-de-prueba", "usage": {"input_tokens": 11, "output_tokens": 7},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}
    document.update(extra)
    return 200, json.dumps(document).encode()


class Transport:
    def __init__(self, reply):
        self.reply, self.requests = reply, []

    def __call__(self, url, headers, body, timeout):
        self.requests.append((url, headers, json.loads(body), timeout))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def analyze(reply, **kwargs):
    transport = Transport(reply)
    provider = OpenAIProvider(KEY, "modelo-de-prueba", transport=transport, **kwargs)
    return provider, transport


class OpenAIProviderTests(unittest.TestCase):
    def test_sends_image_and_strict_schema_and_reads_structured_output(self):
        provider, transport = analyze(response([region()]))
        result = provider.analyze(b"\x89PNG-bytes", "image/png", 200, 100)
        url, headers, payload, timeout = transport.requests[0]
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(headers["Authorization"], f"Bearer {KEY}")
        content = payload["input"][0]["content"]
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))
        self.assertIn("200 × 100", content[0]["text"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertEqual(result.model, "modelo-de-prueba")
        self.assertEqual((result.input_tokens, result.output_tokens), (11, 7))
        self.assertEqual(len(result.regions), 1)

    def test_requires_key_and_model_from_private_configuration(self):
        for key, model in ((None, "m"), ("k", None), ("", "")):
            with self.subTest(key=key, model=model), self.assertRaises(ValueError):
                OpenAIProvider(key, model)

    def test_every_failure_maps_to_a_catalogue_code_without_leaking_the_key(self):
        cases = {
            "rate limit": ((429, b"{}"), IssueCode.PROVIDER_RATE_LIMITED),
            "bad credentials": ((401, b'{"error":"' + KEY.encode() + b'"}'), IssueCode.PROVIDER_UNAVAILABLE),
            "server error": ((503, b"oops"), IssueCode.PROVIDER_UNAVAILABLE),
            "unexpected status": ((400, b"{}"), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "not json": ((200, b"<html>"), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "incomplete": ((200, json.dumps({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}).encode()), IssueCode.ANALYSIS_INCOMPLETE),
            "refusal": ((200, json.dumps({"output": [{"content": [{"type": "refusal", "refusal": "no"}]}]}).encode()), IssueCode.ANALYSIS_REFUSED),
            "no text": ((200, json.dumps({"output": []}).encode()), IssueCode.ANALYSIS_INCOMPLETE),
            "bad schema": ((200, json.dumps({"output": [{"content": [{"type": "output_text", "text": "{\"otra\": 1}"}]}]}).encode()), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "connection": (urllib.error.URLError("sin red"), IssueCode.PROVIDER_UNAVAILABLE),
            "timeout": (TimeoutError("lento"), IssueCode.PROVIDER_UNAVAILABLE),
        }
        for name, (reply, code) in cases.items():
            with self.subTest(name):
                provider, _ = analyze(reply)
                with self.assertRaises(ProviderError) as caught:
                    provider.analyze(b"x", "image/png", 10, 10)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn(KEY, caught.exception.detail)

    def test_never_switches_provider_on_failure(self):
        provider, transport = analyze((503, b""))
        with self.assertRaises(ProviderError):
            provider.analyze(b"x", "image/png", 10, 10)
        self.assertEqual(len(transport.requests), 1)


def result(regions):
    return ProviderResult(regions=regions, model="m", raw={"ok": True}, duration_ms=5)


class NormalizeTests(unittest.TestCase):
    def test_assigns_stable_unique_region_ids_and_builds_a_valid_spec(self):
        normalized = normalize(result([region(), region(x_px=70, visual_role="Icono", observed_text=None)]), "openai", "job_1", "asset_1", 200, 100)
        spec = normalized.spec
        self.assertEqual([r.region_id for r in spec.regions], ["region_1", "region_2"])
        self.assertEqual(spec.analysis_id, "analysis_job_1")
        self.assertEqual(spec.original_response_artifact_id, "job_1_provider_raw_json")
        self.assertIsNone(spec.regions[1].observed_text)
        self.assertEqual(normalized.incoherent_region_ids, [])

    def test_a_box_outside_the_original_is_kept_and_flagged_as_incoherent(self):
        normalized = normalize(result([region(), region(x_px=180, width_px=50)]), "openai", "job_1", "asset_1", 200, 100)
        self.assertEqual(normalized.incoherent_region_ids, ["region_2"])
        issue = region_incoherent_issue(normalized.spec, "region_2")
        self.assertEqual((issue.code, issue.severity.value, issue.stage.value), (IssueCode.ANALYSIS_REGION_INCOHERENT, "review_required", "analysis"))
        self.assertEqual(issue.region_ids, ("region_2",))

    def test_impossible_values_invalidate_the_whole_response(self):
        bad = {
            "no regions": [], "zero area": [region(width_px=0)], "negative origin": [region(x_px=-1)],
            "nan": [region(x_px=float("nan"))], "bad colour": [region(suggested_colors=["rojo"])],
            "missing field": [{"x_px": 1}], "empty role": [region(visual_role="  ")],
        }
        for name, regions in bad.items():
            with self.subTest(name), self.assertRaises(ProviderError) as caught:
                normalize(result(regions), "openai", "j", "a", 200, 100)
            self.assertEqual(caught.exception.code, IssueCode.ANALYSIS_SCHEMA_INVALID)


class ConfigurationTests(unittest.TestCase):
    def config(self, **extra):
        return ApiConfig(
            data_root=ROOT, profiles_path=ROOT, python_executable=ROOT, inkstitch_executable=ROOT,
            engine_version="x", signing_key="s" * 32, public_base_url="http://x", service_token="t", **extra,
        )

    def test_key_and_model_go_together_and_the_key_is_not_in_repr(self):
        with self.assertRaises(ValueError):
            self.config(openai_api_key=KEY)
        with self.assertRaises(ValueError):
            self.config(openai_model="m")
        config = self.config(openai_api_key=KEY, openai_model="m")
        self.assertNotIn(KEY, repr(config))

    def test_availability_reflects_what_is_configured_and_never_a_fallback(self):
        both_off = {item.provider_id: item for item in provider_availability({})}
        self.assertFalse(both_off["openai"].available)
        self.assertIn("no está configurado", both_off["openai"].unavailable_reason)
        on = {item.provider_id: item.available for item in provider_availability({"openai": object()})}
        self.assertEqual(on, {"openai": True, "ollama": False})


if __name__ == "__main__":
    unittest.main()
