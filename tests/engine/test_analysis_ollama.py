"""H2 paquete C: adaptador del modelo de visión local (Ollama) con transporte falso; sin red ni servidor real."""
import base64
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_api.analysis import OllamaProvider, ProviderError, configured_providers, provider_availability
from embroidery_api.config import ApiConfig
from embroidery_contracts import IssueCode
from test_analysis_provider import Transport, region

MODEL = "qwen2.5vl:7b"


def ollama_reply(regions, **extra):
    document = {"model": MODEL, "done": True, "done_reason": "stop", "prompt_eval_count": 21, "eval_count": 9,
                "message": {"role": "assistant", "content": json.dumps({"regions": regions})}}
    document.update(extra)
    return 200, json.dumps(document).encode()


def ollama(reply, **kwargs):
    transport = Transport(reply)
    return OllamaProvider(MODEL, transport=transport, **kwargs), transport


def tags(*names):
    return lambda url, timeout: (200, json.dumps({"models": [{"name": name} for name in names]}).encode())


def down(url, timeout):
    raise urllib.error.URLError("rechazada")


class OllamaProviderTests(unittest.TestCase):
    def test_sends_the_image_as_plain_base64_with_a_schema_and_no_streaming(self):
        provider, transport = ollama(ollama_reply([region()]))
        result = provider.analyze(b"\x89PNG-bytes", "image/png", 200, 100)
        url, headers, payload, timeout = transport.requests[0]
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        self.assertNotIn("Authorization", headers)  # un servidor local no usa claves
        message = payload["messages"][0]
        self.assertEqual(message["images"], [base64.b64encode(b"\x89PNG-bytes").decode()])  # sin prefijo data:
        self.assertIn("200 × 100", message["content"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["format"]["type"], "object")
        self.assertEqual(payload["options"], {"temperature": 0, "seed": 0})
        self.assertEqual((result.model, result.input_tokens, result.output_tokens), (MODEL, 21, 9))
        self.assertEqual(len(result.regions), 1)

    def test_requires_the_model_from_private_configuration(self):
        with self.assertRaises(ValueError):
            OllamaProvider("")

    def test_every_failure_maps_to_a_catalogue_code(self):
        def reply(**document):
            return 200, json.dumps(document).encode()

        cases = {
            "server down": (urllib.error.URLError("rechazada"), IssueCode.LOCAL_MODEL_UNAVAILABLE),
            "timeout": (TimeoutError("lento"), IssueCode.LOCAL_MODEL_UNAVAILABLE),
            "model not installed": ((404, b'{"error":"model not found"}'), IssueCode.LOCAL_MODEL_UNAVAILABLE),
            "server error": ((500, b"oops"), IssueCode.LOCAL_MODEL_UNAVAILABLE),
            "unexpected status": ((400, b"{}"), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "not json": ((200, b"<html>"), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "cut by length": (reply(done_reason="length", message={"content": "{"}), IssueCode.ANALYSIS_INCOMPLETE),
            "no message": (reply(done=True), IssueCode.ANALYSIS_INCOMPLETE),
            "empty content": (reply(message={"content": "  "}), IssueCode.ANALYSIS_INCOMPLETE),
            "text instead of json": (reply(message={"content": "Veo un logo azul"}), IssueCode.ANALYSIS_SCHEMA_INVALID),
            "bad schema": (reply(message={"content": '{"otra": 1}'}), IssueCode.ANALYSIS_SCHEMA_INVALID),
        }
        for name, (answer, code) in cases.items():
            with self.subTest(name):
                provider, _ = ollama(answer)
                with self.assertRaises(ProviderError) as caught:
                    provider.analyze(b"x", "image/png", 10, 10)
                self.assertEqual(caught.exception.code, code)

    def test_never_retries_with_another_provider_and_honours_cancellation(self):
        provider, transport = ollama((500, b""))
        with self.assertRaises(ProviderError):
            provider.analyze(b"x", "image/png", 10, 10)
        self.assertEqual(len(transport.requests), 1)
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(ProviderError):
            provider.analyze(b"x", "image/png", 10, 10, cancelled)
        self.assertEqual(len(transport.requests), 1)  # ni siquiera llamó al servidor


class OllamaProbeTests(unittest.TestCase):
    def test_the_probe_checks_server_and_model_and_is_cached_for_a_few_seconds(self):
        clock = [0.0]
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return tags(MODEL, "otro:latest")(url, timeout)

        provider = OllamaProvider(MODEL, fetch=fetch, clock=lambda: clock[0])
        self.assertEqual(provider.probe(), (True, None))
        provider.probe()
        self.assertEqual(calls, ["http://127.0.0.1:11434/api/tags"])  # la segunda consulta salió del recuerdo
        clock[0] = OllamaProvider.PROBE_TTL_S + 1
        provider.probe()
        self.assertEqual(len(calls), 2)

    def test_the_probe_reports_why_it_is_unavailable(self):
        cases = {
            "no responde": (down, "no responde"),
            "no instalado": (tags("otro:latest"), "no está instalado"),
            "estado": (lambda url, timeout: (503, b""), "estado 503"),
            "ilegible": (lambda url, timeout: (200, b"{no es json"), "ilegible"),
        }
        for name, (fetch, text) in cases.items():
            with self.subTest(name):
                available, reason = OllamaProvider(MODEL, fetch=fetch).probe()
                self.assertFalse(available)
                self.assertIn(text, reason)

    def test_a_model_without_a_tag_means_latest(self):
        self.assertTrue(OllamaProvider("llava", fetch=tags("llava:latest")).probe()[0])


class OllamaConfigurationTests(unittest.TestCase):
    @staticmethod
    def config(**extra):
        return ApiConfig(
            data_root=ROOT, profiles_path=ROOT, python_executable=ROOT, inkstitch_executable=ROOT,
            engine_version="x", signing_key="s" * 32, public_base_url="http://x", service_token="t", **extra,
        )

    def test_the_local_model_is_configured_only_with_a_model(self):
        self.assertEqual(configured_providers(self.config()), {})
        providers = configured_providers(self.config(ollama_model=MODEL, ollama_base_url="http://192.168.1.50:11434"))
        self.assertEqual(set(providers), {"ollama"})
        self.assertEqual(providers["ollama"]._base, "http://192.168.1.50:11434")

    def test_invalid_values_are_rejected(self):
        for extra in ({"ollama_base_url": "ftp://x"}, {"ollama_timeout_s": 0}, {"ollama_timeout_s": float("inf")}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.config(**extra)

    def test_availability_is_live_for_ollama_and_static_for_validation(self):
        provider = OllamaProvider(MODEL, fetch=down)
        static = {item.provider_id: item for item in provider_availability({"ollama": provider})}
        live = {item.provider_id: item for item in provider_availability({"ollama": provider}, live=True)}
        self.assertTrue(static["ollama"].available)  # configurado: se puede pedir
        self.assertFalse(live["ollama"].available)   # pero hoy no responde: se dice
        self.assertIn("no responde", live["ollama"].unavailable_reason)


if __name__ == "__main__":
    unittest.main()
