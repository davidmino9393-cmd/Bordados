"""Paquete F de H2: mide el módulo E (vectorize) sobre el conjunto de tests/fixtures/h2.

Solo informa lo medido. Si `vectorize` no existe, dice que no está disponible y no inventa resultados.
Uso:  python tests/h2_eval/run_eval.py [--manifest RUTA] [--out informe.json] [--only ID ...]
Códigos de salida: 0 todas las comprobaciones pasan, 1 alguna falla, 2 vectorize no disponible.
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("packages/contracts", "workers/embroidery"):
    sys.path.insert(0, str(ROOT / sub))

from embroidery_contracts import AnalysisSpec, EmbroideryDocument, JobSettings, SourceAsset  # noqa: E402

DEFAULT_MANIFEST = ROOT / "tests" / "fixtures" / "h2" / "manifest.json"
VECTORIZE_SOURCE = ROOT / "workers" / "embroidery" / "vectorize"
BOUNDS_TOLERANCE_MM = 0.01
ALLOWED_GEOMETRY_KINDS = {"verified_curve", "verified_mask"}
PROVISIONAL_REASON_PREFIX = "provisional_until_h3"
PROVISIONAL_STATUS = "provisional_uncalibrated"
TIMINGS_KEY = "timings"
NOT_MEASURED = ("iou_vs_mask", "holes_preserved", "text_as_annotation")
MEDIA_TYPES = {"png": "image/png", "jpeg": "image/jpeg", "svg": "image/svg+xml"}
SETTINGS_BASE = {
    "machine_profile": "janome_mc550e", "machine_profile_version": "0.1",
    "hoop_profile": "sq20b", "hoop": {"profile_id": "sq20b", "profile_version": "0.1", "width_mm": 200.0, "height_mm": 200.0, "jef_hoop_code": 4},
    "fabric_profile": "gabardina_inicial", "fabric_profile_version": "0.1", "thread_profile": "embroidery_thread_initial",
    "ai_provider": "none", "ai_model": None,
}


def load_vectorize():
    try:
        from vectorize import vectorize  # noqa: PLC0415
    except ImportError:
        return None
    return vectorize


def build_inputs(entry, base_dir):
    data = (base_dir / entry["file"]).read_bytes()
    size = entry.get("pixel_size")
    asset = SourceAsset(
        asset_id=f"asset_{entry['id']}".replace("-", "_"), project_id="project_eval", sha256=hashlib.sha256(data).hexdigest(),
        media_type=MEDIA_TYPES[entry["format"]], original_filename=Path(entry["file"]).name,
        original_width_px=size["width"] if size else None, original_height_px=size["height"] if size else None,
    )
    target = entry["target_size_mm"]
    settings = JobSettings(target={"width_mm": target["width_mm"], "height_mm": target["height_mm"]},
                           color_limit=entry["expected_colors"], **SETTINGS_BASE)
    # Sin pistas de IA a propósito: E debe sacar la geometría de los píxeles. No es un análisis real.
    analysis = AnalysisSpec(
        analysis_id=f"analysis_{asset.asset_id}", asset_id=asset.asset_id, provider="openai", model="arnes-sin-analisis",
        prompt_version="none", original_response_artifact_id="none", regions=(), duration_ms=0,
    )
    return data, asset, settings, analysis


def deterministic_part(evidence):
    return {key: value for key, value in evidence.items() if key != TIMINGS_KEY}


def check_result(result, asset, settings, entry):
    document = result.document
    checks = {}
    try:
        EmbroideryDocument.model_validate(document.model_dump(mode="json"))
        checks["document_valid"] = True
    except Exception:
        checks["document_valid"] = False
    bounds, target = document.object_bounds_mm, settings.target
    checks["within_target_contain"] = (
        bounds.min_x_mm >= -BOUNDS_TOLERANCE_MM and bounds.min_y_mm >= -BOUNDS_TOLERANCE_MM
        and bounds.max_x_mm <= target.width_mm + BOUNDS_TOLERANCE_MM and bounds.max_y_mm <= target.height_mm + BOUNDS_TOLERANCE_MM
    )
    checks["colors_within_limit"] = len({o.work_color.lower() for o in document.objects}) <= settings.color_limit
    checks["geometry_kinds_allowed"] = all(o.geometry_kind in ALLOWED_GEOMETRY_KINDS for o in document.objects)
    provisional = {d.object_id for d in document.decisions if d.reason.startswith(PROVISIONAL_REASON_PREFIX) and d.origin == "rule"}
    checks["provisional_values_marked"] = (
        bool(document.objects) and all(o.object_id in provisional for o in document.objects)
        and result.evidence.get("parameters_status") == PROVISIONAL_STATUS
    )
    checks["has_objects"] = bool(document.objects)
    issues = [issue.severity.value for issue in result.issues]
    expected = entry["expected_outcome"]
    return checks, {"expected_outcome": expected, "issue_severities": sorted(set(issues)),
                    "review_required_reported": "review_required" in issues}


def evaluate_image(vectorize_fn, entry, base_dir):
    data, asset, settings, analysis = build_inputs(entry, base_dir)
    kwargs = {"job_id": "job_eval", "revision_id": "revision_eval"}
    record = {"id": entry["id"], "category": entry["category"]}
    try:
        first = vectorize_fn(data, asset.media_type, asset, analysis, settings, **kwargs)
        second = vectorize_fn(data, asset.media_type, asset, analysis, settings, **kwargs)
    except Exception as error:  # VectorizeError o fallo inesperado: se informa, no se oculta
        code = getattr(error, "code", None)
        record.update(status="error", error_type=type(error).__name__, error_code=getattr(code, "value", code), reason=str(getattr(error, "reason", error)))
        return record
    checks, outcome = check_result(first, asset, settings, entry)
    checks["deterministic"] = (
        first.document.model_dump(mode="json") == second.document.model_dump(mode="json")
        and first.editable_svg == second.editable_svg
        and deterministic_part(first.evidence) == deterministic_part(second.evidence)
    )
    record.update(status="ok", checks=checks, outcome=outcome, objects=len(first.document.objects),
                  duration_ms=[first.duration_ms, second.duration_ms])
    return record


def forbidden_literals(manifest):
    names = set()
    for entry in manifest["images"]:
        names.update({Path(entry["file"]).name, Path(entry["file"]).stem, entry["id"], entry["design_family"]})
    return {name for name in names if len(name) >= 4}


def static_review(manifest, source_dir=VECTORIZE_SOURCE):
    """Busca nombres de archivo, ids y familias del conjunto dentro del código de E (constantes por logo)."""
    findings = []
    for path in sorted(source_dir.rglob("*.py")) if source_dir.exists() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        for literal in sorted(forbidden_literals(manifest)):
            if re.search(re.escape(literal), text, re.IGNORECASE):
                findings.append({"file": path.name if source_dir != VECTORIZE_SOURCE else str(path.relative_to(ROOT)), "literal": literal})
    return findings


def summarize(records):
    ok = [r for r in records if r["status"] == "ok"]
    names = sorted({name for r in ok for name in r["checks"]})
    summary = {"images": len(records), "errors": sum(1 for r in records if r["status"] == "error"),
               "checks": {name: {"passed": sum(r["checks"][name] for r in ok), "of": len(ok)} for name in names}}
    durations = [d for r in ok for d in r["duration_ms"]]
    if durations:
        summary["duration_ms"] = {"median": statistics.median(durations), "max": max(durations), "runs": len(durations)}
    return summary


def run(vectorize_fn, manifest_path=DEFAULT_MANIFEST, only=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    entries = [e for e in manifest["images"] if not only or e["id"] in only]
    records = [evaluate_image(vectorize_fn, entry, Path(manifest_path).parent) for entry in entries]
    findings = static_review(manifest)
    summary = summarize(records)
    failed = summary["errors"] > 0 or bool(findings) or any(v["passed"] != v["of"] for v in summary["checks"].values())
    return {"status": "failed" if failed else "passed", "manifest": str(Path(manifest_path).name), "not_measured": list(NOT_MEASURED),
            "static_review": {"per_logo_literals": findings}, "summary": summary, "images": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out")
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    vectorize_fn = load_vectorize()
    if vectorize_fn is None:
        report = {"status": "vectorize_not_available", "detail": "No existe workers/embroidery/vectorize; no se midió nada."}
    else:
        report = run(vectorize_fn, args.manifest, set(args.only or ()))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return {"passed": 0, "failed": 1}.get(report["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
