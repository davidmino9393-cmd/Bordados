"""H2: pipeline de imagen de la API (análisis, decisión, continuación) con proveedores falsos inyectados.

No hay red ni IA real: se comprueba el comportamiento del backend. La vectorización todavía no existe, así que
todo job de imagen que sigue adelante termina en un fallo controlado y honesto.
"""
import copy
import hashlib
import io
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
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

import uvicorn
from PIL import Image, ImageDraw

from embroidery_api.analysis import AnalysisProvider, ProviderError, ProviderResult
from embroidery_api.app import create_app
from embroidery_api.config import ApiConfig
from embroidery_contracts import IssueCode

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

    def start(self, providers):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = ApiConfig(
            data_root=Path(self.tmp.name) / "data", profiles_path=ROOT / "services" / "api" / "profiles.json",
            python_executable=Path(sys.executable), inkstitch_executable=Path(sys.executable), engine_version="fake",
            signing_key="s" * 32, public_base_url="http://testserver", service_token=TOKEN,
            max_workers=1, max_queued_jobs=8, timeout_s=20, worker_script=FAKE_WORKER,
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

    def test_a_clean_analysis_does_not_pause_and_vectorizes_into_needs_review_without_digitizing(self):
        self.start({"openai": FakeProvider("openai", [INSIDE])})
        _, job = self.raster_job(image=png(shape=True))
        done = self.wait(job["job_id"])
        self.assertEqual(done["status"], "needs_review")
        stages = self.stages(done)
        self.assertEqual((stages["analyzing"], stages["vectorizing"]), ("completed", "completed"))
        self.assertEqual((stages["digitizing"], stages["validating"]), ("skipped", "skipped"))
        issue = next(i for i in done["issues"] if i["code"] == "DENSITY_REVIEW_REQUIRED")
        self.assertEqual((issue["severity"], issue["stage"]), ("review_required", "routing"))
        self.assertTrue(issue["object_ids"])
        self.assertNotEqual(done["status"], "ready_for_sewout")
        status, manifest = self.call("GET", f"/api/v1/jobs/{job['job_id']}/artifacts")
        self.assertEqual(status, 200, manifest)
        self.assertIsNone(manifest["reread_metrics"])  # sin JEF no hay relectura
        self.assertEqual([a["kind"] for a in manifest["artifacts"]], ["editable_svg"])
        self.assertEqual((manifest["provenance"]["simulated"], manifest["provenance"]["method"]), (False, "e1_raster_mask_vectorization"))
        artifact = manifest["artifacts"][0]
        request = urllib.request.Request(self.base + urllib.parse.urlsplit(artifact["download"]["url"]).path, method="GET")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read()
        self.assertEqual((len(payload), hashlib.sha256(payload).hexdigest()), (artifact["byte_size"], artifact["sha256"]))
        self.assertIn(b"<svg", payload[:400])

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
        self.assertEqual(done["status"], "needs_review")  # E1 vectoriza; sin H3 no hay puntadas validadas
        self.assertEqual((self.stages(done)["vectorizing"], self.stages(done)["digitizing"]), ("completed", "skipped"))
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
