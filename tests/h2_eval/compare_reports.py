"""Compara dos informes de run_eval.py (p. ej. dos variantes de E sobre el mismo conjunto) y arma la tabla en Markdown.

Uso:  python tests/h2_eval/compare_reports.py base.json candidato.json [--names base candidato]
Solo muestra lo medido: mejora/empata/empeora se decide por la fracción de píxeles con error de canal grande.
"""
import argparse
import json
from pathlib import Path

TIE_TOLERANCE = 1e-6


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare(base, candidate, names=("base", "candidato")):
    rows, verdicts = [], {"mejora": 0, "empata": 0, "empeora": 0}
    candidate_by_id = {image["id"]: image for image in candidate["images"]}
    for image in base["images"]:
        other = candidate_by_id.get(image["id"])
        if image["status"] != "ok" or not other or other["status"] != "ok":
            continue
        a, b = image["fidelity"], other["fidelity"]
        delta = b["large_error_fraction"] - a["large_error_fraction"]
        verdict = "mejora" if delta < -TIE_TOLERANCE else "empeora" if delta > TIE_TOLERANCE else "empata"
        verdicts[verdict] += 1
        rows.append(
            f"| {image['id']} | {a['large_error_fraction']:.4f} | {b['large_error_fraction']:.4f} | {a['p95_max_channel_error']} | "
            f"{b['p95_max_channel_error']} | {a['mean_abs_rgb_error']:.2f} | {b['mean_abs_rgb_error']:.2f} | {image['objects']} / {other['objects']} | {verdict} |"
        )
    first, second = names
    header = (
        f"| Imagen | Píxeles con error ≥ 64 ({first}) | ({second}) | p95 ({first}) | p95 ({second}) | Error medio ({first}) | "
        f"({second}) | Objetos | Resultado |\n|---|---:|---:|---:|---:|---:|---:|---|---|"
    )
    durations = {
        name: report["summary"].get("duration_ms", {}) for name, report in zip(names, (base, candidate))
    }
    footer = (
        f"\nMejora {verdicts['mejora']}, empata {verdicts['empata']}, empeora {verdicts['empeora']}. "
        + "; ".join(f"{name}: mediana {d.get('median')} ms, máximo {d.get('max')} ms" for name, d in durations.items())
    )
    return header + "\n" + "\n".join(rows) + "\n" + footer


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("candidate")
    parser.add_argument("--names", nargs=2, default=["base", "candidato"])
    args = parser.parse_args(argv)
    print(compare(load(args.base), load(args.candidate), tuple(args.names)))


if __name__ == "__main__":
    main()
