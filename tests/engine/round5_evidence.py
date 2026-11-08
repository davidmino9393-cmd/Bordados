"""Reproduce round 5 with a local immutable job copy and the installed exporter.

Usage: python -B tests/engine/round5_evidence.py --job-dir LOCAL_JOB --out IGNORED_TMP --inkstitch EXE
The job's SVG/PNG stay in ignored temporary storage; only measured reports are committed.
"""
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/contracts"), str(ROOT / "workers/embroidery"), str(ROOT / "tests/engine")]

from embroidery_contracts import EmbroideryDocument, IssueCode
from vectorize.reference_geometry import apply, legibility_issues
from vectorize.inkstitch import reference_issues, to_reference_inkstitch_svg
from vectorize.types import VectorizeResult
from test_reference_techniques import stroke

SVG = "{http://www.w3.org/2000/svg}"
INKSTITCH = "{http://inkstitch.org/namespace}"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(document, evidence):
    result = {}
    for obj in document.objects:
        rings = obj.reference_rings
        stats = {key: value for key, value in evidence[obj.object_id].items() if key != "rings"}
        result[obj.object_id] = {**stats, "ring_count": len(rings),
                                 "techniques_all_rings": dict(Counter(r["technique"] for r in rings)),
                                 "techniques_exported_rings": dict(Counter(r["technique"] for r in rings if not r["omitted"])),
                                 "omitted": dict(Counter(r["omitted"] for r in rings if r["omitted"])),
                                 "running_compensation_mm": sorted({r["pull_compensation_mm"] for r in rings if r["technique"] == "running"}),
                                 "kept_rings": [{key: value for key, value in r.items()
                                                 if key not in {"stitch_path_mm", "fill_path_mm"}}
                                                for r in rings if not r["omitted"]]}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inkstitch", type=Path, required=True)
    parser.add_argument("--export-timeout", type=int, default=900)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    original_svg = args.out / "original-input.svg"
    original_doc = args.out / "original-document.json"
    shutil.copyfile(args.job_dir / "digitizing/input.svg", original_svg)
    shutil.copyfile(args.job_dir / "vectorized-document.json", original_doc)
    raw_doc = EmbroideryDocument.model_validate_json(original_doc.read_bytes())
    # Measure E1's original geometry as well as the actual (simplified) SVG passed to Ink/Stitch.
    measured_doc, full_widths = apply(raw_doc)
    assert [o.path_data_mm for o in measured_doc.objects] == [o.path_data_mm for o in raw_doc.objects]
    root = ET.fromstring(original_svg.read_bytes())
    paths = {p.get("id"): p for p in root.iter(SVG + "path")}
    actual_objects = tuple(obj.model_copy(update={"path_data_mm": paths[obj.object_id].get("d"),
                                                "reference_rings": (), "stitch_path_mm": None})
                           for obj in raw_doc.objects if obj.object_id in paths)
    actual_doc = raw_doc.model_copy(update={"objects": actual_objects})
    derived, widths = apply(actual_doc)
    assert [o.path_data_mm for o in actual_doc.objects] == [o.path_data_mm for o in derived.objects]
    result = VectorizeResult(derived, legibility_issues(widths), b"", {"stroke_width": widths}, 0)
    output = to_reference_inkstitch_svg(result)
    (args.out / "new-reference.svg").write_bytes(output)
    nodes = list(ET.fromstring(output).iter(SVG + "path"))
    running = [p for p in nodes if p.get("data-technique") == "running"]
    assert running, "Real job must produce centreline running paths"
    assert all(INKSTITCH + "auto_fill" not in p.attrib and INKSTITCH + "pull_compensation_mm" not in p.attrib for p in running)
    real_rings = [r for obj in derived.objects for r in obj.reference_rings if not r["omitted"]]
    assert all(r["technique"] == "running" and r["pull_compensation_mm"] == 0
               for r in real_rings if r["width"]["median_mm"] < .9)
    assert any(i.code == IssueCode.LEGIBILITY_RISK for i in result.issues)
    fixtures = {}
    for width in (.3, .5, .8, 1.5, 3.):
        value = stroke(width)
        ring, = value.document.objects[0].reference_rings
        fixtures[str(width)] = {key: value for key, value in ring.items() if key not in {"stitch_path_mm", "fill_path_mm"}}
    command = [sys.executable, "-B", str(ROOT / "workers/embroidery/worker.py"), "--svg", str(args.out / "new-reference.svg"),
               "--job-dir", str(args.out / "export"), "--inkstitch", str(args.inkstitch),
               "--engine-version", "v3.2.2", "--timeout", str(args.export_timeout), "--jef-hoop-code", "4"]
    completed = subprocess.run(command, capture_output=True, timeout=2 * args.export_timeout + 60)
    (args.out / "worker.stdout").write_bytes(completed.stdout)
    (args.out / "worker.stderr").write_bytes(completed.stderr)
    exported = json.loads((args.out / "export/result.json").read_text(encoding="utf-8"))
    assert completed.returncode == 0 and exported["ok"], exported
    assert all(count > 0 for count in exported["metrics"]["needle_stitches_by_thread_block"])
    report = {"original_input_svg_sha256": sha(original_svg), "original_document_sha256": sha(original_doc),
              "new_svg_sha256": sha(args.out / "new-reference.svg"), "source_mask_path_data_mm_unchanged": True,
              "original_e1_widths": summarize(measured_doc, full_widths), "actual_input_svg_widths": summarize(derived, widths),
              "fixture_measurements": fixtures, "exported_path_techniques": dict(Counter(p.get("data-technique") for p in nodes)),
              "issues": [i.model_dump(mode="json") for i in reference_issues(result)],
              "metrics": exported["metrics"], "diagnostics": exported["diagnostics"],
              "engine_sha256": exported["engine_sha256"], "physical_approval": "untested", "digital_readiness_evaluated": False}
    (args.out / "measurements.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": report["metrics"], "path_techniques": report["exported_path_techniques"]}))


if __name__ == "__main__":
    main()
