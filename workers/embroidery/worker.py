"""H0-03 standalone CLI feasibility worker; not an HTTP API or digital approval."""
import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import traceback
import xml.etree.ElementTree as ET

from process_runner import WorkerFailure, run_logged

SVG = "http://www.w3.org/2000/svg"
IS = "http://inkstitch.org/namespace"
INK = "http://www.inkscape.org/namespaces/inkscape"


def prepared_input(source, directory):
    data = source.read_bytes()
    try:
        if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
            raise ValueError("DTD/entities are not supported")
        root = ET.fromstring(data)
        if root.tag != "{" + SVG + "}svg":
            raise ValueError("Expected SVG root")
        versions = list(root.iter("{" + IS + "}inkstitch_svg_version"))
        if not versions or int(versions[0].text or "0") != 3:
            raise ValueError("This probe requires a prepared Ink/Stitch schema-3 SVG; no silent migration")
        for element in root.iter():
            if element.tag in {"{" + SVG + "}script", "{" + SVG + "}foreignObject"}:
                raise ValueError("Active SVG content is not supported")
            for key, value in element.attrib.items():
                if key.endswith("href") and not value.startswith("#"):
                    raise ValueError("External/embedded referenced assets are not supported by this probe")
    except (ET.ParseError, ValueError) as exc:
        raise WorkerFailure("INPUT_UNREADABLE", "invalid_or_unprepared_svg", {"message": str(exc)}) from exc
    destination = directory / "input.svg"
    destination.write_bytes(data)
    return destination, hashlib.sha256(data).hexdigest()


def diagnostics(payload):
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise WorkerFailure("WORKER_EXPORT_FAILED", "invalid_diagnostics_svg", {"message": str(exc)}) from exc
    return [{"code": "ENGINE_DIAGNOSTIC_UNCLASSIFIED", "severity": "review_required",
             "native_text": "".join(element.itertext()), "native_diagnostic_id": element.get("id"),
             "source_object_mapping_verified": False}
            for element in root.iter("{" + SVG + "}text")
            if element.get("{" + INK + "}label") == "Description"]


def execute(args, directory):
    source, input_hash = prepared_input(args.svg.resolve(), directory)
    result = {"input_sha256": input_hash, "engine_sha256": None,
              "engine_version": args.engine_version, "engine_backend": "inkstitch_cli",
              "python_version": sys.version, "digital_readiness_evaluated": False,
              "physical_approval": "untested", "processes": []}
    if args.inkscape:
        version, record = run_logged([str(args.inkscape.resolve()), "--version"], directory, "inkscape-version", args.timeout)
        result.update(inkscape_version=version.decode(errors="replace").strip())
        result["processes"].append(record)
    command = [str(args.inkstitch.resolve())]
    if args.inkstitch.is_file():
        result["engine_sha256"] = hashlib.sha256(args.inkstitch.read_bytes()).hexdigest()
    payload, record = run_logged(command + ["--extension=troubleshoot", str(source)], directory, "diagnostics", args.timeout)
    (directory / "diagnostics.svg").write_bytes(payload)
    result["diagnostics"] = diagnostics(payload)
    result["processes"].append(record)
    payload, record = run_logged(command + ["--extension=output", "--format=jef", "--trims=true", str(source)], directory, "export", args.timeout)
    (directory / "output.jef").write_bytes(payload)
    result["processes"].append(record)
    from jef_audit import audit
    result["metrics"] = audit(directory)
    result["reader_version"] = importlib.metadata.version("pyembroidery")
    result.update(ok=True, format_checks_passed=True, acceptance="not_assessed; retain geometry/satin diagnostics for review")
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("svg", "job-dir", "inkstitch"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--inkscape", type=Path)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be finite and positive")
    directory = args.job_dir.resolve()
    try:
        directory.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(json.dumps({"ok": False, "issue": {"code": "WORKER_EXPORT_FAILED", "reason": "job_directory_unavailable", "evidence": {"message": str(exc)}}}))
        return 1
    try:
        result = execute(args, directory)
    except WorkerFailure as exc:
        result = {"ok": False, "issue": exc.issue, "digital_readiness_evaluated": False}
    except (OSError, ImportError) as exc:
        result = {"ok": False, "issue": {"code": "WORKER_EXPORT_FAILED", "reason": "environment_or_io_error", "evidence": {"message": str(exc)}}, "digital_readiness_evaluated": False}
    except Exception as exc:
        (directory / "worker.error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        result = {"ok": False, "issue": {"code": "WORKER_EXPORT_FAILED", "reason": "internal_worker_error", "evidence": {"message": str(exc), "type": type(exc).__name__}}, "digital_readiness_evaluated": False}
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
