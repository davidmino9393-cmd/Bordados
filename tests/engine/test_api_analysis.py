"""H2: pipeline de imagen de la API (análisis, decisión, continuación, vectorización y JEF) con proveedores falsos.

No hay red ni IA real, y el worker es el falso (no corre Ink/Stitch): se comprueba el comportamiento del backend.
Una imagen termina en needs_review con el JEF de referencia; sin `raster_digitizing` se queda en la geometría de E1.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

import uvicorn
from PIL import Image, ImageDraw

from embroidery_api.analysis import AnalysisProvider, OllamaProvider, ProviderError, ProviderResult
from embroidery_api.app import create_app
from embroidery_api.config import ApiConfig
from embroidery_api.profiles import load_profiles
from embroidery_contracts import IssueCode
from vectorize.inkstitch import REFERENCE_ADAPTER, REFERENCE_PULL_COMPENSATION_MM

TOKEN = "test-token"
SETTINGS = json.loads((ROOT / "packages" / "contracts" / "fixtures" / "generation-from-svg.json").read_text(encoding="utf-8"))["payload"]["settings"]
FAKE_WORKER = ROOT / "tests" / "engine" / "fixtures" / "fake_worker.py"
INSIDE = {"x_px": 5, "y_px": 5, "width_px": 40, "height_px": 20, "visual_role": "Texto", "observed_text": "LOGO", "suggested_colors": ["#1F3A93"], "uncertainties": []}
OUTSIDE = dict(INSIDE, x_px=60, width_px=40, visual_role="Zona dudosa")


def png(width=80, height=60, shape=False):
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), "white")
    if shape:  # un anillo oscuro: una forma con un hueco, para que E1 tenga qué vectorizar
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 5, width - 10, height - 5), fill="#1F3A93")
        draw.ellipse((25, 18, width - 25, height - 18), fill="white")
    image.save(buffer, "PNG")
    return buffer.getvalue()


class FakeProvider(AnalysisProvider):
    def __init__(self, provider_id, regions=(INSIDE,), error=None):
        self.provider_id, self.model = provider_id, f"fake-{provider_id}"
        self.regions, self.error, self.calls = list(regions), error, 0

    def analyze(self, image, media_type, width_px, height_px, cancel=None):
        self.calls += 1
        if self.error:
            raise self.error
        return ProviderResult(regions=copy.deepcopy(self.regions), model=self.model, raw={"fake": True}, duration_ms=9)


class AnalysisApiTests(unittest.TestCase):
    providers = None
    raster_digitizing = True  # con el worker falso: se prueba el cableado, no la calidad de las puntadas

    def start(self, providers):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = ApiConfig(
            data_root=Path(self.tmp.name) / "data", profiles_path=ROOT / "services" / "api" / "profiles.json",
            python_executable=Path(sys.executable), inkstitch_executable=Path(sys.executable), engine_version="fake",
            signing_key="s" * 32, public_base_url="http://testserver", service_token=TOKEN,
            max_workers=1, max_queued_jobs=8, timeout_s=20, worker_script=FAKE_WORKER,
            raster_digitizing=self.raster_digitizing,
        )
        server = uvicorn.Server(uvicorn.Config(create_app(config, analysis_providers=providers), host="127.0.0.1", port=0, log_level="critical"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.time() + 10
        while not server.started and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(server.started, "uvicorn did not start")
        self.base = f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"

        def stop():
            server.should_exit = True
            thread.join(10)

        self.addCleanup(stop)  # se ejecuta antes que el borrado del directorio temporal (LIFO)

    def call(self, method, path, body=None, key=None, raw=None, content_type=None):
        headers = {"Authorization": f"Bearer {TOKEN}"}
        data = raw
        if body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        if method == "POST":
            headers["Idempotency-Key"] = key or uuid.uuid4().hex
        request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read() or b"null")
            finally:
                exc.close()

    def upload(self, project_id, content, filename="logo.png", mime="image/png", purpose=None):
        boundary = "----h2" + uuid.uuid4().hex
        field = f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'.encode() if purpose else b""
        body = field + (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode() + content + f"\r\n--{boundary}--\r\n".encode()
        return self.call("POST", f"/api/v1/projects/{project_id}/assets", raw=body, content_type=f"multipart/form-data; boundary={boundary}")

    def settings(self, provider="openai"):
        return dict(copy.deepcopy(SETTINGS), ai_provider=provider)

    def raster_job(self, provider="openai", image=None, settings=None):
        """Crea proyecto, imagen, revisión inicial y job de imagen; devuelve (project_id, job)."""
        _, project = self.call("POST", "/api/v1/projects", {"name": "H2"})
        pid = project["project_id"]
        status, asset = self.upload(pid, image or png())
        self.assertEqual(status, 201, asset)
        settings = settings or self.settings(provider)
        status, revision = self.call("POST", f"/api/v1/projects/{pid}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "inicial", "settings": settings, "document": None})
        self.assertEqual(status, 201, revision)
        status, job = self.call("POST", f"/api/v1/projects/{pid}/jobs", {"schema_version": "0.1", "asset_id": asset["asset_id"], "revision_id": revision["revision_id"], "input_kind": "raster_image", "settings": settings})
        self.assertEqual(status, 202, job)
        return pid, job

    def wait(self, job_id, statuses=("needs_review", "failed", "cancelled", "ready_for_sewout"), timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status, job = self.call("GET", f"/api/v1/jobs/{job_id}")
            if status == 200 and job["status"] in statuses:
                return job
            time.sleep(0.03)
        self.fail(f"job {job_id} no llegó a {statuses}")

    def stages(self, job):
        return {record["stage"]: record["outcome"] for record in job["stages"]}


class CatalogAndCreationTests(AnalysisApiTests):
    def test_catalog_lists_only_configured_providers_with_a_reason_for_the_rest(self):
        self.start({"openai": FakeProvider("openai")})
        _, catalog = self.call("GET", "/api/v1/profiles")
        by_id = {p["provider_id"]: p for p in catalog["providers"]}
        self.assertTrue(by_id["openai"]["available"])
        self.assertFalse(by_id["ollama"]["available"])
        self.assertTrue(by_id["ollama"]["unavailable_reason"])

    def test_without_configured_providers_an_image_job_is_rejected(self):
        self.start({})
        _, catalog = self.call("GET", "/api/v1/profiles")
        self.assertFalse(any(p["available"] for p in catalog["providers"]))
        _, project = self.call("POST", "/api/v1/projects", {"name": "H2"})
        status, body = self.call("POST", f"/api/v1/projects/{project['project_id']}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "r", "settings": self.settings(), "document": None})
        self.assertEqual((status, body["code"]), (422, "INVALID_REQUEST"))

    def test_an_svg_cannot_be_submitted_as_a_raster_image_nor_the_reverse(self):
        self.start({"openai": FakeProvider("openai")})
        _, project = self.call("POST", "/api/v1/projects", {"name": "H2"})
        pid = project["project_id"]
        _, svg = self.upload(pid, b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><path id="a" d="M0 0L1 1"/></svg>', "a.svg", "image/svg+xml")
        _, image = self.upload(pid, png())
        _, revision = self.call("POST", f"/api/v1/projects/{pid}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "r", "settings": self.settings(), "document": None})
        for asset, kind in ((svg, "raster_image"), (image, "prepared_svg")):
            with self.subTest(kind=kind):
                status, body = self.call("POST", f"/api/v1/projects/{pid}/jobs", {"schema_version": "0.1", "asset_id": asset["asset_id"], "revision_id": revision["revision_id"], "input_kind": kind, "settings": self.settings(None if kind == "prepared_svg" else "openai") if kind == "raster_image" else dict(SETTINGS)})
                self.assertIn(status, (409, 422), body)


class AnalysisFlowTests(AnalysisApiTests):
    def test_incoherent_box_pauses_in_needs_review_with_a_localized_issue(self):
        provider = FakeProvider("openai", [INSIDE, OUTSIDE])
        self.start({"openai": provider})
        _, job = self.raster_job()
        self.assertEqual((job["status"], self.stages(job)["analyzing"]), ("queued", "pending"))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "needs_review")
        self.assertEqual(self.stages(done), {"analyzing": "completed", "vectorizing": "pending", "digitizing": "pending", "validating": "pending"})
        issue = done["issues"][0]
        self.assertEqual((issue["code"], issue["severity"], issue["stage"], issue["region_ids"]), ("ANALYSIS_REGION_INCOHERENT", "review_required", "analysis", ["region_2"]))
        self.assertEqual(done["review"]["region_ids"], ["region_2"])
        self.assertEqual(provider.calls, 1)
        status, body = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        self.assertEqual((status, body["code"]), (409, "ARTIFACTS_UNAVAILABLE"))
        status, analysis = self.call("GET", f"/api/v1/jobs/{job['job_id']}/analysis")
        self.assertEqual(status, 200)
        self.assertEqual([r["region_id"] for r in analysis["regions"]], ["region_1", "region_2"])
        self.assertEqual((analysis["provider"], analysis["asset_id"]), ("openai", done["asset_id"]))

    def test_a_clean_analysis_does_not_pause_and_ends_in_needs_review_with_the_jef_and_the_reference_notice(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job(image=png(shape=True))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "needs_review")  # ready_for_sewout exige comprobaciones que no existen
        self.assertEqual(self.stages(done), {"analyzing": "completed", "vectorizing": "completed", "digitizing": "completed", "validating": "completed"})
        issue = next(i for i in done["issues"] if i["code"] == "DENSITY_REVIEW_REQUIRED")
        self.assertEqual((issue["severity"], issue["stage"]), ("review_required", "routing"))
        self.assertTrue(issue["object_ids"])
        self.assertIs(issue["evidence"]["parameters_calibrated"], False)
        self.assertEqual(issue["evidence"]["parameter_source"], "gabardina_400ppm_referencia")
        self.assertIn("referencia", issue["description"])
        self.assertNotEqual(done["status"], "ready_for_sewout")
        status, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        self.assertEqual(status, 200, manifest)
        kinds = {a["kind"] for a in manifest["artifacts"]}
        self.assertTrue({"jef", "preview_png", "inkstitch_svg", "editable_svg", "validation_json"} <= kinds, kinds)
        self.assertIsNotNone(manifest["reread_metrics"])
        self.assertIs(manifest["provenance"]["simulated"], False)
        for kind in ("jef", "inkstitch_svg"):
            artifact = next(a for a in manifest["artifacts"] if a["kind"] == kind)
            request = urllib.request.Request(self.base + urllib.parse.urlsplit(artifact["download"]["url"]).path, method="GET")
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = response.read()
            self.assertEqual((len(payload), hashlib.sha256(payload).hexdigest()), (artifact["byte_size"], artifact["sha256"]))
        self.assertIn(b"<svg", payload[:400])
        self.assertIn(REFERENCE_ADAPTER.encode(), payload)  # el SVG que se bordó es el de referencia, no la entrada cruda

    def test_the_worker_receives_the_reference_svg_made_from_the_vectorized_geometry(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job(image=png(shape=True))
        done = self.wait(job["job_id"])
        _, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        artifact = next(a for a in manifest["artifacts"] if a["kind"] == "inkstitch_svg")
        request = urllib.request.Request(self.base + urllib.parse.urlsplit(artifact["download"]["url"]).path, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            svg = response.read().decode("utf-8")
        object_ids = {object_id for issue in done["issues"] for object_id in issue["object_ids"]}
        self.assertTrue(object_ids)
        self.assertTrue(all(f'id="{object_id}"' in svg for object_id in object_ids if object_id.startswith("mask_")))
        self.assertIn("inkstitch:row_spacing_mm", svg)

    def test_an_empty_image_fails_with_the_original_vectorization_diagnostic_kept(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job()
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "failed")
        self.assertEqual(self.stages(done), {"analyzing": "completed", "vectorizing": "failed", "digitizing": "pending", "validating": "pending"})
        self.assertEqual(done["failure"]["stage"], "vectorizing")
        evidence = done["issues"][0]["evidence"]
        self.assertEqual((evidence["reason"], evidence["original_code"]), ("vectorization_review_unlocalized", "GEOMETRY_INVALID"))
        self.assertEqual(evidence["original_evidence"]["reason"], "empty_foreground")

    def test_the_uploaded_original_has_a_signed_download_that_serves_the_same_bytes(self):
        self.start({"openai": FakeProvider("openai")})
        _, project = self.call("POST", "/api/v1/projects", {"name": "Original"})
        pid = project["project_id"]
        image = png(shape=True)
        status, asset = self.upload(pid, image)
        self.assertEqual(status, 201)
        _, detail = self.call("GET", f"/api/v1/projects/{pid}")
        for source in (asset, detail["assets"][0]):
            download = source["original_download"]
            self.assertIsNotNone(download)
            request = urllib.request.Request(self.base + urllib.parse.urlsplit(download["url"]).path, method="GET")
            with urllib.request.urlopen(request, timeout=15) as response:
                self.assertEqual((response.read(), response.headers["Content-Type"]), (image, "image/png"))
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        # Un enlace de otro tipo de archivo no sirve para pedir un original ajeno.
        tampered = self.base + urllib.parse.urlsplit(asset["original_download"]["url"]).path[:-3] + "xyz"
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(urllib.request.Request(tampered), timeout=15)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()

    def test_sewout_photos_are_assets_with_their_own_purpose_that_never_become_designs(self):
        self.start({"openai": FakeProvider("openai")})
        _, project = self.call("POST", "/api/v1/projects", {"name": "Fotos"})
        pid = project["project_id"]
        _, design = self.upload(pid, png(shape=True), "logo.png")
        status, photo = self.upload(pid, png(), "muestra.png", purpose="sewout_photo")
        self.assertEqual((status, design["purpose"], photo["purpose"]), (201, "design", "sewout_photo"))
        self.assertEqual({a["purpose"] for a in self.call("GET", f"/api/v1/projects/{pid}")[1]["assets"]}, {"design", "sewout_photo"})
        self.assertEqual(self.upload(pid, png(), "x.png", purpose="otra")[0], 422)
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><path id="a" d="M0 0L1 1"/></svg>'
        self.assertEqual(self.upload(pid, svg, "a.svg", "image/svg+xml", purpose="sewout_photo")[0], 422)
        _, revision = self.call("POST", f"/api/v1/projects/{pid}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "r", "settings": self.settings(), "document": None})
        job_body = {"schema_version": "0.1", "asset_id": photo["asset_id"], "revision_id": revision["revision_id"], "input_kind": "raster_image", "settings": self.settings()}
        self.assertEqual(self.call("POST", f"/api/v1/projects/{pid}/jobs", job_body)[0], 422)
        sewout = {"schema_version": "0.1", "revision_id": revision["revision_id"], "status": "untested", "tested_at": None, "fabric_profile": "gabardina_inicial",
                  "stabilizer": "entretela", "thread": "poliester", "observations": "sin probar"}
        self.assertEqual(self.call("POST", f"/api/v1/projects/{pid}/sewouts", dict(sewout, photo_asset_ids=[design["asset_id"]]))[0], 422)
        status, recorded = self.call("POST", f"/api/v1/projects/{pid}/sewouts", dict(sewout, photo_asset_ids=[photo["asset_id"]]))
        self.assertEqual((status, recorded["photo_asset_ids"]), (201, [photo["asset_id"]]))

    def test_the_local_model_is_probed_live_in_the_profile_catalogue(self):
        def tags(url, timeout):
            return 200, json.dumps({"models": [{"name": "qwen2.5vl:7b"}]}).encode()

        def down(url, timeout):
            raise urllib.error.URLError("rechazada")

        for fetch, available in ((tags, True), (down, False)):
            with self.subTest(available=available):
                self.start({"ollama": OllamaProvider("qwen2.5vl:7b", fetch=fetch)})
                _, catalogue = self.call("GET", "/api/v1/profiles")
                by_id = {item["provider_id"]: item for item in catalogue["providers"]}
                self.assertEqual(by_id["ollama"]["available"], available)
                self.assertEqual(by_id["ollama"]["unavailable_reason"] is None, available)
                self.assertFalse(by_id["openai"]["available"])

    def test_a_job_runs_end_to_end_with_the_ollama_adapter_and_never_falls_back(self):
        def chat(url, headers, body, timeout):
            self.assertTrue(url.endswith("/api/chat"))
            reply = {"model": "qwen2.5vl:7b", "done": True, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 3,
                     "message": {"role": "assistant", "content": json.dumps({"regions": [dict(INSIDE)]})}}
            return 200, json.dumps(reply).encode()

        self.start({"ollama": OllamaProvider("qwen2.5vl:7b", transport=chat)})
        _, job = self.raster_job("ollama", image=png(shape=True))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "needs_review")  # E1 vectorizó; sin H3 no hay puntadas
        self.assertEqual(done["settings_snapshot"]["ai_provider"], "ollama")
        _, analysis = self.call("GET", f"/api/v1/jobs/{job['job_id']}/analysis")
        self.assertEqual((analysis["provider"], analysis["model"]), ("ollama", "qwen2.5vl:7b"))

    def test_a_down_local_model_fails_the_job_with_its_own_code_and_does_not_use_openai(self):
        def refuse(url, headers, body, timeout):
            raise urllib.error.URLError("rechazada")

        openai = FakeProvider("openai", [INSIDE])
        self.start({"ollama": OllamaProvider("qwen2.5vl:7b", transport=refuse), "openai": openai})
        _, job = self.raster_job("ollama", image=png(shape=True))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "failed")
        self.assertEqual((done["failure"]["code"], done["failure"]["stage"]), ("LOCAL_MODEL_UNAVAILABLE", "analyzing"))
        self.assertEqual(openai.calls, 0)

    def test_provider_failures_end_the_job_with_the_catalogue_code(self):
        for code in (IssueCode.ANALYSIS_REFUSED, IssueCode.PROVIDER_RATE_LIMITED, IssueCode.ANALYSIS_SCHEMA_INVALID):
            with self.subTest(code=code):
                self.start({"openai": FakeProvider("openai", error=ProviderError(code, "detail"))})
                _, job = self.raster_job()
                done = self.wait(job["job_id"])
                self.assertEqual(done["status"], "failed")
                self.assertEqual(done["failure"], {"code": code.value, "message": done["failure"]["message"], "stage": "analyzing"})
                self.assertEqual(self.stages(done)["analyzing"], "failed")
                self.assertEqual(self.stages(done)["vectorizing"], "pending")

    def test_prepared_svg_and_unknown_jobs_have_no_analysis(self):
        self.start({"openai": FakeProvider("openai")})
        self.assertEqual(self.call("GET", "/api/v1/jobs/job_inexistente/analysis")[0], 404)
        _, project = self.call("POST", "/api/v1/projects", {"name": "SVG"})
        pid = project["project_id"]
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><path id="a" d="M0 0L1 1"/></svg>'
        _, asset = self.upload(pid, svg, "a.svg", "image/svg+xml")
        _, revision = self.call("POST", f"/api/v1/projects/{pid}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "r", "settings": SETTINGS, "document": None})
        status, job = self.call("POST", f"/api/v1/projects/{pid}/jobs", {"schema_version": "0.1", "asset_id": asset["asset_id"], "revision_id": revision["revision_id"], "input_kind": "prepared_svg", "settings": SETTINGS})
        self.assertEqual(status, 202, job)
        status, body = self.call("GET", f"/api/v1/jobs/{job['job_id']}/analysis")
        self.assertEqual((status, body["code"]), (404, "NOT_FOUND"))
        self.wait(job["job_id"])


def layers_png(colours, width=120, height=60):
    """Un rectángulo por color sobre fondo blanco."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    step = width // len(colours)
    for index, colour in enumerate(colours):
        draw.rectangle((index * step + 5, 5, (index + 1) * step - 5, height - 5), fill=colour)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


