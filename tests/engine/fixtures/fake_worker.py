"""Deterministic worker used by API integration tests; it never runs Ink/Stitch."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "workers" / "embroidery" / "evidence" / "cli-main-final"
ARTIFACTS = ("output.jef", "preview.png", "raw-commands.json")


def write_result(job_dir, result):
    (job_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--svg", required=True, type=Path)
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--inkstitch", required=True, type=Path)
    parser.add_argument("--inkscape", type=Path)
    parser.add_argument("--engine-version", required=True)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--jef-hoop-code", type=int)
    args = parser.parse_args()

    job_dir = args.job_dir.resolve()
    job_dir.mkdir(parents=True, exist_ok=False)
    data = args.svg.read_bytes()
    (job_dir / "input.svg").write_bytes(data)

    if b"FAKE_FAIL" in data:
        write_result(job_dir, {
            "ok": False,
            "issue": {
                "code": "INPUT_UNREADABLE",
                "reason": "fake_invalid_input",
                "evidence": {"message": "deterministic fake failure"},
            },
            "digital_readiness_evaluated": False,
        })
        return 1

    if b"FAKE_SLEEP" in data:
        time.sleep(5)

    for name in ARTIFACTS:
        shutil.copyfile(EVIDENCE / name, job_dir / name)
    result = json.loads((EVIDENCE / "result.json").read_text(encoding="utf-8"))
    result["input_sha256"] = hashlib.sha256(data).hexdigest()
    result["processes"] = []
    write_result(job_dir, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
