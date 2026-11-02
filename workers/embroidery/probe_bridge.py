"""Probe an unmodified, externally supplied Bridge checkout; never edits inputs."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import sys


def main():
    parser = argparse.ArgumentParser()
    for name in ("bridge-root", "inkstitch-root", "engine-python", "svg", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    source = args.out / "input.svg"
    shutil.copyfile(args.svg, source)
    os.environ.update(INKSTITCH_MCP_ROOT=str(args.bridge_root.resolve()),
                      INKSTITCH_MCP_REPO=str(args.inkstitch_root.resolve()),
                      INKSTITCH_MCP_PYTHON=str(args.engine_python.resolve()))
    sys.path.insert(0, str(args.bridge_root.resolve() / "src"))
    bridge = importlib.import_module("inkstitch_mcp")
    runner = importlib.import_module("inkstitch_mcp.runner")
    rc, payload, stderr = runner.run_raw("output", ["--format=jef"], source, timeout=60)
    (args.out / "stdout.bin").write_bytes(payload)
    (args.out / "stderr.txt").write_bytes(stderr.encode("utf-8"))
    result = {"route": "inkstitch_mcp.runner.run_raw", "bridge_version": bridge.__version__,
              "engine_python": str(args.engine_python.resolve()),
              "inkstitch_checkout": str(args.inkstitch_root.resolve()),
              "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "toolchain_path_problems": runner.check_toolchain(),
              "returncode": rc, "payload_bytes": len(payload), "stderr": stderr,
              "mcp_protocol_exercised": False, "export_succeeded": rc == 0 and bool(payload)}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["export_succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
