"""Reproduce E1 smoke evidence; not the independent H2 evaluation F."""
import argparse
import hashlib
from io import BytesIO
import json
import platform
from pathlib import Path
import subprocess
import sys

from PIL import Image, __version__ as pillow_version

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "workers" / "embroidery"))

from embroidery_contracts import JobSettings, SourceAsset
from vectorize import vectorize


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def case_inputs(case, fixture_root):
    path = fixture_root / case["file"]
    data = path.read_bytes()
    if sha(data) != case["sha256"]:
        raise ValueError(f"Input hash changed: {case['id']}")
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
    media_type = {"png": "image/png", "jpeg": "image/jpeg"}[case["format"]]
    asset = SourceAsset(
        asset_id="asset_" + case["id"], project_id="project_e1_smoke",
        sha256=sha(data), media_type=media_type, original_filename=path.name,
        original_width_px=width, original_height_px=height,
    )
    settings_path = ROOT / "packages/contracts/fixtures/generation-from-svg.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))["payload"]["settings"]
    settings.update(target={**case["target_size_mm"], "fit": "contain"}, color_limit=case["expected_colors"])
    return data, media_type, asset, JobSettings.model_validate(settings)


def render_preview(inkscape, svg, output):
    command = [str(inkscape), str(svg.resolve()), "--export-area-page", "--export-width=600",
               "--export-type=png", "--export-filename=" + str(output.resolve())]
    result = subprocess.run(command, capture_output=True, timeout=30, check=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {"renderer": "Inkscape CLI", "sha256": sha(output.read_bytes()),
            "stderr": result.stderr.decode(errors="replace")}


def record_case(case, fixture_root, destination, inkscape):
    inputs = case_inputs(case, fixture_root)
    arguments = {"job_id": "job_" + case["id"], "revision_id": "rev_" + case["id"], "cancel": None}
    first = vectorize(inputs[0], inputs[1], inputs[2], None, inputs[3], **arguments)
    second = vectorize(inputs[0], inputs[1], inputs[2], None, inputs[3], **arguments)
    deterministic = (first.document == second.document and first.editable_svg == second.editable_svg
                     and first.evidence == second.evidence and first.issues == second.issues)
    if not deterministic:
        raise AssertionError(f"Geometry/evidence changed between runs: {case['id']}")
    directory = destination / case["id"]
    directory.mkdir(parents=True, exist_ok=True)
    svg = directory / "editable.svg"
    svg.write_bytes(first.editable_svg)
    write_json(directory / "document.json", first.document.model_dump(mode="json"))
    detail = {
        "input_sha256": inputs[2].sha256, "source": "synthetic_fixture",
        "analysis_provider_used": None, "duration_ms": first.duration_ms,
        "method_evidence": first.evidence, "deterministic_except_duration": deterministic,
        "issues": [issue.model_dump(mode="json") for issue in first.issues],
    }
    if inkscape:
        detail["preview"] = render_preview(inkscape, svg, directory / "preview.png")
    write_json(directory / "evidence.json", detail)
    return {
        "case": case["id"], "input_sha256": inputs[2].sha256,
        "document_sha256": sha((directory / "document.json").read_bytes()),
        "editable_svg_sha256": sha(first.editable_svg), "object_count": len(first.document.objects),
        "work_color_count": len({obj.work_color for obj in first.document.objects}),
        "object_bounds_mm": first.document.object_bounds_mm.model_dump(),
        "duration_ms": first.duration_ms, "deterministic_except_duration": deterministic,
        "issue_codes": sorted({issue.code.value for issue in first.issues}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/fixtures/h2/manifest.json")
    parser.add_argument("--case", action="append", required=True, dest="cases")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inkscape", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in manifest["images"]}
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {
        "scope": "E1 smoke on selected flat raster fixtures; not evaluation F",
        "python": platform.python_version(), "pillow": pillow_version,
        "schema_version": "0.1", "digital_readiness_evaluated": False,
        "physical_approval": "untested", "jef_generated": False,
        "cases": [record_case(cases[name], args.manifest.parent, args.output, args.inkscape)
                  for name in args.cases],
    }
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
