# Integración temporal — compuerta F pendiente

Propósito: preparar y verificar la combinación sin fusionar ramas. Fecha: 2026-11-03.

Contenido: [Árbol](#árbol), [Resultados](#resultados), [Reproducción](#reproducción), [Límites](#límites), [Referencias](#referencias).

## Árbol

| Elemento | SHA |
|---|---|
| main congelado | `68d7ecdfef23f34e5becd9e5ccb0be9de65244bf` |
| motor probado | `452bd249d765c53d6d4e7155259cff2e47913f73` |
| merge-tree con conflicto documental | `39dc496d0167f93e663d2fd26f577ced2016630b` |
| árbol resuelto y archivado | **`c094fad22189747ec686bf52bcfe61b24b519f03`** |

Único conflicto: `workers/embroidery/vectorize/CONTINUAR.md`. Gana la estructura y relevo actualizado de **Codex**, conservando su revisión de finos y eliminando el estado histórico obsoleto. Se incorporan los hechos posteriores de main: imagen→JEF de referencia y variantes SVG corregidas. [Documento resultante](CONTINUAR.resolved.md).

Se utilizó un índice temporal exclusivo. `preparation.json` verifica referencias e índice real idénticos antes/después. Sin worktrees, checkout, merge sobre refs ni push. El árbol es candidato técnico, no un commit de integración autorizado.

## Resultados

| Comprobación del árbol integrado | Resultado |
|---|---|
| Motor | **182 pruebas**, sin fallos, 4 omitidas; 45,750 s |
| h2_eval | **16 pruebas**, sin fallos, 1 omitida; 0,195 s |
| F real | 16 entradas, 14 raster y 2 SVG omitidos; 0 errores |
| Ocho checks estructurales F | **14/14 cada uno**, incluido determinismo y límites |
| Salida global F | **failed / exit 1** por revisión estática |
| F de main68 aislado | **mismo failed / exit 1**, mismos dos literales y checks 14/14 |

Pendiente de compuerta: `workers/embroidery/vectorize/inkstitch.py:116` contiene `REFERENCE_PROFILE_ID = "anime_socks_gabardina_400ppm"`; F informa dos coincidencias (`Anime_Socks`, `anime_socks`). Ya existe en main: no lo introduce el helper ni la combinación. El informe detecta etiquetas de procedencia de referencia; esta preparación no decide unilateralmente si corresponde ajustar el criterio o el código. No se ocultaron coincidencias ni se alteró el arnés.

**No se da GO de integración con F rojo.** API/web/F son de Claude: se comunicó el caso, con baseline. El consumo API de image_input también sigue pendiente de su integración; el catálogo anuncia 20 Mpx aunque E1 ya comparte 4 Mpx con el helper.

## Reproducción

`prepare.py --repo C:\dev\wt-motor --main <SHA main de la tabla> --motor <SHA motor> --out <carpeta temporal nueva dentro del workspace>` prepara objetos, resolución, archivo y snapshot. Requiere Git, Python estándar y una carpeta nueva; no toca refs ni índice real. Comandos exactos en preparation.json.

Con Python empaquetado, PYTHONDONTWRITEBYTECODE=1 y PYTHONPATH a deps API/worker de motor:

- unittest discover del snapshot: `-s source/tests/engine -p test_*.py -q`.
- unittest discover: `-s source/tests/h2_eval -p test_*.py -q`.
- F: `source/tests/h2_eval/run_eval.py --worker-path <source/workers/embroidery> --out F.json`.
- Baseline: archive de main68, mismo comando F con su propio worker-path.

## Límites

Pruebas del motor incluyen worker falso para casos HTTP; cuatro pruebas opcionales omitidas no se presentan como realizadas. F ejecutó E1 real sobre fixtures sintéticos y referencia PNG; no mide calibración física. Auditorías independent-review/** se conservan conscientemente como artefactos locales con JEF/capturas/trazas; no se empaquetan en el commit del helper.

## Referencias

- [Preparación](preparation.json) · [Motor](engine-tests.log) · [h2_eval](eval-tests.log)
- [F integrado](F.json) · [F baseline main](F-main-baseline.json) · [Script](prepare.py)
