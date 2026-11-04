"""HTTP integration checks for H0-04 using a deterministic worker fixture."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

import uvicorn

import embroidery_api.app as api_app
import embroidery_api.runner as api_runner
from embroidery_api.app import create_app
from embroidery_api.config import ApiConfig
from embroidery_api.runner import JobRunner
from embroidery_api.svg_fit import fit_to_target


TOKEN = "test-token"
SETTINGS = json.loads((ROOT / "packages" / "contracts" / "fixtures" / "generation-from-svg.json").read_text(encoding="utf-8"))["payload"]["settings"]
FAKE_WORKER = ROOT / "tests" / "engine" / "fixtures" / "fake_worker.py"


def svg(marker="", path_id="shape_1", root='width="10mm" height="10mm" viewBox="0 0 10 10"'):
    comment = f"<!-- {marker} -->" if marker else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" {root}>'
        f'{comment}<path id="{path_id}" d="M 0 0 L 10 10"/></svg>'
    ).encode()


def header(headers, name):
    return next((value for key, value in headers.items() if key.lower() == name.lower()), None)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = ApiConfig(
            data_root=Path(self.tmp.name) / "data",
            profiles_path=ROOT / "services" / "api" / "profiles.json",
            python_executable=Path(sys.executable),
            inkstitch_executable=Path(sys.executable),
            engine_version="fake-engine",
            signing_key="s" * 32,
            public_base_url="http://testserver",
            service_token=TOKEN,
            max_workers=1,
            max_queued_jobs=8,
            timeout_s=20,
            worker_script=FAKE_WORKER,
        )
        self.server = uvicorn.Server(uvicorn.Config(
            create_app(config), host="127.0.0.1", port=0, log_level="critical",
        ))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started and time.time() < deadline:
            time.sleep(0.01)
        if not self.server.started:
            self.fail("uvicorn did not start")
        self.base_url = f"http://127.0.0.1:{self.server.servers[0].sockets[0].getsockname()[1]}"
        self.addCleanup(self._stop)

    def _stop(self):
        self.server.should_exit = True
        self.thread.join(10)

    def request(self, method, path, body=None, headers=None, auth=True, raw=None, content_type=None):
        values = {}
        if auth:
            values["Authorization"] = f"Bearer {TOKEN}"
        if headers:
            values.update(headers)
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            values["Content-Type"] = "application/json"
        if content_type:
            values["Content-Type"] = content_type
        request = urllib.request.Request(self.base_url + path, data=data, headers=values, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, dict(exc.headers), exc.read()
            finally:
                exc.close()

    def json_request(self, method, path, body=None, headers=None, auth=True, raw=None, content_type=None):
        status, response_headers, payload = self.request(
            method, path, body, headers, auth, raw, content_type
        )
        return status, response_headers, json.loads(payload) if payload else None

    def post(self, path, body, key=None):
        return self.json_request("POST", path, body, {"Idempotency-Key": key or uuid.uuid4().hex})

    def upload(self, project_id, content, filename="design.svg"):
        boundary = "----h004" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: image/svg+xml\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.json_request(
            "POST", f"/api/v1/projects/{project_id}/assets", headers={
                "Idempotency-Key": uuid.uuid4().hex,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }, raw=body,
        )

    def setup_project(self, content, settings=SETTINGS):
        status, _, project = self.post("/api/v1/projects", {"name": "Integration"})
        self.assertEqual(status, 201, project)
        project_id = project["project_id"]
        status, _, asset = self.upload(project_id, content)
        self.assertEqual(status, 201, asset)
        revision = {
            "schema_version": "0.1", "base_revision_id": None, "reason": "initial",
            "settings": settings, "document": None,
        }
        status, _, revision = self.post(f"/api/v1/projects/{project_id}/revisions", revision)
        self.assertEqual(status, 201, revision)
        return project_id, asset["asset_id"], revision["revision_id"]

    def create_job(self, project_id, asset_id, revision_id, settings=SETTINGS):
        body = {
            "schema_version": "0.1", "asset_id": asset_id,
            "revision_id": revision_id, "input_kind": "prepared_svg", "settings": settings,
        }
        started = time.perf_counter()
        status, _, job = self.post(f"/api/v1/projects/{project_id}/jobs", body)
        return status, job, time.perf_counter() - started

    def wait_job(self, project_id, job_id, statuses, timeout=20):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status, _, job = self.json_request("GET", f"/api/v1/jobs/{job_id}")
            if status == 200 and job["status"] in statuses:
                return job
            time.sleep(0.05)
        self.fail(f"job {job_id} did not reach {statuses}")

    def artifacts(self, job_id):
        return self.json_request("GET", f"/api/v1/jobs/{job_id}/artifacts")

    def test_artifact_states_and_download(self):
        project_id, asset_id, revision_id = self.setup_project(svg("FAKE_SLEEP"))
        status, first, _ = self.create_job(project_id, asset_id, revision_id)
        self.assertEqual(status, 202)
        self.assertEqual(first["status"], "queued")
        self.wait_job(project_id, first["job_id"], {"digitizing"})
        status, second, _ = self.create_job(project_id, asset_id, revision_id)
        self.assertEqual(status, 202)
        self.assertEqual(second["status"], "queued")

        for job in (first, second):
            status, headers, problem = self.artifacts(job["job_id"])
            self.assertEqual(status, 409, problem)
            self.assertEqual(problem["code"], "ARTIFACTS_UNAVAILABLE")
            self.assertEqual(header(headers, "Cache-Control"), "no-store")
            self.assertTrue(header(headers, "X-Request-ID"))

        for job in (first, second):
            status, _, _ = self.post(f"/api/v1/jobs/{job['job_id']}/cancel", {})
            self.assertEqual(status, 202)
        for job in (first, second):
            self.wait_job(project_id, job["job_id"], {"cancelled"})

        status, _, failed_asset = self.upload(project_id, svg("FAKE_FAIL"))
        self.assertEqual(status, 201)
        status, failed, _ = self.create_job(project_id, failed_asset["asset_id"], revision_id)
        self.assertEqual(status, 202)
        failed = self.wait_job(project_id, failed["job_id"], {"failed"})
        self.assertEqual(failed["failure"]["code"], "INPUT_UNREADABLE")
        status, _, problem = self.artifacts(failed["job_id"])
        self.assertEqual(status, 409, problem)
        self.assertEqual(problem["code"], "ARTIFACTS_UNAVAILABLE")

        status, _, good_asset = self.upload(project_id, svg())
        self.assertEqual(status, 201)
        status, good, _ = self.create_job(project_id, good_asset["asset_id"], revision_id)
        self.assertEqual(status, 202)
        good = self.wait_job(project_id, good["job_id"], {"needs_review"})
        status, _, manifest = self.artifacts(good["job_id"])
        self.assertEqual(status, 200, manifest)
        self.assertTrue(manifest["artifacts"])
        jef = next(item for item in manifest["artifacts"] if item["kind"] == "jef")
        self.assertTrue(jef["download"]["url"].startswith("http://testserver/downloads/"))
        self.assertEqual(jef["download_url"], jef["download"]["url"])
        path = urllib.parse.urlsplit(jef["download"]["url"]).path
        status, headers, payload = self.request("GET", path, auth=False)
        self.assertEqual(status, 200)
        self.assertEqual(len(payload), jef["byte_size"])
        self.assertEqual(header(headers, "Cache-Control"), "no-store")
        self.assertTrue(header(headers, "X-Request-ID"))

    def test_a_cancel_accepted_while_the_worker_finishes_leaves_the_job_cancelled_without_artifacts(self):
        """R1: el subproceso terminó y falta guardar el resultado; la cancelación (202) llega justo en esa ventana."""
        project_id, asset_id, revision_id = self.setup_project(svg())
        reached, release = threading.Event(), threading.Event()

        def hold(_runner, _job_id):
            reached.set()
            release.wait(15)

        with patch.object(JobRunner, "_worker_finished", hold):
            status, job, _ = self.create_job(project_id, asset_id, revision_id)
            self.assertEqual(status, 202)
            self.assertTrue(reached.wait(15), "el worker no llegó a terminar")
            status, _, accepted = self.post(f"/api/v1/jobs/{job['job_id']}/cancel", {})
            self.assertEqual(status, 202)
            self.assertTrue(accepted["cancellation_requested"])
            self.assertEqual(accepted["status"], "digitizing")  # el resultado todavía no se guardó
            release.set()
            final = self.wait_job(project_id, job["job_id"], {"cancelled", "needs_review", "failed"})
        self.assertEqual(final["status"], "cancelled")
        self.assertTrue(final["cancellation_requested"])
        self.assertIsNone(final.get("artifact_manifest"))
        self.assertIsNone(final.get("validation_report"))
        self.assertEqual(final["issues"], [])
        self.assertEqual({record["stage"]: record["outcome"] for record in final["stages"]}["digitizing"], "cancelled")
        status, _, problem = self.artifacts(job["job_id"])
        self.assertEqual((status, problem["code"]), (409, "ARTIFACTS_UNAVAILABLE"))

    def test_a_cancel_after_the_result_was_saved_does_not_touch_it(self):
        project_id, asset_id, revision_id = self.setup_project(svg())
        _, job, _ = self.create_job(project_id, asset_id, revision_id)
        before = self.wait_job(project_id, job["job_id"], {"needs_review"})
        status, _, answer = self.post(f"/api/v1/jobs/{job['job_id']}/cancel", {})
        self.assertEqual((status, answer["status"], answer["cancellation_requested"]), (202, "needs_review", False))
        _, _, after = self.json_request("GET", f"/api/v1/jobs/{job['job_id']}")
        self.assertEqual(after, before)
        status, _, manifest = self.artifacts(job["job_id"])
        self.assertEqual(status, 200, manifest)

    def test_concurrent_cancellations_never_lose_an_accepted_request_or_revive_a_finished_job(self):
        """Cancelar a distintos instantes del trabajo: la solicitud aceptada se cumple o el trabajo ya había terminado."""
        project_id, asset_id, revision_id = self.setup_project(svg())
        final_states = {"cancelled", "needs_review", "failed"}
        for delay in (0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.3):
            with self.subTest(delay=delay):
                _, job, _ = self.create_job(project_id, asset_id, revision_id)
                time.sleep(delay)
                status, _, answer = self.post(f"/api/v1/jobs/{job['job_id']}/cancel", {})
                self.assertEqual(status, 202)
                final = self.wait_job(project_id, job["job_id"], final_states)
                self.assertEqual(final["status"] == "cancelled", final["cancellation_requested"])  # nunca se contradicen
                if answer["status"] in final_states:  # ya había terminado cuando llegó la cancelación: no se toca
                    self.assertEqual((final["status"], final["cancellation_requested"]), (answer["status"], False))
                else:  # aceptada mientras corría: el resultado no la pisa
                    self.assertEqual(final["status"], "cancelled")
                    self.assertIsNone(final.get("artifact_manifest"))
                    status, _, problem = self.artifacts(job["job_id"])
                    self.assertEqual((status, problem["code"]), (409, "ARTIFACTS_UNAVAILABLE"))

    def variant(self, project_id, parent_id, width=160.0, height=160.0, key=None, kind="size_variant"):
        body = {"schema_version": "0.1", "kind": kind, "parent_job_id": parent_id}
        if kind == "size_variant":
            body["target"] = {"width_mm": width, "height_mm": height, "fit": "contain"}
        else:
            body["corrections"] = [{"action": "exclude_region", "object_id": "shape_1"}]
        return self.post(f"/api/v1/projects/{project_id}/revisions", body, key)

    def test_a_size_variant_is_a_new_revision_and_a_new_job_and_the_origin_does_not_change(self):
        project_id, asset_id, revision_id = self.setup_project(svg())
        _, parent, _ = self.create_job(project_id, asset_id, revision_id)
        before = self.wait_job(project_id, parent["job_id"], {"needs_review"})
        status, _, child = self.variant(project_id, parent["job_id"])
        self.assertEqual(status, 202, child)
        self.assertEqual((child["status"], child["parent_job_id"], child["input_kind"]), ("queued", parent["job_id"], "prepared_svg"))
        self.assertEqual(child["settings_snapshot"]["target"], {"width_mm": 160.0, "height_mm": 160.0, "fit": "contain"})
        rest = lambda settings: {key: value for key, value in settings.items() if key != "target"}  # noqa: E731
        self.assertEqual(rest(child["settings_snapshot"]), rest(before["settings_snapshot"]))  # solo cambia el destino
        self.assertNotEqual(child["revision_id"], parent["revision_id"])
        _, _, revisions = self.json_request("GET", f"/api/v1/projects/{project_id}/revisions")
        linked = next(item for item in revisions["items"] if item["revision_id"] == child["revision_id"])
        self.assertEqual((linked["kind"], linked["base_revision_id"], linked["parent_job_id"], linked["job_id"]),
                         ("size_variant", revision_id, parent["job_id"], child["job_id"]))
        done = self.wait_job(project_id, child["job_id"], {"needs_review"})
        self.assertEqual(done["asset_id"], before["asset_id"])
        status, _, manifest = self.artifacts(child["job_id"])
        self.assertEqual(status, 200, manifest)
        _, _, after = self.json_request("GET", f"/api/v1/jobs/{parent['job_id']}")
        self.assertEqual(after, before)  # el job de origen y su revisión quedan como estaban

    def test_a_size_variant_waits_for_the_origin_and_checks_ownership_and_kind(self):
        project_id, asset_id, revision_id = self.setup_project(svg("FAKE_SLEEP"))
        _, parent, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, parent["job_id"], {"digitizing"})
        status, _, problem = self.variant(project_id, parent["job_id"])
        self.assertEqual((status, problem["code"]), (409, "REVISION_CONFLICT"))  # todavía corre
        self.post(f"/api/v1/jobs/{parent['job_id']}/cancel", {})
        self.wait_job(project_id, parent["job_id"], {"cancelled"})
        status, _, problem = self.variant(project_id, "job_inexistente")
        self.assertEqual((status, problem["code"]), (404, "NOT_FOUND"))
        _, _, other = self.post("/api/v1/projects", {"name": "Otro"})
        status, _, problem = self.variant(other["project_id"], parent["job_id"])
        self.assertEqual((status, problem["code"]), (404, "NOT_FOUND"))  # un job de otro proyecto no se usa
        status, _, problem = self.variant(project_id, parent["job_id"], kind="correction")
        self.assertEqual((status, problem["code"]), (422, "INVALID_REQUEST"))  # las correcciones todavía no se admiten
        status, _, child = self.variant(project_id, parent["job_id"])  # un origen cancelado sí admite variante
        self.assertEqual(status, 202, child)
        self.post(f"/api/v1/jobs/{child['job_id']}/cancel", {})

    def test_a_size_variant_request_is_idempotent(self):
        project_id, asset_id, revision_id = self.setup_project(svg())
        _, parent, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, parent["job_id"], {"needs_review"})
        _, _, first = self.variant(project_id, parent["job_id"], key="misma-clave")
        status, _, again = self.variant(project_id, parent["job_id"], key="misma-clave")
        self.assertEqual((status, again["job_id"]), (202, first["job_id"]))
        status, _, problem = self.variant(project_id, parent["job_id"], 170.0, 170.0, key="misma-clave")
        self.assertEqual((status, problem["code"]), (409, "IDEMPOTENCY_CONFLICT"))
        _, _, revisions = self.json_request("GET", f"/api/v1/projects/{project_id}/revisions")
        self.assertEqual(sum(1 for item in revisions["items"] if item["kind"] == "size_variant"), 1)
        self.wait_job(project_id, first["job_id"], {"needs_review"})

    def job_input(self, job_id):
        """El SVG que recibió el worker de ese job."""
        return (Path(self.tmp.name) / "data" / "jobs" / job_id / "input.svg").read_bytes()

    def test_a_size_variant_of_a_prepared_svg_reaches_the_worker_at_the_new_size_and_the_origin_keeps_its_bytes(self):
        """V1: la variante de un SVG preparado cambia la geometría antes de digitalizar; no solo el destino."""
        original = svg()
        project_id, asset_id, revision_id = self.setup_project(original)
        _, parent, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, parent["job_id"], {"needs_review"})
        parent_input = self.job_input(parent["job_id"])
        self.assertEqual(parent_input, original)  # el original va tal cual
        status, _, child = self.variant(project_id, parent["job_id"], 200.0, 170.0)  # la hoja es cuadrada: manda el alto
        self.assertEqual(status, 202, child)
        self.wait_job(project_id, child["job_id"], {"needs_review"})
        fitted = self.job_input(child["job_id"])
        self.assertIn(b'width="170mm" height="170mm" viewBox="0 0 10 10"', fitted)  # viewBox intacto: el motor escala por él
        self.assertEqual(fitted.replace(b'width="170mm" height="170mm"', b'width="10mm" height="10mm"'), original)  # solo cambió la hoja
        self.assertEqual(self.job_input(parent["job_id"]), parent_input)
        _, _, manifest = self.artifacts(child["job_id"])
        self.assertEqual(manifest["input_sha256"], hashlib.sha256(original).hexdigest())  # lo que subió la persona
        self.assertEqual(manifest["geometry_sha256"], hashlib.sha256(fitted).hexdigest())  # lo que vio el motor
        _, _, parent_manifest = self.artifacts(parent["job_id"])
        self.assertEqual(parent_manifest["input_sha256"], parent_manifest["geometry_sha256"])

    def test_a_size_variant_of_a_prepared_svg_can_also_be_smaller(self):
        project_id, asset_id, revision_id = self.setup_project(svg(root='width="400mm" height="400mm" viewBox="0 0 400 400"'))
        _, parent, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, parent["job_id"], {"needs_review"})
        _, _, child = self.variant(project_id, parent["job_id"], 160.0, 200.0)
        self.wait_job(project_id, child["job_id"], {"needs_review"})
        self.assertIn(b'width="160mm" height="160mm"', self.job_input(child["job_id"]))

    def test_a_size_variant_is_refused_when_the_svg_cannot_change_size(self):
        """Sin viewBox o sin tamaño absoluto el motor no escalaría el dibujo: se dice por qué, y no se crea nada."""
        for root, reason in (
            ('width="10mm" height="10mm"', "viewBox"),
            ('width="100%" height="100%" viewBox="0 0 10 10"', "width"),
            ('viewBox="0 0 10 10"', "width"),
        ):
            with self.subTest(root=root):
                project_id, asset_id, revision_id = self.setup_project(svg(root=root))
                _, parent, _ = self.create_job(project_id, asset_id, revision_id)
                self.wait_job(project_id, parent["job_id"], {"needs_review"})
                status, _, problem = self.variant(project_id, parent["job_id"])
                self.assertEqual((status, problem["code"]), (422, "INVALID_REQUEST"))
                self.assertIn(reason, problem["detail"])
                _, _, revisions = self.json_request("GET", f"/api/v1/projects/{project_id}/revisions")
                self.assertEqual(sum(1 for item in revisions["items"] if item["kind"] == "size_variant"), 0)

    def with_target(self, width, height):
        return {**SETTINGS, "target": {"width_mm": width, "height_mm": height, "fit": "contain"}}

    def test_a_prepared_svg_job_is_digitized_at_its_declared_size_and_the_target_is_only_a_limit(self):
        """B2: el job base no escala el SVG preparado aunque el destino difiera; solo una variante cambia el tamaño."""
        cases = (
            ("destino mayor que la hoja", svg(), self.with_target(160.0, 160.0)),
            ("destino igual a la hoja", svg(root='width="160mm" height="160mm" viewBox="0 0 160 160"'), self.with_target(160.0, 160.0)),
        )
        for label, original, settings in cases:
            with self.subTest(label):
                project_id, asset_id, revision_id = self.setup_project(original, settings)
                status, job, _ = self.create_job(project_id, asset_id, revision_id, settings)
                self.assertEqual(status, 202, job)
                self.assertEqual(job["settings_snapshot"]["target"], settings["target"])  # el destino pedido queda registrado tal cual
                self.wait_job(project_id, job["job_id"], {"needs_review"})
                self.assertEqual(self.job_input(job["job_id"]), original)  # el worker recibió el SVG sin tocar
                _, _, manifest = self.artifacts(job["job_id"])
                digest = hashlib.sha256(original).hexdigest()
                self.assertEqual((manifest["input_sha256"], manifest["geometry_sha256"]), (digest, digest))

    def test_a_prepared_svg_larger_than_the_target_still_fails_with_the_dimensions_issue(self):
        """El destino sigue siendo un límite: lo que no entra se rechaza con motivo, no se achica en silencio."""
        settings = self.with_target(100.0, 100.0)  # el worker de prueba entrega un JEF de 150 × 142,8 mm
        project_id, asset_id, revision_id = self.setup_project(svg(), settings)
        _, job, _ = self.create_job(project_id, asset_id, revision_id, settings)
        failed = self.wait_job(project_id, job["job_id"], {"failed"})
        self.assertIn("DIMENSIONS_EXCEEDED", [issue["code"] for issue in failed["issues"]])
        self.assertEqual(self.job_input(job["job_id"]), svg())

    def test_a_variant_of_a_variant_is_fitted_from_the_original_asset_not_from_the_parents_fitted_svg(self):
        """B3: la cadena base -> A -> B parte siempre del asset que subió la persona."""
        original = svg()
        digest = hashlib.sha256(original).hexdigest()
        project_id, asset_id, revision_id = self.setup_project(original)
        _, base, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, base["job_id"], {"needs_review"})
        with patch.object(api_runner, "fit_to_target", wraps=fit_to_target) as fitted:
            _, _, first = self.variant(project_id, base["job_id"], 200.0, 170.0)
            self.wait_job(project_id, first["job_id"], {"needs_review"})
            status, _, second = self.variant(project_id, first["job_id"], 160.0, 160.0)  # el padre es la variante A
            self.assertEqual(status, 202, second)
            self.wait_job(project_id, second["job_id"], {"needs_review"})
        self.assertEqual([call.args[0] for call in fitted.call_args_list], [original, original])  # ninguna parte del SVG ajustado
        self.assertEqual((second["parent_job_id"], second["asset_id"]), (first["job_id"], base["asset_id"]))
        self.assertEqual(second["settings_snapshot"]["target"], {"width_mm": 160.0, "height_mm": 160.0, "fit": "contain"})
        first_input, second_input = self.job_input(first["job_id"]), self.job_input(second["job_id"])
        self.assertEqual(second_input, fit_to_target(original, 160.0, 160.0)[0])  # igual que ajustar el original de una vez
        self.assertIn(b'width="160mm" height="160mm"', second_input)
        self.assertIn(b'width="170mm" height="170mm"', first_input)
        for job, fitted_input in ((first, first_input), (second, second_input)):
            _, _, manifest = self.artifacts(job["job_id"])
            self.assertEqual(manifest["input_sha256"], digest)  # lo que subió la persona, también en la cadena
            self.assertEqual(manifest["geometry_sha256"], hashlib.sha256(fitted_input).hexdigest())
        self.assertEqual(self.job_input(base["job_id"]), original)  # y el origen sigue igual

    def test_repeating_a_prepared_svg_variant_request_returns_the_same_body_and_does_not_fit_again(self):
        """B3: el replay con la misma clave no crea otra revisión ni vuelve a leer y ajustar el SVG."""
        project_id, asset_id, revision_id = self.setup_project(svg())
        _, base, _ = self.create_job(project_id, asset_id, revision_id)
        self.wait_job(project_id, base["job_id"], {"needs_review"})
        with patch.object(api_app, "fit_to_target", wraps=fit_to_target) as on_request, \
                patch.object(api_runner, "fit_to_target", wraps=fit_to_target) as on_worker:
            status, _, first = self.variant(project_id, base["job_id"], 200.0, 170.0, key="misma-clave-svg")
            self.assertEqual(status, 202, first)
            self.wait_job(project_id, first["job_id"], {"needs_review"})
            self.assertEqual((on_request.call_count, on_worker.call_count), (1, 1))
            status, _, again = self.variant(project_id, base["job_id"], 200.0, 170.0, key="misma-clave-svg")
            self.assertEqual((status, again), (202, first))  # el mismo cuerpo, no solo el mismo job
            self.assertEqual((on_request.call_count, on_worker.call_count), (1, 1))  # no se leyó ni se ajustó de nuevo
        _, _, revisions = self.json_request("GET", f"/api/v1/projects/{project_id}/revisions")
        self.assertEqual(sum(1 for item in revisions["items"] if item["kind"] == "size_variant"), 1)
        self.assertEqual(self.job_input(first["job_id"]), fit_to_target(svg(), 200.0, 170.0)[0])  # el job guardado no se tocó

    def test_job_creation_does_not_wait_for_worker(self):
        project_id, asset_id, revision_id = self.setup_project(svg("FAKE_SLEEP"))
        status, job, elapsed = self.create_job(project_id, asset_id, revision_id)
        self.assertEqual(status, 202)
        self.assertLess(elapsed, 0.5)
        self.assertEqual(job["status"], "queued")
        self.post(f"/api/v1/jobs/{job['job_id']}/cancel", {})
        self.wait_job(project_id, job["job_id"], {"cancelled"})

    def test_authentication_problem_and_no_store(self):
        status, headers, problem = self.json_request("GET", "/api/v1/projects", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(problem["code"], "UNAUTHENTICATED")
        self.assertEqual(problem["status"], 401)
        self.assertEqual(problem["instance"], "/api/v1/projects")
        self.assertEqual(header(headers, "WWW-Authenticate"), "Bearer")
        self.assertEqual(header(headers, "Cache-Control"), "no-store")
        self.assertTrue(header(headers, "X-Request-ID"))
        status, headers, profiles = self.json_request("GET", "/api/v1/profiles")
        self.assertEqual(status, 200)
        self.assertEqual(profiles["machines"][0]["profile_id"], "janome_mc550e")
        self.assertEqual(header(headers, "Cache-Control"), "no-store")
        self.assertTrue(header(headers, "X-Request-ID"))

    def test_project_idempotency(self):
        key = uuid.uuid4().hex
        status, _, first = self.post("/api/v1/projects", {"name": "Idempotent"}, key)
        self.assertEqual(status, 201)
        status, _, replay = self.post("/api/v1/projects", {"name": "Idempotent"}, key)
        self.assertEqual(status, 201)
        self.assertEqual(first["project_id"], replay["project_id"])
        status, _, conflict = self.post("/api/v1/projects", {"name": "Different"}, key)
        self.assertEqual(status, 409)
        self.assertEqual(conflict["code"], "IDEMPOTENCY_CONFLICT")


if __name__ == "__main__":
    unittest.main()