NEAR_WHITE = (243, 241, 240)
DARK_BLUE, DARK_RED = (10, 20, 90), (90, 10, 20)


class JefFromImageTests(AnalysisApiTests):
    """Una imagen llega a un JEF sin pasar por la IA, y lo que no se puede bordar se avisa."""

    def run_without_ai(self, image, **changes):
        self.start({})
        _, job = self.raster_job("none", image=image, settings=dict(self.settings("none"), **changes))
        return job, self.wait(job["job_id"])

    def artifact(self, job, kind):
        _, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        item = next(a for a in manifest["artifacts"] if a["kind"] == kind)
        request = urllib.request.Request(self.base + urllib.parse.urlsplit(item["download"]["url"]).path, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()

    @staticmethod
    def x_extent(svg):
        xs = [float(x) for x in re.findall(r"[ML](-?[\d.]+),-?[\d.]+", svg)]
        return max(xs) - min(xs)

    def test_the_manifest_keeps_the_uploaded_image_apart_from_the_intermediate_svg(self):
        """R2: input_sha256 es el PNG que subió la persona; geometry_sha256, el SVG intermedio que recibió el worker."""
        image = png(shape=True)
        job, _ = self.run_without_ai(image)
        _, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        svg = self.artifact(job, "inkstitch_svg")
        self.assertEqual(manifest["input_sha256"], hashlib.sha256(image).hexdigest())
        self.assertEqual(manifest["geometry_sha256"], hashlib.sha256(svg).hexdigest())
        editable = self.artifact(job, "editable_svg")
        self.assertNotEqual(editable, svg)
        drawing = next(a for a in manifest["artifacts"] if a["kind"] == "editable_svg")
        self.assertEqual(drawing["sha256"], hashlib.sha256(editable).hexdigest())
        self.assertNotEqual(manifest["input_sha256"], manifest["geometry_sha256"])

    def test_an_image_without_ai_analysis_goes_straight_to_vectorizing_and_the_jef(self):
        job, done = self.run_without_ai(png(shape=True))
        analyzing = next(r for r in done["stages"] if r["stage"] == "analyzing")
        self.assertEqual((analyzing["outcome"], analyzing["reason"]), ("skipped", "Sin análisis de IA: la persona eligió continuar sin él"))
        self.assertEqual(done["status"], "needs_review")
        self.assertEqual(self.stages(done), {"analyzing": "skipped", "vectorizing": "completed", "digitizing": "completed", "validating": "completed"})
        status, body = self.call("GET", f"/api/v1/jobs/{job['job_id']}/analysis")
        self.assertEqual((status, body["code"]), (404, "NOT_FOUND"))
        self.assertTrue(self.artifact(job, "jef"))
        _, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        jef = next(a for a in manifest["artifacts"] if a["kind"] == "jef")
        self.assertEqual(jef["filename"], "logo.jef")  # se llama como la imagen que se subió, no «output.jef»
        request = urllib.request.Request(self.base + urllib.parse.urlsplit(jef["download"]["url"]).path, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            self.assertIn("logo.jef", response.headers["Content-Disposition"])

    def test_nothing_to_stitch_pauses_for_review_without_a_jef(self):
        job, done = self.run_without_ai(layers_png([NEAR_WHITE]))
        self.assertEqual(done["status"], "needs_review")
        self.assertEqual(self.stages(done), {"analyzing": "skipped", "vectorizing": "completed", "digitizing": "skipped", "validating": "skipped"})
        issue = done["issues"][0]
        self.assertEqual((issue["code"], issue["severity"]), ("GEOMETRY_INVALID", "review_required"))
        self.assertTrue(issue["object_ids"])
        status, body = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        self.assertEqual((status, body["code"]), (409, "ARTIFACTS_UNAVAILABLE"))

    def test_a_near_white_layer_does_not_use_up_a_thread_and_the_omission_is_reported(self):
        job, done = self.run_without_ai(layers_png([DARK_BLUE, DARK_RED, NEAR_WHITE]), color_limit=2)
        svg = self.artifact(job, "inkstitch_svg").decode("utf-8")
        self.assertEqual(svg.count("<path"), 2)  # dos hilos: la capa casi blanca no cuenta
        removed = next(i for i in done["issues"] if i["code"] == "VISUAL_MISMATCH")
        self.assertEqual(removed["severity"], "review_required")
        self.assertTrue(removed["object_ids"])
        omitted = [o for o in removed["evidence"]["stitchable"]["objects"].values() if o["omitted"]]
        self.assertEqual([o["omitted"] for o in omitted], ["near_white_layer_taken_as_background"])

    def test_a_size_variant_of_an_image_regenerates_from_the_original_at_the_new_size_without_ai(self):
        job, done = self.run_without_ai(png(shape=True))
        status, variant = self.call("POST", f"/api/v1/projects/{done['project_id']}/revisions", {
            "schema_version": "0.1", "kind": "size_variant", "parent_job_id": job["job_id"],
            "target": {"width_mm": 160.0, "height_mm": 160.0, "fit": "contain"}})  # el worker falso devuelve 150 x 142,8 mm: no cabe en uno menor
        self.assertEqual(status, 202, variant)
        self.assertEqual((variant["input_kind"], variant["parent_job_id"], variant["asset_id"]), ("raster_image", job["job_id"], done["asset_id"]))
        analyzing = next(r for r in variant["stages"] if r["stage"] == "analyzing")
        self.assertEqual((analyzing["outcome"], analyzing["reason"]), ("skipped", "Sin análisis de IA: la persona eligió continuar sin él"))
        final = self.wait(variant["job_id"])
        self.assertEqual(final["status"], "needs_review")
        self.assertEqual(self.stages(final), {"analyzing": "skipped", "vectorizing": "completed", "digitizing": "completed", "validating": "completed"})
        self.assertEqual(final["settings_snapshot"]["target"], {"width_mm": 160.0, "height_mm": 160.0, "fit": "contain"})
        self.assertTrue(self.artifact(variant, "jef"))
        # Se vuelve a generar desde los píxeles: el SVG de la variante crece en la proporción de los destinos (149,6 -> 159,6).
        extent = lambda item: self.x_extent(self.artifact(item, "inkstitch_svg").decode("utf-8").split("<path", 1)[1])  # noqa: E731
        self.assertAlmostEqual(extent(variant) / extent(job), 159.6 / 149.6, delta=0.01)
        self.assertEqual(self.call("GET", f"/api/v1/jobs/{job['job_id']}")[1]["status"], "needs_review")  # el origen no cambió

    def test_the_vectorized_size_leaves_room_for_the_pull_compensation(self):
        job, _ = self.run_without_ai(Image_bytes((80, 60), DARK_BLUE))
        extent = self.x_extent(self.artifact(job, "inkstitch_svg").decode("utf-8").split("<path", 1)[1])
        # El destino pedido es 150 mm; el runner descuenta la compensación de ambos lados.
        self.assertAlmostEqual(extent, 150.0 - 2 * REFERENCE_PULL_COMPENSATION_MM, delta=0.02)

    def test_oversized_variant_preserves_geometry_and_offers_only_hoop_blocked_jef_for_inspection(self):
        # El JEF de la fixture mide 150 × 142,8 mm. Un aro de 140 mm lo bloquea realmente.
        catalog_path = ROOT / "services" / "api" / "profiles.json"
        catalog = load_profiles(catalog_path)
        hoop = next(item for item in catalog.hoops if item.profile_id == SETTINGS["hoop_profile"])
        narrow = hoop.model_copy(update={"width_mm": 140.0, "height_mm": 200.0})
        catalog = catalog.model_copy(update={"hoops": (narrow,)})
        with patch("embroidery_api.app.load_profiles", return_value=catalog):
            self.start({})
        settings = self.settings("none")
        settings["hoop"].update(width_mm=140.0, height_mm=200.0)
        settings["target"].update(width_mm=140.0, height_mm=160.0)
        project, parent = self.raster_job("none", image=Image_bytes((80, 60), DARK_BLUE), settings=settings)
        self.assertEqual(self.wait(parent["job_id"])["status"], "failed")

        for height, expected in ((360.0, "needs_review"), (100.0, "failed")):
            with self.subTest(height=height):
                target = {"width_mm": 280.0, "height_mm": height, "fit": "contain"}
                status, child = self.call("POST", f"/api/v1/projects/{project}/revisions", {
                    "schema_version": "0.1", "kind": "size_variant", "parent_job_id": parent["job_id"], "target": target,
                })
                self.assertEqual(status, 202, child)
                done = self.wait(child["job_id"])
                self.assertEqual(done["status"], expected)
                blocks = {i["code"] for i in done["issues"] if i["severity"] == "blocking_error"}
                if expected == "needs_review":
                    self.assertEqual(blocks, {"HOOP_INCOMPATIBLE"})
                    self.assertTrue(done["review"]["object_ids"])
                    self.assertFalse(done["validation_report"]["digital_checks_passed"])
                    self.assertTrue(self.artifact(child, "jef"))
                    svg = self.artifact(child, "inkstitch_svg").decode("utf-8")
                    self.assertAlmostEqual(self.x_extent(svg.split("<path", 1)[1]),
                                           280.0 - 2 * REFERENCE_PULL_COMPENSATION_MM, delta=0.2)
                else:
                    self.assertEqual(blocks, {"HOOP_INCOMPATIBLE", "DIMENSIONS_EXCEEDED"})
                    self.assertEqual(self.call("GET", f"/api/v1/jobs/{child['job_id']}/artifacts")[0], 409)


def Image_bytes(size, colour):
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, "PNG")
    return buffer.getvalue()


class GeometryOnlyTests(AnalysisApiTests):
    """Con `raster_digitizing` apagado el trabajo se queda en la geometría de E1: sin JEF ni relectura."""

    raster_digitizing = False

    def test_the_job_stops_at_the_vectorized_geometry_without_digitizing(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job(image=png(shape=True))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "needs_review")
        stages = self.stages(done)
        self.assertEqual((stages["analyzing"], stages["vectorizing"]), ("completed", "completed"))
        self.assertEqual((stages["digitizing"], stages["validating"]), ("skipped", "skipped"))
        issue = next(i for i in done["issues"] if i["code"] == "DENSITY_REVIEW_REQUIRED")
        self.assertEqual((issue["severity"], issue["stage"]), ("review_required", "routing"))
        self.assertIn("provisionales", issue["description"])
        status, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        self.assertEqual(status, 200, manifest)
        self.assertIsNone(manifest["reread_metrics"])  # sin JEF no hay relectura
        self.assertEqual([a["kind"] for a in manifest["artifacts"]], ["editable_svg"])
        self.assertEqual((manifest["provenance"]["simulated"], manifest["provenance"]["method"]), (False, "e1_raster_mask_vectorization"))


class DecisionTests(AnalysisApiTests):
    def review(self, providers=None, regions=(INSIDE, OUTSIDE), provider="openai"):
        self.start(providers or {"openai": FakeProvider("openai", regions), "ollama": FakeProvider("ollama", regions)})
        pid, job = self.raster_job(provider, image=png(shape=True))
        return pid, self.wait(job["job_id"])

    def decide(self, job_id, body, key=None):
        return self.call("POST", f"/api/v1/jobs/{job_id}/analysis-decision", body, key=key)

    def test_approve_creates_a_child_job_on_the_same_revision_and_leaves_the_original_untouched(self):
        pid, original = self.review()
        status, child = self.decide(original["job_id"], {"action": "approve", "flagged_region_ids": ["region_2"]})
        self.assertEqual(status, 202, child)
        self.assertEqual((child["status"], child["parent_job_id"]), ("queued", original["job_id"]))
        self.assertEqual((child["revision_id"], child["asset_id"]), (original["revision_id"], original["asset_id"]))
        analyzing = next(r for r in child["stages"] if r["stage"] == "analyzing")
        self.assertEqual((analyzing["outcome"], analyzing["reason"]), ("skipped", f"análisis aprobado en {original['job_id']}"))
        done = self.wait(child["job_id"])
        self.assertEqual(done["status"], "needs_review")  # E1 vectoriza y se genera el JEF de referencia
        self.assertEqual((self.stages(done)["vectorizing"], self.stages(done)["digitizing"]), ("completed", "completed"))
        self.assertIn("DENSITY_REVIEW_REQUIRED", [i["code"] for i in done["issues"]])
        self.assertEqual(self.call("GET", f"/api/v1/jobs/{child['job_id']}/analysis")[1]["analysis_id"], f"analysis_{original['job_id']}")
        self.assertEqual(self.call("GET", f"/api/v1/jobs/{original['job_id']}")[1]["status"], "needs_review")

    def test_approve_rejects_regions_that_are_not_part_of_the_analysis(self):
        _, original = self.review()
        status, body = self.decide(original["job_id"], {"action": "approve", "flagged_region_ids": ["region_99"]})
        self.assertEqual((status, body["code"]), (422, "INVALID_REQUEST"))

    def test_change_provider_creates_an_analysis_retry_revision_and_a_new_job(self):
        pid, original = self.review()
        status, child = self.decide(original["job_id"], {"action": "change_provider", "ai_provider": "ollama"})
        self.assertEqual(status, 202, child)
        self.assertEqual(child["settings_snapshot"]["ai_provider"], "ollama")
        self.assertNotEqual(child["revision_id"], original["revision_id"])
        self.assertEqual(child["parent_job_id"], original["job_id"])
        self.assertEqual(self.stages(child)["analyzing"], "pending")
        _, history = self.call("GET", f"/api/v1/projects/{pid}/revisions")
        retry = next(r for r in history["items"] if r["kind"] == "analysis_retry")
        self.assertEqual((retry["base_revision_id"], retry["parent_job_id"], retry["job_id"]), (original["revision_id"], original["job_id"], child["job_id"]))
        self.assertEqual(self.wait(child["job_id"])["status"], "needs_review")

    def test_change_provider_rejects_the_same_or_an_unavailable_provider(self):
        _, original = self.review({"openai": FakeProvider("openai", [INSIDE, OUTSIDE])})
        for provider in ("openai", "ollama"):
            with self.subTest(provider=provider):
                status, body = self.decide(original["job_id"], {"action": "change_provider", "ai_provider": provider})
                self.assertEqual((status, body["code"]), (422, "INVALID_REQUEST"))

    def test_only_a_job_waiting_for_an_analysis_decision_accepts_one(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job()
        failed = self.wait(job["job_id"])
        status, body = self.decide(failed["job_id"], {"action": "approve", "flagged_region_ids": []})
        self.assertEqual((status, body["code"]), (409, "REVISION_CONFLICT"))
        self.assertEqual(self.decide("job_inexistente", {"action": "approve"})[0], 404)

    def test_the_client_cannot_inject_state_or_unknown_fields(self):
        _, original = self.review()
        for bad in ({"action": "approve", "status": "ready_for_sewout"}, {"action": "change_provider", "ai_provider": "none"}, {"action": "borrar"}):
            with self.subTest(bad=bad):
                self.assertEqual(self.decide(original["job_id"], bad)[0], 422)

    def test_idempotency_replays_the_same_job_and_rejects_other_content(self):
        _, original = self.review()
        body = {"action": "approve", "flagged_region_ids": []}
        first = self.decide(original["job_id"], body, key="decision-1")
        again = self.decide(original["job_id"], body, key="decision-1")
        self.assertEqual((first[0], again[0], first[1]["job_id"]), (202, 202, again[1]["job_id"]))
        status, conflict = self.decide(original["job_id"], {"action": "change_provider", "ai_provider": "ollama"}, key="decision-1")
        self.assertEqual((status, conflict["code"]), (409, "IDEMPOTENCY_CONFLICT"))


if __name__ == "__main__":
    unittest.main()
