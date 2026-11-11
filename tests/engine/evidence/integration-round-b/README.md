# Integración ronda B — main real integrado

Propósito: verificar el merge de main en codex/motor. Fecha: 2026-11-08, ronda 4, intento 4.

Contenido: [Identidad](#identidad), [Resultados](#resultados), [Límites](#límites), [Repro](#repro), [Referencias](#referencias).

## Identidad

| Elemento | SHA |
|---|---|
| main confirmado, no actualizado por Codex | `b1ce70ca06d06b81e35c8becfefecac5e40412c9` |
| motor antes del merge | `66b943a38b24a08502e851795742eeb5eb12010d` |
| merge probado en codex/motor | `fd39dbdf4cf7d68e63dbb9afa11c21af051ef6e1` |
| árbol probado | `d14cf1ea8bdc8eb94a24a1dd4e4273b9add6adad` |

Merge real sin conflictos. Main posterior confirmado; main_updated_by_codex=false. Commit posterior separado: solamente estas tres evidencias.

## Resultados

| Control sobre el merge | Medición fresca |
|---|---|
| Motor completo, exit 0 | 186 totales: 182 aprobadas, 4 omitidas; 0 fallos, 0 errores; 49,748 s |
| F, passed / exit 0 | 16 imágenes: 14 raster medidos, 2 SVG omitidos; 0 errores; ocho checks 14/14; per_logo_literals=[] |
| F tiempos | 28 ejecuciones; mediana 1262 ms, máximo 4352 ms |
| F IoU | 14/14 medidos; mínimo 0.699623, mediana 0.9886705 |

Resumen fresco y SHA256 del F local: [status.json](status.json). Informe completo: `tests/engine/.tmp/r4deps/F.json` (ignorado). F no mide holes_preserved_as_count, text_as_annotation ni background_assumption.

Los demás JSON/logs de esta carpeta son históricos del árbol `8e57b556bcd2e198699283b80574329f90aa56ed` (2026-11-03). Incluyen F.json, motor.log, h2_eval.log y auditorías API/JEF; no son nuevas mediciones sobre este merge.

## Límites

`services/api/build_openapi.py:286` conserva `40000000`, sin editar. H3/calibración física pendiente con David; sin marcar ready_for_sewout. La integración de consumo del helper API/EXIF requiere seguimiento del dueño API; esta ronda no la certifica.

## Repro

En el merge indicado, desde `C:\dev\wt-motor`:

```powershell
$py='C:\Users\david\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH='C:\dev\wt-motor\services\api;C:\dev\wt-motor\workers\embroidery;C:\dev\wt-motor\tests\engine\.tmp\r4deps\api;C:\dev\wt-motor\tests\engine\.tmp\r4deps\embroidery'
& $py -B -m unittest discover -s tests/engine -p 'test_*.py' -q
& $py -B tests/h2_eval/run_eval.py --worker-path workers/embroidery --out tests/engine/.tmp\r4deps\F.json
```

## Referencias

- [Preparación](preparation.json) · [Estado y resultados frescos](status.json)
- Históricos: [F](F.json) · [Motor](motor.log) · [h2_eval](h2_eval.log) · [API](audit-api.json) · [JEF](jef-hashes.json)
- [Medición20MP](../image-input/README.md) · [Control rojo/verde](../reference-profile-neutral/README.md)
