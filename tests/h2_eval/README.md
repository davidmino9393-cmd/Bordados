# Evaluación F de H2

Mide el módulo E (`workers/embroidery/vectorize`) sobre `tests/fixtures/h2/manifest.json`. Solo informa lo medido; sin `vectorize` responde `vectorize_not_available` (salida 2).

| Comprobación | Qué mide |
|---|---|
| `document_valid` | El documento vuelve a validar contra `EmbroideryDocument` |
| `within_target_contain` | Límites de objetos dentro del tamaño objetivo (tolerancia 0,01 mm) |
| `colors_within_limit` | Colores distintos ≤ `color_limit` (se usa `expected_colors` del manifiesto) |
| `geometry_kinds_allowed` | Solo `verified_curve` / `verified_mask` |
| `provisional_values_marked` | Convención de E1: cada objeto con `DesignDecision` (`h3_validation_required`), cubierto por una incidencia `DENSITY_REVIEW_REQUIRED` y `evidence.h3_validation_required` |
| `deterministic` | Dos corridas: mismo documento, SVG y evidencia (sin `timings`) |
| Revisión estática | Nombres de archivo, ids y familias del conjunto dentro del código de E |

**Aún no se mide:** IoU contra la máscara, conservación de huecos y texto como anotación (necesitan rasterizar el documento; se agregan cuando exista E). El arnés pasa `AnalysisSpec` sin regiones a propósito: E debe sacar la geometría de los píxeles.

```bash
python tests/h2_eval/run_eval.py --out informe.json      # contra E
python -m unittest discover -s tests/h2_eval -p "test_*.py"   # pruebas del arnés (vectorize falso)
```
