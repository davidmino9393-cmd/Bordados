"""Recheck saved real outputs and original references without running the engine."""
import hashlib
import json
from pathlib import Path
import platform

from jef_audit import binary_commands

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent / "evidence"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_export(job, reference):
    directory = EVIDENCE / job
    report = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    actual_data, original_data = (directory / "output.jef").read_bytes(), (ROOT / reference).read_bytes()
    actual, original = binary_commands(actual_data), binary_commands(original_data)
    assert report["ok"] and actual == original, job
    assert actual_data[116:actual["offset"]] == original_data[116:original["offset"]], "JEF palette changed"
    assert digest(directory / "output.jef") == report["metrics"]["jef_sha256"]
    assert (directory / "preview.png").is_file()
    assert report["digital_readiness_evaluated"] is False
    return {"job": job, "reference": reference, "metrics": report["metrics"],
            "normalized_commands_equal": True, "palette_equal": True,
            "native_diagnostics_retained": len(report["diagnostics"])}


def main():
    refs = json.loads((ROOT / "workers/embroidery/inventory/source-inventory.json").read_text(encoding="utf-8"))["reference_sha256"]
    assert all(digest(ROOT / path) == expected for path, expected in refs.items())
    frozen = json.loads((EVIDENCE / "frozen-contracts.sha256.json").read_text(encoding="utf-8"))
    assert all(digest(ROOT / path) == expected for path, expected in frozen.items())
    exports = [compare_export("cli-main-final", "Anime_Socks_Bordado/Anime_Socks_Optimizado.jef"),
               compare_export("cli-small-final", "Anime_Socks_Bordado_13x12/Anime_Socks_13x12.jef")]
    failures = {}
    for case, code in (("invalid-svg", "INPUT_UNREADABLE"), ("missing-binary", "WORKER_EXPORT_FAILED"),
                       ("timeout-final", "WORKER_TIMEOUT")):
        result = json.loads((EVIDENCE / case / "result.json").read_text(encoding="utf-8"))
        assert not result["ok"] and result["issue"]["code"] == code
        failures[case] = result["issue"]
    assert failures["timeout-final"]["evidence"]["cleanup"]["confirmed"]
    assert failures["timeout-final"]["evidence"]["started_suspended"]
    summary = {"platform": platform.platform(), "original_references_unchanged": len(refs),
               "frozen_contract_files_unchanged": len(frozen), "exports": exports, "controlled_failures": failures,
               "linux_tested": False, "windows_service_session_zero_tested": False,
               "observed_execution": "Windows processes, hidden console, DEVNULL stdin, no desktop interaction"}
    (EVIDENCE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified_exports": len(exports), "originals_intact": len(refs), "frozen_contracts_intact": len(frozen), "controlled_failures": list(failures)}))


if __name__ == "__main__":
    main()
