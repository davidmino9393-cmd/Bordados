"""Compara la topología de dos variantes de E (base y candidato) frente a la del original.

Dos mediciones, ambas independientes de la paleta que elija cada variante:
1. Por capa de color (lo que informó Codex): huecos de cada color, con su área. Muestra si la baja de huecos es ruido.
2. Estructura frente al original: componentes y huecos de los trazos oscuros (luminancia < umbral) del ORIGINAL contra los
   del redibujado de cada variante. Si una variante pierde un contorno interior (p. ej. la panza de una letra), acá se ve.

Uso:  python tests/h2_eval/topology_report.py --base RUTA/workers/embroidery --candidate RUTA/workers/embroidery --out informe.json [--only ID ...]
"""
import argparse
import io
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(HERE))

import fidelity  # noqa: E402
import run_eval  # noqa: E402
import topology  # noqa: E402
from PIL import Image  # noqa: E402

DEFAULT_CASES = ("anime-socks-150", "dificil-degradado-01", "jpeg-simple-01", "dificil-texto-chico-01", "logo-escudo-01", "letras-nova-01")
MANIFEST = ROOT / "tests" / "fixtures" / "h2" / "manifest.json"


def load_vectorize(worker_path):
    for name in [m for m in sys.modules if m == "vectorize" or m.startswith("vectorize.")]:
        del sys.modules[name]
    sys.path.insert(0, str(Path(worker_path).resolve()))
    try:
        from vectorize import vectorize  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    return vectorize


def layers(document, size):
    """Una máscara por objeto y el redibujado RGB completo."""
    a, b, c, d, e, f = fidelity.inverse_affine(document.coordinates.source_px_to_mm)
    canvas = Image.new("RGB", size, (255, 255, 255))
    masks = []
    for obj in document.objects:
        polygons = [[(a * x + c * y + e, b * x + d * y + f) for x, y in p] for p in fidelity.subpaths(obj.path_data_mm)]
        mask = fidelity.fill_even_odd(polygons, *size)
        canvas.paste(fidelity.hex_to_rgb(obj.work_color), mask=mask)
        masks.append((obj.work_color, mask))
    return masks, canvas


def structure(image):
    return {f"luma<{t}": topology.summary(topology.topology(topology.dark_mask(image, t))) for t in topology.DARK_LUMA_THRESHOLDS}


def evaluate_variant(vectorize_fn, entry, data, asset, settings, analysis, size):
    result = vectorize_fn(data, asset.media_type, asset, analysis, settings, job_id="job_topology", revision_id="revision_topology")
    masks, canvas = layers(result.document, size)
    per_layer = {color: topology.summary(topology.topology(mask)) for color, mask in masks}
    return {
        "palette": [color for color, _ in masks],
        "per_layer": per_layer,
        "holes_all_layers": {key: sum(layer["holes"][key] for layer in per_layer.values()) for key in next(iter(per_layer.values()))["holes"]},
        "structure": structure(canvas),
    }


def _triple(shape):
    return f"{shape['components']['>=16px']} / {shape['holes']['>=16px']} / {shape['holes']['>=64px']}"


def to_markdown(report, names=("base", "candidato")):
    """Tablas del informe: huecos por capa y estructura frente al original (componentes ≥ 16 px / huecos ≥ 16 px / huecos ≥ 64 px)."""
    lines = []
    for case_id, case in report["cases"].items():
        first, second = (case["variants"][name] for name in names)
        lines += [f"### {case_id}", "", f"Paletas: {names[0]} {', '.join(first['palette'])}; {names[1]} {', '.join(second['palette'])}.", "",
                  f"Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): {names[0]} {first['holes_all_layers']['>=1px']} / {first['holes_all_layers']['>=16px']} / "
                  f"{first['holes_all_layers']['>=64px']}; {names[1]} {second['holes_all_layers']['>=1px']} / {second['holes_all_layers']['>=16px']} / "
                  f"{second['holes_all_layers']['>=64px']}.", "",
                  f"| Trazos con luminancia menor a | Original | {names[0]} | {names[1]} |", "|---|---|---|---|"]
        for threshold, original in case["original_structure"].items():
            lines.append(f"| {threshold.split('<')[1]} | {_triple(original)} | {_triple(first['structure'][threshold])} | {_triple(second['structure'][threshold])} |")
        lines.append("")
    return chr(10).join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--out")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--markdown", help="además del JSON, escribe las tablas en este archivo")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    variants = {"base": load_vectorize(args.base), "candidato": None}
    report = {"cases": {}}
    wanted = set(args.only) if args.only else set(DEFAULT_CASES)
    for entry in manifest["images"]:
        if entry["id"] not in wanted or entry["format"] == "svg":
            continue
        data, asset, settings, analysis = run_eval.build_inputs(entry, MANIFEST.parent)
        original = Image.open(io.BytesIO(data)).convert("RGB")
        case = {"original_structure": structure(original), "variants": {}}
        for name, path in (("base", args.base), ("candidato", args.candidate)):
            case["variants"][name] = evaluate_variant(load_vectorize(path), entry, data, asset, settings, analysis, original.size)
        report["cases"][entry["id"]] = case
        print("medido", entry["id"], file=sys.stderr)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
