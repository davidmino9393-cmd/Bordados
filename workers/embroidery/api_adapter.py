"""Map measured standalone-worker files to frozen v0.1; never grant readiness."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from embroidery_contracts import ArtifactManifest, Issue, JobResponse, ValidationReport
from embroidery_contracts.issues import ISSUE_RULES, IssueCode
from embroidery_contracts.results import Artifact, RereadMetrics, ValidationCheck

SVG = "http://www.w3.org/2000/svg"
IS = "http://inkstitch.org/namespace"
HOOP_MARGIN_MM = 2.0


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_issue(code, description, evidence, object_ids=()):
    rule = ISSUE_RULES[IssueCode(code)]
    return Issue(code=code, severity=rule.severity, stage=rule.stage, object_ids=object_ids,
                 description=description, evidence=evidence,
                 suggested_correction="Revisar la evidencia de este trabajo y crear otra revisión o intento si corresponde.")


def candidate_ids(source, satin_only=False):
    root = ET.parse(source).getroot()
    return tuple(element.get("id") for element in root.iter("{" + SVG + "}path")
                 if element.get("id") and (not satin_only or element.get("{" + IS + "}satin_column", "").lower() == "true"))


def measured_metrics(result, directory, raw_id, duration_ms):
    source = result["metrics"]
    events = json.loads((directory / "raw-commands.json").read_text(encoding="utf-8"))
    previous, max_stitch, jumps = (0, 0), 0.0, 0.0
    for command, x, y in events:
        length = math.hypot(x - previous[0], y - previous[1]) / 10
        if command == "stitch":
            max_stitch = max(max_stitch, length)
        elif command == "jump":
            jumps += length
        previous = (x, y)
    left, top, right, bottom = source["stitch_bounds_mm"]
    return RereadMetrics(
        stitch_bounds_mm={"min_x_mm": left, "min_y_mm": top, "max_x_mm": right, "max_y_mm": bottom},
        **{key: source[key] for key in ("needle_stitches", "thread_blocks", "color_changes", "raw_jump_commands", "displacement_jump_commands", "interpreted_trims")},
        max_stitch_length_mm=max_stitch, jump_travel_mm=jumps, processing_duration_ms=duration_ms,
        count_method=source["count_method"] + "; lengths from normalized raw commands /10; native JEF frame",
        raw_commands_artifact_id=raw_id,
    )


def native_issues(result, directory):
    satin_ids = candidate_ids(directory / "input.svg", satin_only=True)
    all_ids = candidate_ids(directory / "input.svg")
    issues = []
    for diagnostic in result.get("diagnostics", []):
        text = diagnostic.get("native_text", "")
        code = "SATIN_RUNG_WARNING" if "Satin has no rungs" in text else "ENGINE_DIAGNOSTIC_UNCLASSIFIED"
        issues.append(make_issue(code, text or "Diagnóstico nativo sin clasificación.",
                      {"native_text": text, "source_object_mapping_verified": False,
                       "localization": "candidate columns, native warning unmapped", "native_diagnostic_id": diagnostic.get("native_diagnostic_id")},
                      satin_ids or all_ids))
    if not issues:
        issues.append(make_issue("ENGINE_DIAGNOSTIC_UNCLASSIFIED", "Geometría, satin y recorrido aún requieren revisión independiente.",
                                {"reason": "digital_geometry_checks_not_implemented", "localization": "candidate source objects"}, all_ids))
    return issues


def measured_checks(job, result, tolerance):
    metrics, settings = result["metrics"], job["settings_snapshot"]
    target, hoop = settings["target"], settings["hoop"]
    dimensions_ok = metrics["width_mm"] <= target["width_mm"] + tolerance and metrics["height_mm"] <= target["height_mm"] + tolerance
    left, top, right, bottom = metrics["stitch_bounds_mm"]
    clearances = {"left": left + hoop["width_mm"] / 2, "right": hoop["width_mm"] / 2 - right,
                  "top": top + hoop["height_mm"] / 2, "bottom": hoop["height_mm"] / 2 - bottom}
    hoop_ok = (metrics["hoop_code"] == hoop["jef_hoop_code"]
               and min(clearances.values()) >= HOOP_MARGIN_MM)
    checks = [ValidationCheck(kind=kind, outcome="passed" if passed else "failed", method=method)
              for kind, passed, method in (("file", True, "independent JEF binary parser and pyembroidery reread"),
                                          ("dimensions", dimensions_ok, f"reread bounds within target; tolerance {tolerance} mm; no resizing"),
                                          ("hoop", hoop_ok, f"native stitch bounds and JEF code versus configured profile; clearance >= {HOOP_MARGIN_MM:g} mm per side"))]
    checks += [ValidationCheck(kind=kind, outcome="not_run", method="not implemented in H0-04; no inferred approval") for kind in ("geometry", "satin", "routing", "visual")]
    issues = []
    target_is_hoop = target["width_mm"] == hoop["width_mm"] and target["height_mm"] == hoop["height_mm"]
    # Si el límite del trabajo es el propio bastidor, pasarse es que el diseño no entra en él.
    if not dimensions_ok and not target_is_hoop:
        issues.append(make_issue("DIMENSIONS_EXCEEDED", "Las medidas releídas superan el destino configurado.", {"width_mm": metrics["width_mm"], "height_mm": metrics["height_mm"], "tolerance_mm": tolerance}))
    if not hoop_ok:
        # Medidas y bastidor (orden 4) más el margen de seguridad por lado que pide la guía (orden 6).
        detail = {"jef_hoop_code": metrics["hoop_code"], "expected_hoop_code": hoop["jef_hoop_code"], "hoop_profile": hoop.get("profile_id"),
                  "hoop_width_mm": hoop["width_mm"], "hoop_height_mm": hoop["height_mm"],
                  "design_width_mm": metrics["width_mm"], "design_height_mm": metrics["height_mm"],
                  "required_margin_per_side_mm": HOOP_MARGIN_MM, "clearance_per_side_mm": clearances}
        issues.append(make_issue(
            "HOOP_INCOMPATIBLE",
            f"El diseño ({metrics['width_mm']:g} x {metrics['height_mm']:g} mm) no entra en el bastidor {hoop.get('profile_id') or 'elegido'} "
            f"({hoop['width_mm']:g} x {hoop['height_mm']:g} mm) con el margen de seguridad de {HOOP_MARGIN_MM:g} mm por lado.", detail))
    return checks, issues


def result_documents(job, result, directory, duration_ms, tolerance, display_names=None, input_sha256=None):
    """`display_names`: nombre que ve la persona al descargar, por tipo de archivo; en disco el archivo no cambia.

    `input_sha256`: huella de lo que subió la persona. Sin ella (un SVG preparado) la entrada es el SVG que recibió el
    worker; con ella (una imagen) el SVG intermedio es la geometría y no se confunde con la entrada.
    """
    display_names = display_names or {}
    job_id = job["job_id"]
    raw_id = f"{job_id}_raw_commands_json"
    metrics = measured_metrics(result, directory, raw_id, duration_ms)
    provenance = {"simulated": False, "method": "standalone Ink/Stitch CLI; independent binary audit and JEF reread",
                  "engine_version": result["engine_version"], "parser_version": result["reader_version"]}
    checks, issues = measured_checks(job, result, tolerance)
    issues += native_issues(result, directory)
    if not any(issue.object_ids or issue.region_ids for issue in issues if issue.severity == "review_required"):
        issues.append(make_issue("WORKER_EXPORT_FAILED", "No fue posible localizar la revisión pendiente en objetos de origen.", {"reason": "review_localization_unavailable"}))
    report = ValidationReport(report_id=f"{job_id}_report", job_id=job_id, revision_id=job["revision_id"],
                              provenance=provenance, checks=checks, issues=issues, digital_checks_passed=False, metrics=metrics)
    (directory / "validation.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    shutil.copyfile(directory / "input.svg", directory / "editable.svg")
    shutil.copyfile(directory / "input.svg", directory / "inkstitch.svg")
    files = (("jef", "output.jef", "application/octet-stream", "export"),
             ("editable_svg", "editable.svg", "image/svg+xml", "document"), ("inkstitch_svg", "inkstitch.svg", "image/svg+xml", "document"),
             ("preview_png", "preview.png", "image/png", "jef_reread"), ("validation_json", "validation.json", "application/json", "validation"),
             ("raw_commands_json", "raw-commands.json", "application/json", "jef_reread"))
    artifacts = [Artifact(artifact_id=f"{job_id}_{kind}", job_id=job_id, kind=kind, filename=display_names.get(kind, filename),
                          media_type=media, sha256=digest(directory / filename), byte_size=(directory / filename).stat().st_size,
                          derived_from=origin)
                 for kind, filename, media, origin in files]
    on_disk = {f"{job_id}_{kind}": str(directory / filename) for kind, filename, _, _ in files}
    settings_hash = hashlib.sha256(json.dumps(job["settings_snapshot"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = ArtifactManifest(manifest_id=f"{job_id}_manifest", job_id=job_id, revision_id=job["revision_id"], provenance=provenance,
                                input_sha256=input_sha256 or result["input_sha256"], settings_sha256=settings_hash,
                                geometry_sha256=result["input_sha256"], artifacts=artifacts, reread_metrics=metrics)
    return report, manifest, on_disk
