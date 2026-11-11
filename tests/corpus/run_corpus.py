"""Pasa un corpus de archivos por la API real (con Inkscape y Ink/Stitch reales) y mide qué pasa con cada uno.

Uso:  python tests/corpus/run_corpus.py --dir CORPUS [--preconvert] [--only TEXTO] [--report RUTA_SIN_EXTENSION] [--keep CARPETA]
`CORPUS` es una carpeta con los archivos y un `manifest.json` (ver generate_corpus.py); sin manifiesto, cada archivo se
mide sin juicio previo. Los datos van a una carpeta temporal y no se toca la base de nadie.
`--preconvert` hace pasar primero cada archivo por la conversión de la API con todos los formatos admitidos y sube el PNG
resultante: sirve para medir cómo andaría un formato que el catálogo todavía no admite.
Por cada archivo informa: qué hizo la API (tipo, tamaño, conversión), cómo terminó el trabajo, avisos, el JEF releído
(tamaño en mm, puntadas, bloques de color), el tiempo, y si coincide con lo esperado. Termina con código 1 si algo esperado no se cumple.
`--keep CARPETA` guarda además, por archivo, el JEF y la vista previa del bordado para mirarlos.
"""
import argparse
import dataclasses
import hashlib
import json
import mimetypes
import shutil
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
for sub in ("services/api", "packages/contracts", "workers/embroidery"):
    sys.path.insert(0, str(ROOT / sub))

import pyembroidery  # noqa: E402
import uvicorn  # noqa: E402

from embroidery_api import input_convert  # noqa: E402
from embroidery_api.app import create_app  # noqa: E402
from embroidery_api.config import ApiConfig  # noqa: E402

TOKEN = "corpus"
JOB_TIMEOUT_S = 420
SETTINGS = json.loads((ROOT / "packages/contracts/fixtures/generation-from-svg.json").read_text(encoding="utf-8"))["payload"]["settings"]
TARGET_MM = 100.0
MIN_STITCHES, MAX_STITCHES = 50, 300_000
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp", ".gif": "image/gif",
        ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff", ".pdf": "application/pdf", ".ai": "application/pdf", ".eps": "application/postscript"}
PASSED = ("BORDADO", "BORDADO_CON_AVISOS")


def start_api(data_root):
    private = json.loads((ROOT / "services/api/.runtime/api-config.json").read_text(encoding="utf-8"))
    config = dataclasses.replace(ApiConfig(**private), data_root=data_root, service_token=TOKEN, basic_username=None, basic_password=None,
                                 database_url=None, public_base_url="http://127.0.0.1:0")
    server = uvicorn.Server(uvicorn.Config(create_app(config), host="127.0.0.1", port=0, log_level="critical"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}", config


class Client:
    def __init__(self, base):
        self.base = base

    def call(self, method, path, body=None, raw=None, headers=None):
        values = {"Authorization": f"Bearer {TOKEN}", **(headers or {})}
        data = raw
        if body is not None:
            data, values["Content-Type"] = json.dumps(body).encode(), "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=values, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")

    def post(self, path, body):
        return self.call("POST", path, body, headers={"Idempotency-Key": uuid.uuid4().hex})

    def upload(self, project_id, name, content, content_type):
        boundary = "----corpus" + uuid.uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {content_type}\r\n\r\n').encode() \
            + content + f"\r\n--{boundary}--\r\n".encode()
        return self.call("POST", f"/api/v1/projects/{project_id}/assets", raw=body,
                         headers={"Idempotency-Key": uuid.uuid4().hex, "Content-Type": f"multipart/form-data; boundary={boundary}"})

    def wait(self, job_id):
        deadline = time.time() + JOB_TIMEOUT_S
        while time.time() < deadline:
            _, job = self.call("GET", f"/api/v1/jobs/{job_id}")
            if job["status"] in {"needs_review", "failed", "cancelled", "ready_for_sewout"}:
                return job
            time.sleep(0.5)
        return {"status": "timeout", "issues": []}


def job_file(data_root, job_id, name):
    """El archivo de un trabajo: el worker de una imagen escribe en `digitizing/` y el de un SVG preparado, en la raíz."""
    return next(iter(sorted((data_root / "jobs" / job_id).rglob(name))), None)


