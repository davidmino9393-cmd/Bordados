"""Valida el manifiesto del conjunto de imágenes de H2 (solo biblioteca estándar).

Uso:  python validate_manifest.py manifest.json [--check-files]

Comprueba la estructura (manifest.schema.json) y las reglas del plan (PLAN_MAESTRO §9):
15–20 imágenes, las dos escalas de Anime Socks, al menos 5 diseños nuevos distintos
(las variantes de un mismo logo no cuentan), casos que deben pedir revisión, y permiso
de uso confirmado en cada una. Con --check-files verifica que existan y que el SHA-256 coincida.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

CATEGORIES = {"flat_logo", "few_colors_drawing", "line_art", "lettering", "closed_curves_with_holes", "transparency", "expects_review"}
OUTCOMES = {"automatic", "needs_review", "unsupported"}
FORMATS = {"png", "jpeg", "svg"}
ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MIN_IMAGES, MAX_IMAGES, MIN_NEW_DESIGNS, MIN_REVIEW_CASES = 15, 20, 5, 2
REFERENCE_FAMILY = "anime_socks"
REQUIRED = ("id", "file", "design_family", "category", "format", "has_transparency", "contains_text", "expected_colors", "target_size_mm", "expected_outcome", "rights")


def structure_errors(image, index):
    where = f"imágenes[{index}] ({image.get('id', '?')})"
    errors = [f"{where}: falta «{key}»" for key in REQUIRED if key not in image]
    if image.get("id") and not ID.match(str(image["id"])):
        errors.append(f"{where}: id inválido (minúsculas, números, - y _)")
    if image.get("category") not in CATEGORIES:
        errors.append(f"{where}: categoría desconocida ({image.get('category')!r})")
    if image.get("format") not in FORMATS:
        errors.append(f"{where}: formato desconocido ({image.get('format')!r})")
    if image.get("expected_outcome") not in OUTCOMES:
        errors.append(f"{where}: resultado esperado desconocido ({image.get('expected_outcome')!r})")
    if image.get("expected_outcome") == "needs_review" and not image.get("expected_review_reason"):
        errors.append(f"{where}: needs_review exige expected_review_reason")
    if image.get("contains_text") and not image.get("text"):
        errors.append(f"{where}: contains_text exige el texto visible en «text»")
    colors = image.get("expected_colors")
    if not isinstance(colors, int) or not 1 <= colors <= 16:
        errors.append(f"{where}: expected_colors debe ser un entero de 1 a 16")
    file = str(image.get("file", ""))
    if file.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", file) or ".." in Path(file).parts:
        errors.append(f"{where}: «file» debe ser una ruta relativa al manifiesto")
    if "sha256" in image and not SHA.match(str(image["sha256"])):
        errors.append(f"{where}: sha256 inválido")
    return errors


def set_errors(images):
    errors = []
    if not MIN_IMAGES <= len(images) <= MAX_IMAGES:
        errors.append(f"el conjunto debe tener entre {MIN_IMAGES} y {MAX_IMAGES} imágenes (tiene {len(images)})")
    for field in ("id", "file"):
        # las dos escalas de la referencia son el mismo archivo con tamaños objetivo distintos
        values = [i.get(field) for i in images if not (field == "file" and i.get("design_family") == REFERENCE_FAMILY)]
        duplicated = sorted({v for v in values if values.count(v) > 1})
        if duplicated:
            errors.append(f"{field} repetido: {', '.join(map(str, duplicated))}")
    reference = [i for i in images if i.get("design_family") == REFERENCE_FAMILY]
    widths = {round(float(i.get("target_size_mm", {}).get("width_mm", 0))) for i in reference}
    if len(widths) < 2:
        errors.append(f"faltan las dos escalas de {REFERENCE_FAMILY} (tamaños objetivo distintos)")
    families = {i.get("design_family") for i in images} - {REFERENCE_FAMILY}
    if len(families) < MIN_NEW_DESIGNS:
        errors.append(f"hacen falta al menos {MIN_NEW_DESIGNS} diseños nuevos distintos (hay {len(families)}); las variantes de un logo no cuentan")
    if sum(1 for i in images if i.get("expected_outcome") == "needs_review") < MIN_REVIEW_CASES:
        errors.append(f"hacen falta al menos {MIN_REVIEW_CASES} casos que deban pedir revisión")
    for category, label in (("lettering", "letras"), ("line_art", "line art"), ("closed_curves_with_holes", "curvas cerradas con huecos")):
        if not any(i.get("category") == category for i in images):
            errors.append(f"falta al menos una imagen de {label}")
    if not any(i.get("has_transparency") for i in images):
        errors.append("falta al menos una imagen con transparencia")
    missing = [str(i.get("id")) for i in images if not i.get("rights", {}).get("permission_confirmed")]
    if missing:
        errors.append(f"sin permiso de uso confirmado: {', '.join(missing)}")
    return errors


def file_errors(images, base):
    errors = []
    for image in images:
        path = base / str(image.get("file", ""))
        if not path.is_file():
            errors.append(f"{image.get('id')}: no existe {image.get('file')}")
        elif image.get("sha256") and hashlib.sha256(path.read_bytes()).hexdigest() != image["sha256"]:
            errors.append(f"{image.get('id')}: el SHA-256 no coincide con {image.get('file')}")
    return errors


def validate(manifest, base=None):
    if manifest.get("schema_version") != "0.1" or not isinstance(manifest.get("images"), list):
        return ["el manifiesto necesita schema_version «0.1» y una lista «images»"]
    images = [i for i in manifest["images"] if isinstance(i, dict)]
    errors = [e for index, image in enumerate(images) for e in structure_errors(image, index)]
    errors += set_errors(images)
    if base is not None:
        errors += file_errors(images, base)
    return errors


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    path = Path(args[0])
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(manifest, path.parent if "--check-files" in argv else None)
    for error in errors:
        print("✘", error)
    print("✔ el manifiesto cumple las reglas" if not errors else f"{len(errors)} problema(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
