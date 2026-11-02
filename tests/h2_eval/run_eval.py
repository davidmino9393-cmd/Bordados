"""Paquete F de H2: mide el módulo E (vectorize) sobre el conjunto de tests/fixtures/h2.

Solo informa lo medido. Si `vectorize` no existe, dice que no está disponible y no inventa resultados.
Uso:  python tests/h2_eval/run_eval.py [--manifest RUTA] [--out informe.json] [--only ID ...] [--worker-path RUTA]
`--worker-path` antepone otra carpeta `workers/embroidery` (p. ej. un hash de E extraído con `git archive`) a la del árbol.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fidelity  # noqa: E402
from embroidery_contracts import AnalysisSpec, EmbroideryDocument, JobSettings, SourceAsset  # noqa: E402

DEFAULT_MANIFEST = ROOT / "tests" / "fixtures" / "h2" / "manifest.json"
VECTORIZE_SOURCE = ROOT / "workers" / "embroidery" / "vectorize"
BOUNDS_TOLERANCE_MM = 0.01
ALLOWED_GEOMETRY_KINDS = {"verified_curve", "verified_mask"}
PROVISIONAL_FLAG = "h3_validation_required"
PROVISIONAL_ISSUE_CODE = "DENSITY_REVIEW_REQUIRED"
MINIMUM_FEATURE_POLICY = "measure_and_report_never_remove_or_thicken"
TIMINGS_KEY = "timings"
NOT_MEASURED = ("holes_preserved_as_count", "text_as_annotation", "background_assumption")
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
    # Convención real de E1: una decisión por objeto con h3_validation_required, una incidencia DENSITY_REVIEW_REQUIRED
    # que cubre todos los objetos y la bandera en la evidencia. Nada de eso es calibración.
    flagged = {d.object_id for d in document.decisions
               if d.origin == "rule" and isinstance(d.new_value, dict) and d.new_value.get(PROVISIONAL_FLAG) is True}
    covered = {oid for issue in result.issues if issue.code.value == PROVISIONAL_ISSUE_CODE for oid in issue.object_ids}
    ids = {o.object_id for o in document.objects}
    checks["provisional_values_marked"] = bool(ids) and ids <= flagged and ids <= covered and result.evidence.get(PROVISIONAL_FLAG) is True
    checks["has_objects"] = bool(document.objects)
    feature = result.evidence.get("minimum_feature", {})
    # Política de ancho mínimo: se mide y se avisa, y E no descarta nada por tamaño.
    checks["minimum_feature_reported_never_removed"] = (
        feature.get("policy") == MINIMUM_FEATURE_POLICY and feature.get("min_width_mm_is_calibrated") is False
        and result.evidence.get("segmentation", {}).get("pixels_discarded_by_size_filter") == 0
    )
    issues = [issue.severity.value for issue in result.issues]
    expected = entry["expected_outcome"]
    return checks, {"expected_outcome": expected, "issue_severities": sorted(set(issues)),
                    "review_required_reported": "review_required" in issues}


def evaluate_image(vectorize_fn, entry, base_dir):
    if entry["format"] == "svg":  # los SVG siguen el recorrido de SVG preparado, no el de E
        return {"id": entry["id"], "category": entry["category"], "status": "skipped", "reason": "svg_uses_prepared_svg_path"}
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
    feature = first.evidence.get("minimum_feature", {})
    record["thin_features"] = {
        "min_width_mm": feature.get("min_width_mm"), "measurable": feature.get("measurable"),
        "thin_fraction_by_object": sorted((v["thin_fraction"] for v in feature.get("objects", {}).values()), reverse=True),
    }
    try:
        record["fidelity"] = fidelity.measure(first.document, data)
    except Exception as error:  # no se oculta: queda en el informe como no medido
        record["fidelity"] = {"not_measured": f"{type(error).__name__}: {error}"}
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
    summary = {"images": len(records), "skipped": sum(1 for r in records if r["status"] == "skipped"), "errors": sum(1 for r in records if r["status"] == "error"),
               "checks": {name: {"passed": sum(r["checks"][name] for r in ok), "of": len(ok)} for name in names}}
    ious = [r["fidelity"]["foreground_iou"] for r in ok if "foreground_iou" in r.get("fidelity", {})]
    if ious:
        summary["foreground_iou"] = {"min": min(ious), "median": statistics.median(ious), "measured": len(ious), "of": len(ok)}
    durations = [d for r in ok for d in r["duration_ms"]]
    if durations:
        summary["duration_ms"] = {"median": statistics.median(durations), "max": max(durations), "runs": len(durations)}
    return summary


def run(vectorize_fn, manifest_path=DEFAULT_MANIFEST, only=None):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    module = sys.modules.get("vectorize")
    evidence_source = str(Path(module.__file__).parent) if module and getattr(module, "__file__", None) else None
    entries = [e for e in manifest["images"] if not only or e["id"] in only]
    records = [evaluate_image(vectorize_fn, entry, Path(manifest_path).parent) for entry in entries]
    findings = static_review(manifest)
    summary = summarize(records)
    failed = summary["errors"] > 0 or bool(findings) or any(v["passed"] != v["of"] for v in summary["checks"].values())
    return {"status": "failed" if failed else "passed", "manifest": str(Path(manifest_path).name), "vectorize_source": evidence_source, "not_measured": list(NOT_MEASURED),
            "static_review": {"per_logo_literals": findings}, "summary": summary, "images": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--worker-path", help="carpeta que contiene el paquete vectorize a evaluar")
    args = parser.parse_args(argv)
    if args.worker_path:
        sys.path.insert(0, str(Path(args.worker_path).resolve()))
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
