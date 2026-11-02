"""Compare normalized raw command JSON structurally, not byte-for-byte."""
import argparse
import json
from pathlib import Path

IDENTICAL = "ESTRUCTURALMENTE IDENTICOS"


def load_commands(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, list):
        raise ValueError(f"{path} must contain a JSON list")
    return document


def compare_raw_commands(reference, actual, max_differences=10):
    reference_commands = load_commands(reference)
    actual_commands = load_commands(actual)
    common = min(len(reference_commands), len(actual_commands))
    differences = [
        index
        for index in range(common)
        if reference_commands[index] != actual_commands[index]
    ]
    if len(reference_commands) != len(actual_commands):
        differences.append(common)
    first = differences[0] if differences else None
    return {
        "reference_count": len(reference_commands),
        "actual_count": len(actual_commands),
        "difference_count": len(differences),
        "first_difference_index": first,
        "difference_indices": differences[:max_differences],
        "verdict": IDENTICAL if first is None else f"DIFERENCIA EN INDICE {first}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--max-differences", type=int, default=10)
    args = parser.parse_args(argv)
    report = compare_raw_commands(
        args.reference, args.actual, max_differences=args.max_differences
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["verdict"] == IDENTICAL else 1


if __name__ == "__main__":
    raise SystemExit(main())
