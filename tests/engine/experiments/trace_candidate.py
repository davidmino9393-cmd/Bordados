"""Trace an isolated kmeans=3 candidate; never modify or select production E."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "workers/embroidery/vectorize"
FIXTURES = ROOT / "tests/fixtures/h2"
SELECTED = {"logo-sol-01", "logo-hoja-01", "logo-escudo-01", "logo-ola-01",
            "anillo-doble-01", "jpeg-simple-01", "dificil-degradado-01", "dificil-texto-chico-01"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def source_hashes(directory):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.glob("*.py"))}


def cases():
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    entries = [entry for entry in manifest["images"] if entry["id"] in SELECTED]
    assert {entry["id"] for entry in entries} == SELECTED, "Missing or changed fixture cases"
    for suffix, width, height in (("150", 150, 142.8), ("126", 126.2, 120)):
        entries.append({"id": "anime-reference-" + suffix, "file": "Anime_Socks.png", "format": "png",
                        "expected_colors": 3, "target_size_mm": {"width_mm": width, "height_mm": height}})
    return entries


def inputs(entry, JobSettings, SourceAsset):
    from PIL import Image
    path = FIXTURES / entry["file"]
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if entry.get("sha256") and digest != entry["sha256"]:
        raise ValueError("Fixture hash changed: " + entry["id"])
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
    media_type = "image/jpeg" if entry["format"] == "jpeg" else "image/png"
    asset = SourceAsset(asset_id="asset_" + entry["id"], project_id="project_trace",
                        sha256=digest, media_type=media_type, original_filename=path.name,
                        original_width_px=width, original_height_px=height)
    template = json.loads((ROOT / "packages/contracts/fixtures/generation-from-svg.json").read_text(encoding="utf-8"))
    settings = template["payload"]["settings"]
    settings.update(target={**entry["target_size_mm"], "fit": "contain"}, color_limit=entry["expected_colors"])
    return data, media_type, asset, JobSettings.model_validate(settings)


def child(worker_path, variant, output):
    sys.path[:0] = [str(worker_path), str(ROOT / "packages/contracts")]
    import vectorize as package
    from embroidery_contracts import EmbroideryDocument, JobSettings, SourceAsset
    from vectorize import VectorizeFailure, vectorize
    if not Path(package.__file__).resolve().is_relative_to(worker_path.resolve()):
        raise RuntimeError("Imported the wrong worker")
    records = []
    for entry in cases():
        args = inputs(entry, JobSettings, SourceAsset)
        kwargs = {"job_id": "job_" + entry["id"], "revision_id": "rev_" + entry["id"]}
        try:
            first = vectorize(args[0], args[1], args[2], None, args[3], **kwargs)
            second = vectorize(args[0], args[1], args[2], None, args[3], **kwargs)
        except VectorizeFailure as error:
            records.append({"case": entry["id"], "status": "controlled_incidence",
                            "issue": error.issue.model_dump(mode="json")})
            continue
        evidence, doc = first.evidence, first.document
        EmbroideryDocument.model_validate_json(doc.model_dump_json())
        same = doc == second.document and first.editable_svg == second.editable_svg and evidence == second.evidence
        bounds, target = doc.object_bounds_mm, args[3].target
        checks = {"deterministic": same,
                  "colors_within_limit": len({obj.work_color for obj in doc.objects}) <= args[3].color_limit,
                  "within_target": 0 <= bounds.min_x_mm <= bounds.max_x_mm <= target.width_mm + 1e-8
                  and 0 <= bounds.min_y_mm <= bounds.max_y_mm <= target.height_mm + 1e-8,
                  "provisional_h3": evidence["h3_validation_required"] and any(
                      issue.code.value == "DENSITY_REVIEW_REQUIRED" for issue in first.issues),
                  "no_size_filter": evidence["segmentation"]["pixels_discarded_by_size_filter"] == 0}
        if not all(checks.values()):
            raise AssertionError((entry["id"], checks))
        records.append({"case": entry["id"], "status": "traced", "checks": checks,
                        "input_sha256": args[2].sha256, "frame": doc.coordinates.model_dump(mode="json"),
                        "bounds_mm": bounds.model_dump(), "duration_ms": [first.duration_ms, second.duration_ms],
                        "document_sha256": hashlib.sha256(doc.model_dump_json().encode()).hexdigest(),
                        "svg_sha256": hashlib.sha256(first.editable_svg).hexdigest(),
                        "svg_bytes": len(first.editable_svg), "masks_per_color": evidence["masks"],
                        "segmentation": evidence["segmentation"], "issue_codes": [i.code.value for i in first.issues]})
        print(variant, entry["id"], "traced", first.duration_ms, "ms", flush=True)
    event = threading.Event()
    event.set()
    try:
        vectorize(args[0], args[1], args[2], None, args[3], **kwargs, cancel=event)
    except VectorizeFailure as error:
        cancellation = error.code.value
    else:
        raise AssertionError("Pre-cancelled work was not stopped")
    assert cancellation == "JOB_CANCELLED"
    write_json(output, {"variant": variant, "source_hashes": source_hashes(worker_path / "vectorize"),
                        "pre_cancel_result": cancellation, "records": records})


def candidate_copy():
    temporary_root = (ROOT / "tests/engine/.tmp").resolve()
    directory = (temporary_root / ("trace-candidate-" + uuid.uuid4().hex)).resolve()
    if not directory.is_relative_to(temporary_root):
        raise ValueError("Candidate directory escapes workspace temp")
    package = directory / "vectorize"
    package.mkdir(parents=True)
    for path in SOURCE.glob("*.py"):
        shutil.copyfile(path, package / path.name)
    path = package / "segmentation.py"
    text = path.read_text(encoding="utf-8")
    token = "colors=color_limit, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE,"
    assert text.count(token) == 1
    text = text.replace(token, "colors=color_limit, method=Image.Quantize.MEDIANCUT, kmeans=3, dither=Image.Dither.NONE,")
    text = text.replace("Pillow MEDIANCUT; no dithering; foreground pixels only", "EXPERIMENT Pillow MEDIANCUT kmeans=3; no dithering; foreground pixels only")
    path.write_text(text, encoding="utf-8")
    path = package / "pipeline.py"
    text = path.read_text(encoding="utf-8")
    token = 'METHOD_VERSION = "e1-pixel-mask-v1"'
    assert text.count(token) == 1
    path.write_text(text.replace(token, 'METHOD_VERSION = "experiment-kmeans3-full-trace"'), encoding="utf-8")
    return directory


def summarize(baseline, candidate):
    assert len(baseline["records"]) == len(candidate["records"]) == 10
    assert baseline["source_hashes"] == source_hashes(SOURCE), "Production source changed"
    comparisons = []
    for before, after in zip(baseline["records"], candidate["records"]):
        assert before["case"] == after["case"]
        row = {"case": before["case"], "statuses": [before["status"], after["status"]]}
        if row["statuses"] == ["traced", "traced"]:
            assert before["input_sha256"] == after["input_sha256"], "Input changed between variants"
            row.update(mask_unchanged=before["segmentation"]["source_mask_sha256"] == after["segmentation"]["source_mask_sha256"],
                       foreground_count_unchanged=before["segmentation"]["foreground_pixels"] == after["segmentation"]["foreground_pixels"],
                       frame_unchanged=before["frame"] == after["frame"],
                       bounds_unchanged=before["bounds_mm"] == after["bounds_mm"],
                       rgb_mae=[r["segmentation"]["mean_absolute_channel_error_rgb"] for r in (before, after)],
                       edges=[sum(m["boundary_edges"] for m in r["masks_per_color"]) for r in (before, after)],
                       holes=[sum(m["holes"] for m in r["masks_per_color"]) for r in (before, after)],
                       svg_bytes=[r["svg_bytes"] for r in (before, after)], durations_ms=[before["duration_ms"], after["duration_ms"]])
            assert row["mask_unchanged"] and row["frame_unchanged"] and row["bounds_unchanged"] and row["foreground_count_unchanged"]
        comparisons.append(row)
    return {"experiment_only": True, "production_baseline_commit": "4a7fd6b", "cases": comparisons,
            "production_sources_unchanged": True, "traced_input_hashes_unchanged": True,
            "topology_by_colour_may_change": True, "semantic_legibility_or_physical_quality_verified": False,
            "jef_generated": False, "process_memory_measured": False,
            "candidate_selected_for_production": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tests/engine/evidence/trace-candidate")
    parser.add_argument("--child", choices=("baseline", "candidate"))
    parser.add_argument("--worker-path", type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.worker_path.resolve(), args.child, args.output)
    before = source_hashes(SOURCE)
    candidate = candidate_copy()
    args.output.mkdir(parents=True, exist_ok=True)
    for variant, path in (("baseline", SOURCE.parent), ("candidate", candidate)):
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--child", variant,
                        "--worker-path", str(path), "--output", str(args.output / (variant + ".json"))],
                       check=True, timeout=240, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert source_hashes(SOURCE) == before, "Production source changed during experiment"
    baseline = json.loads((args.output / "baseline.json").read_text(encoding="utf-8"))
    refined = json.loads((args.output / "candidate.json").read_text(encoding="utf-8"))
    write_json(args.output / "summary.json", summarize(baseline, refined))
    print("Full tracing comparison complete; production unchanged.")


if __name__ == "__main__":
    main()