def measure_jef(path):
    if path is None or not path.exists():
        return None
    pattern = pyembroidery.read(str(path))
    left, top, right, bottom = pattern.bounds()
    stitches = sum(1 for _, _, command in pattern.stitches if command == pyembroidery.STITCH)
    return {"width_mm": round((right - left) / 10, 1), "height_mm": round((bottom - top) / 10, 1), "stitches": stitches,
            "color_blocks": sum(1 for _ in pattern.get_as_colorblocks()), "jef_sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16]}


def judge(row, expect):
    """Si lo que pasó es lo que se esperaba. `libre`: sin juicio previo."""
    if expect == "libre":
        return True
    result = row["resultado"]
    if expect == "ok":
        return result in PASSED
    return result == expect.replace("rechazo:", "RECHAZADO:").replace("falla:", "FALLA:")


def run_one(client, data_root, directory, entry, preconvert, accepted_all, inkscape, keep=None):
    name = entry["file"]
    content = (directory / name).read_bytes()
    content_type = MIME.get(Path(name).suffix.lower(), mimetypes.guess_type(name)[0] or "application/octet-stream")
    row = {"archivo": name, "categoria": entry.get("category", ""), "formato": entry.get("format", Path(name).suffix.lstrip(".")),
           "esperado": entry.get("expect", "libre")}
    notes = []

    def done(**fields):
        row.update(fields)
        row["coincide"] = judge(row, row["esperado"])
        if notes:
            row["nota"] = "; ".join(notes)
        return row

    if preconvert:
        try:
            normalized = input_convert.normalize_upload(content, content_type, name, accepted=accepted_all, inkscape=inkscape)
        except input_convert.ConversionRefused as refused:
            return done(resultado=f"RECHAZADO:{refused.code}", detalle=refused.detail)
        if normalized.conversion:
            notes.append(f"convertido de {normalized.conversion['from']} con {normalized.conversion['tool']} antes de subir")
        content, content_type, name = normalized.data, normalized.media_type, normalized.filename
    _, project = client.post("/api/v1/projects", {"name": row["archivo"][:60]})
    pid = project["project_id"]
    status, asset = client.upload(pid, name, content, content_type)
    if status != 201:
        return done(resultado=f"RECHAZADO:{asset.get('code')}", detalle=asset.get("detail"))
    row["asset"] = {"tipo": asset["media_type"], "px": [asset.get("original_width_px"), asset.get("original_height_px")]}
    settings = {**SETTINGS, "target": {"width_mm": TARGET_MM, "height_mm": TARGET_MM, "fit": "contain"}, "ai_provider": "none"}
    _, revision = client.post(f"/api/v1/projects/{pid}/revisions", {"schema_version": "0.1", "base_revision_id": None, "reason": "corpus",
                                                                       "settings": settings, "document": None})
    kind = "prepared_svg" if asset["media_type"] == "image/svg+xml" else "raster_image"
    started = time.perf_counter()
    status, job = client.post(f"/api/v1/projects/{pid}/jobs", {"schema_version": "0.1", "asset_id": asset["asset_id"],
                                                                "revision_id": revision["revision_id"], "input_kind": kind, "settings": settings})
    if status != 202:
        return done(resultado=f"RECHAZADO:{job.get('code')}", detalle=job.get("detail"))
    finished = client.wait(job["job_id"])
    row["segundos"] = round(time.perf_counter() - started, 1)
    row["avisos"] = sorted({issue["code"] for issue in finished.get("issues") or []})
    jef = measure_jef(job_file(data_root, job["job_id"], "output.jef"))
    row["jef"] = jef
    if keep:
        keep.mkdir(parents=True, exist_ok=True)
        for source, suffix in (("output.jef", ".jef"), ("preview.png", ".preview.png")):
            found = job_file(data_root, job["job_id"], source)
            if found:
                shutil.copyfile(found, keep / (Path(row["archivo"]).stem + suffix))
    if finished["status"] == "needs_review" and jef:
        result = "BORDADO"
        if not MIN_STITCHES <= jef["stitches"] <= MAX_STITCHES:
            result = "BORDADO_SOSPECHOSO"
            notes.append(f"puntadas fuera de {MIN_STITCHES} a {MAX_STITCHES}")
        elif {"VISUAL_MISMATCH", "ANALYSIS_REGION_INCOHERENT"} & set(row["avisos"]):
            result = "BORDADO_CON_AVISOS"
        return done(resultado=result)
    failure = (finished.get("failure") or {}).get("code") or next(
        (issue["code"] for issue in finished.get("issues") or [] if issue.get("severity") == "blocking_error"), finished["status"])
    return done(resultado=f"FALLA:{failure}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--preconvert", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--keep", type=Path)
    arguments = parser.parse_args()
    manifest_file = arguments.dir / "manifest.json"
    entries = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else [
        {"file": path.name, "expect": "libre"} for path in sorted(arguments.dir.iterdir()) if path.is_file() and path.suffix.lower() in MIME]
    entries = [entry for entry in entries if arguments.only in entry["file"]]
    accepted_all = frozenset(set(MIME.values()) - {"application/postscript"})
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
        data_root = Path(temporary) / "data"
        server, base, config = start_api(data_root)
        client, rows = Client(base), []
        for entry in entries:
            row = run_one(client, data_root, arguments.dir, entry, arguments.preconvert, accepted_all, config.inkscape_executable, arguments.keep)
            rows.append(row)
            jef = row.get("jef")
            measured = f"{jef['width_mm']}x{jef['height_mm']} mm, {jef['stitches']} puntadas, {jef['color_blocks']} bloques" if jef else ""
            print(f"{'OK' if row['coincide'] else 'XX'} {row['archivo']:<32} {row['resultado']:<30} {measured} {row.get('segundos', '')}", file=sys.stderr, flush=True)
        server.should_exit = True
    by_result = {}
    for row in rows:
        key = row["resultado"].split(":")[0]
        by_result[key] = by_result.get(key, 0) + 1
    summary = {"archivos": len(rows), "como_se_esperaba": sum(1 for row in rows if row["coincide"]), "preconvertido": arguments.preconvert, "por_resultado": by_result}
    if arguments.report:
        arguments.report.with_suffix(".json").write_text(json.dumps({"resumen": summary, "filas": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0 if all(row["coincide"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
