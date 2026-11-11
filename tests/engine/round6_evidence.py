"""Reproduce the guide-based reference export and count real JEF commands.

Use the installed Ink/Stitch through worker.py, never an SVG stitch estimate.
Example: python -B tests/engine/round6_evidence.py --baseline-dir BASE --out OUT
--inkstitch EXE [--prepare-only | --measure-only]. Source files are read-only.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "workers/embroidery/.deps"), str(ROOT / "packages/contracts"),
               str(ROOT / "workers/embroidery")]

import pyembroidery as pe
from PIL import Image, ImageFilter
from embroidery_contracts import EmbroideryDocument, JobSettings
from jef_audit import binary_commands, measure
from vectorize.types import VectorizeResult
from vectorize.reference_geometry import apply
from vectorize.reference_geometry import _components, _mask
from vectorize.inkstitch import REFERENCE_PULL_COMPENSATION_MM, to_reference_inkstitch_svg

SVG = "{http://www.w3.org/2000/svg}"
IS = "{http://inkstitch.org/namespace}"
SOURCE_SHA256 = "3ba1cfc1f560fa4dfa47d23b3fe2f5be986b9714f9ad1124bce8cb0bb746f6c8"
SOURCE_E1_SHA256 = "8fb87ee04ebe321b778b1edfd33872d7a159945169ab723d92de19655d3936c0"
READER_SETTINGS = {"trims": True, "trim_at": 3, "trim_distance": None, "clipping": True}
COMMAND_NAMES = {pe.STITCH: "stitch", pe.JUMP: "jump", pe.TRIM: "trim",
                 pe.COLOR_CHANGE: "color_change", pe.END: "end", pe.STOP: "stop"}
WIDTH_BINS = (("<1", 0, 1), ("1-<1.5", 1, 1.5), ("1.5-4", 1.5, 4.000000001),
              (">4-<7", 4.000000001, 7), (">=7", 7, math.inf))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def measure_jef(path):
    """Independent raw decoder plus pyembroidery trim interpretation, in mm."""
    raw = binary_commands(path.read_bytes())
    pattern = pe.read(str(path), settings=READER_SETTINGS)
    metrics = measure(pattern, raw)
    previous, travel = (0, 0), 0.0
    for command, x, y in raw["events_01mm"]:
        if command == "jump":
            travel += math.dist(previous, (x, y)) / 10
        previous = x, y
    metrics.update(jump_travel_mm=travel, jef_sha256=sha(path),
                   raw_command_counts=raw["counts"],
                   pyembroidery_command_counts={COMMAND_NAMES.get(k, str(k)): v for k, v in
                                                 Counter(s[2] & pe.COMMAND_MASK for s in pattern.stitches).items()},
                   reader_version=importlib.metadata.version("pyembroidery"), reader_settings=READER_SETTINGS)
    return metrics


def width_summary(document):
    units = [r for obj in document.objects for r in obj.reference_rings if not r["omitted"]]
    bins = {name: Counter() for name, _, _ in WIDTH_BINS}
    for unit in units:
        width = unit.get("local_width_mm", unit["width"]["median_mm"])
        for name, low, high in WIDTH_BINS:
            if low <= width < high:
                bins[name][unit["technique"]] += 1
                break
    detail = json.dumps([{k: v for k, v in r.items() if not k.endswith("path_mm")} for r in units],
                        sort_keys=True, separators=(",", ":"))
    return {"techniques": dict(Counter(u["technique"] for u in units)),
            "width_bins_mm": {name: dict(counts) for name, counts in bins.items()},
            "unit_count": len(units),
            # Per-unit rails are reproducible from the versioned adapter; keep only their hash.
            "units_sha256": hashlib.sha256(detail.encode()).hexdigest()}


def _labelled_mask(document):
    """E1 mask dilated like component_topology, labelled by 8-connected component."""
    affine = document.coordinates.source_px_to_mm
    scale = abs(affine[0])
    canvas = Image.new("L", (math.ceil(document.page_bounds_mm.max_x_mm / scale) + 2,
                             math.ceil(document.page_bounds_mm.max_y_mm / scale) + 2))
    for obj in document.objects:
        for _, border, holes in _components(obj.path_data_mm):
            mask, origin = _mask([border, *holes], scale, None, (affine[4], affine[5]))
            canvas.paste(255, (round(origin[0]), round(origin[1])), mask)
    radius_px = math.ceil((REFERENCE_PULL_COMPENSATION_MM + .05) / scale)
    expanded = canvas.filter(ImageFilter.MaxFilter(2 * radius_px + 1))
    pixels, (width, height) = expanded.tobytes(), expanded.size
    labels, count = [0] * (width * height), 0
    for position, value in enumerate(pixels):
        if not value or labels[position]:
            continue
        count += 1
        labels[position], pending = count, [position]
        while pending:
            current = pending.pop()
            x, y = current % width, current // width
            for row in range(max(0, y - 1), min(height, y + 2)):
                for column in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = row * width + column
                    if pixels[neighbor] and not labels[neighbor]:
                        labels[neighbor] = count
                        pending.append(neighbor)
    box = canvas.getbbox()
    centre = ((box[0] + box[2]) / 2 * scale, (box[1] + box[3]) / 2 * scale)
    return labels, width, height, scale, centre


def jump_classification(path, document):
    """Each JEF jump run: explicit cut (>=3 zero jumps) or not; crosses blank fabric or not.

    JEF coordinates are centred on the stitch bounds; that centre is taken as the
    centre of the E1 mask bounds (pull compensation is symmetric).
    """
    labels, width, height, scale, centre = _labelled_mask(document)

    def label(point):
        x = int((point[0] / 10 + centre[0]) / scale)
        y = int((point[1] / 10 + centre[1]) / scale)
        return labels[y * width + x] if 0 <= x < width and 0 <= y < height else 0

    events, runs, previous, last_stitch = binary_commands(path.read_bytes())["events_01mm"], [], (0, 0), None
    index = 0
    while index < len(events):
        command, x, y = events[index]
        if command != "jump":
            if command == "stitch":
                last_stitch = (x, y)
            previous, index = (x, y), index + 1
            continue
        zero, start = 0, index
        while index < len(events) and events[index][0] == "jump":
            zero += (events[index][1], events[index][2]) == previous
            previous, index = (events[index][1], events[index][2]), index + 1
        commands = index - start
        if index < len(events) and events[index][0] == "stitch" and last_stitch:
            a, b = last_stitch, (events[index][1], events[index][2])
            length = math.dist(a, b) / 10
            steps = max(2, int(length / (scale / 2)) + 2)
            seen = {label((a[0] + (b[0] - a[0]) * k / steps, a[1] + (b[1] - a[1]) * k / steps))
                    for k in range(steps + 1)}
            runs.append({"cut": zero >= 3, "length_mm": length, "read_as_trim": commands >= READER_SETTINGS["trim_at"],
                         "crosses_blank": seen != {label(a)} or 0 in seen})
    crossing = [r for r in runs if r["crosses_blank"]]
    floats = [r for r in crossing if not r["cut"]]
    inside = [r for r in runs if not r["crosses_blank"]]
    return {"jump_runs_before_a_stitch": len(runs), "blank_crossings": len(crossing),
            "blank_crossings_cut": len(crossing) - len(floats),
            "uncut_blank_crossings": len(floats), "uncut_blank_crossing_mm": sum(r["length_mm"] for r in floats),
            "uncut_blank_crossings_read_as_trim_by_3_jump_rule": sum(r["read_as_trim"] for r in floats),
            "uncut_blank_crossings_left_as_floats": sum(not r["read_as_trim"] for r in floats),
            "max_float_over_blank_mm": max((r["length_mm"] for r in floats if not r["read_as_trim"]), default=0.),
            "cuts_inside_one_component": sum(r["cut"] for r in inside),
            "uncut_jumps_inside_one_component": sum(not r["cut"] for r in inside),
            "max_uncut_inside_mm": max((r["length_mm"] for r in inside if not r["cut"]), default=0.),
            "explicit_cut_runs_total": sum(1 for r in runs if r["cut"]),
            "policy": "mask dilated 0.30 mm (pull 0.25 + JEF 0.05); explicit cut = >=3 zero-length JEF jumps"}


def component_topology(document):
    """Conservative cut lower bound after over-approximating pull and rounding."""
    affine = document.coordinates.source_px_to_mm
    scale = abs(affine[0])
    canvas = Image.new("L", (math.ceil(document.page_bounds_mm.max_x_mm / scale) + 2,
                             math.ceil(document.page_bounds_mm.max_y_mm / scale) + 2))
    retained_count = 0
    for obj in document.objects:
        kept = {u["ring_index"] for u in obj.reference_rings if not u["omitted"]}
        for index, border, holes in _components(obj.path_data_mm):
            if index not in kept:
                continue
            retained_count += 1
            mask, origin = _mask([border, *holes], scale, None, (affine[4], affine[5]))
            canvas.paste(255, (round(origin[0]), round(origin[1])), mask)
    radius_px = math.ceil((REFERENCE_PULL_COMPENSATION_MM + .05) / scale)
    expanded = canvas.filter(ImageFilter.MaxFilter(2 * radius_px + 1))
    count = _connected_count(expanded)
    return {"retained_original_components": retained_count,
            "overexpanded_8_connected_components": count, "cut_lower_bound": max(0, count - 1),
            "overapproximation_box_radius_mm": radius_px * scale,
            "policy": "box dilation contains 0.25mm pull + 0.05mm JEF rounding; no connector across remaining blank gaps"}


def _connected_count(image):
    pixels = bytearray(image.tobytes())
    width, height = image.size
    count = 0
    for position, value in enumerate(pixels):
        if not value:
            continue
        count += 1
        pixels[position] = 0
        pending = [position]
        while pending:
            current = pending.pop()
            x, y = current % width, current // width
            for row in range(max(0, y - 1), min(height, y + 2)):
                for column in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = row * width + column
                    if pixels[neighbor]:
                        pixels[neighbor] = 0
                        pending.append(neighbor)
    return count


def prepare(args, baseline_job):
    source = args.baseline_dir / "input.png"
    if sha(source) != SOURCE_SHA256:
        raise ValueError("Wrong real-logo input hash")
    settings = JobSettings.model_validate(baseline_job["settings_snapshot"])
    assert settings.hoop_profile == "sq14b" and settings.fabric_profile == "algodon" and settings.color_limit == 12
    with Image.open(source) as image:
        width, height = image.size
    started = perf_counter()
    # Order 5 upstream already cleaned the palette and capped the target to
    # 130 mm. Reuse its registered E1 mask, never rerun a different preprocessor.
    doc_file = args.source_run / "vectorized-document.json"
    if sha(doc_file) != SOURCE_E1_SHA256:
        raise ValueError("Wrong registered Order 5 E1 document hash")
    document = EmbroideryDocument.model_validate_json(doc_file.read_bytes())
    source_evidence = json.loads((args.source_run / "vectorized-evidence.json").read_text(encoding="utf-8"))
    before = [obj.path_data_mm for obj in document.objects]
    derived, widths = apply(document, settings=settings)
    result = VectorizeResult(derived, (), b"", {"stroke_width": widths}, 0)
    payload = to_reference_inkstitch_svg(result)
    assert before == [obj.path_data_mm for obj in result.document.objects]
    (args.out / "input.svg").write_bytes(payload)
    (args.out / "before-routing.svg").write_bytes(payload)
    shutil.copyfile(doc_file, args.out / "source-e1-document.json")
    shutil.copyfile(args.source_run / "digitizing/input.svg", args.out / "before.svg")
    shutil.copyfile(args.baseline_dir / "output.jef", args.out / "before.jef")
    save_json(args.out / "settings.json", settings.model_dump(mode="json"))
    roots = [p for p in ET.fromstring(payload).iter(SVG + "path") if p.get("data-technique")]
    report = {"input_sha256": sha(source), "input_size_px": [width, height],
              "input_svg_sha256": sha(args.out / "input.svg"), "requested_settings": settings.model_dump(mode="json"),
              "target_vectorized_mm": [document.page_bounds_mm.max_x_mm, document.page_bounds_mm.max_y_mm],
              "api_inset_mm_before": .4, "api_inset_mm_after": 2 * REFERENCE_PULL_COMPENSATION_MM,
              "same_registered_e1_geometry_used": True,
              "source_e1_document_sha256": sha(doc_file), "before_svg_sha256": sha(args.out / "before.svg"),
              "vectorization_and_svg_s": perf_counter() - started,
              "e1_path_data_sha256": hashlib.sha256(json.dumps(before, separators=(",", ":")).encode()).hexdigest(),
              "e1_paths_unchanged_by_adapter": True, "width_selection": width_summary(result.document),
              "component_topology": component_topology(result.document),
              "svg_path_techniques": dict(Counter(p.get("data-technique") for p in roots)),
              "e1_mask_evidence": source_evidence["masks"],
              "svg_trim_after_true": sum(p.get(IS + "trim_after", "").lower() == "true" for p in roots),
              "status": "needs_review", "parameters_calibrated": False, "physical_approval": "untested",
              "digital_readiness_evaluated": False}
    save_json(args.out / "preparation.json", report)
    print(json.dumps({k: report[k] for k in ("input_svg_sha256", "svg_path_techniques", "vectorization_and_svg_s")}))


def export(args):
    command = [sys.executable, "-B", str(ROOT / "workers/embroidery/worker.py"),
               "--svg", str((args.out / "input.svg").resolve()), "--job-dir", str((args.out / "worker").resolve()),
               "--inkstitch", str(args.inkstitch.resolve()), "--engine-version", "v3.2.2",
               "--timeout", "600", "--jef-hoop-code", "2"]
    started = perf_counter()
    completed = subprocess.run(command, capture_output=True, timeout=1260)
    (args.out / "worker.stdout.txt").write_bytes(completed.stdout)
    (args.out / "worker.stderr.txt").write_bytes(completed.stderr)
    save_json(args.out / "timing.json", {"worker_wall_s": perf_counter() - started, "exit_code": completed.returncode})
    if completed.returncode:
        raise RuntimeError((args.out / "worker/result.json").read_text(encoding="utf-8"))
    shutil.copyfile(args.out / "worker/output.jef", args.out / "output.jef")
    shutil.copyfile(args.out / "worker/input.svg", args.out / "input.svg")
    shutil.copyfile(args.out / "worker/result.json", args.out / "worker-result.json")
    shutil.copyfile(args.out / "worker/diagnostics.svg", args.out / "troubleshoot.svg")


def measurements(args, baseline_job):
    prep = json.loads((args.out / "preparation.json").read_text(encoding="utf-8"))
    worker = json.loads((args.out / "worker/result.json").read_text(encoding="utf-8"))
    before = measure_jef(args.baseline_dir / "output.jef")
    after = measure_jef(args.out / "output.jef")
    document = EmbroideryDocument.model_validate_json((args.out / "source-e1-document.json").read_bytes())
    before["jump_classification"] = jump_classification(args.baseline_dir / "output.jef", document)
    after["jump_classification"] = jump_classification(args.out / "output.jef", document)
    before.update(digitizing_s=next(s["measured_duration_ms"] / 1000 for s in baseline_job["stages"]
                                   if s["stage"] == "digitizing"),
                  reported_job_wall_s=419.5,
                  troubleshoot=[i["description"] for i in baseline_job["diagnostics"]
                                if i["code"] == "ENGINE_DIAGNOSTIC_UNCLASSIFIED"])
    records = worker["processes"]
    after.update(digitizing_s=sum(r["duration_ms"] for r in records) / 1000,
                 export_s=sum(r["duration_ms"] for r in records if "--extension=output" in r["command"]) / 1000,
                 worker_wall_s=json.loads((args.out / "timing.json").read_text())["worker_wall_s"],
                 troubleshoot=[d["native_text"] for d in worker["diagnostics"]],
                 hoop_margin_per_side_mm=[(140 - after["width_mm"]) / 2, (140 - after["height_mm"]) / 2])
    paths = [p for p in ET.parse(args.out / "input.svg").getroot().iter(SVG + "path")
             if p.get("data-technique")]
    report = {**prep, "source_svg_sha256": prep["input_svg_sha256"], "input_svg_sha256": sha(args.out / "input.svg"),
              "final_svg_path_techniques": dict(Counter(p.get("data-technique") for p in paths)),
              "native_routing": worker.get("native_routing"), "before": before, "after": after,
              "engine_sha256": worker["engine_sha256"], "engine_version": worker["engine_version"],
              "hashes": {name: sha(args.out / name) for name in
                         ("input.svg", "output.jef", "settings.json", "source-e1-document.json", "before.svg", "before.jef",
                          "before-routing.svg", "worker-result.json", "troubleshoot.svg")}}
    save_json(args.out / "measurements.json", report)
    print(json.dumps({"before": before, "after": after}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True, help="immutable Order 5 job directory with E1 document")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inkstitch", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare-only", action="store_true")
    mode.add_argument("--measure-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    baseline_bytes = (args.baseline_dir / "job.json").read_bytes()
    try:
        baseline_text = baseline_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        baseline_text = baseline_bytes.decode("cp1252")  # historical OpenCode capture on Windows
    baseline_job = json.loads(baseline_text)
    if not args.measure_only:
        prepare(args, baseline_job)
        if args.prepare_only:
            return
        export(args)
    measurements(args, baseline_job)


if __name__ == "__main__":
    main()
