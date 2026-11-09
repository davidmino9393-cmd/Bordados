# Ronda 5 — técnicas por ancho

Propósito: evidencia medida del commit `5dfd8aa1d915acd511d0f5ac41f2404508a398ab`, base `bf91e6f`. Main sigue `b1ce70c`, sin actualizar.

Contenido: [Resultados](#resultados), [Caso real](#caso-real), [Límites](#límites), [Repro](#repro), [Referencias](#referencias).

## Resultados

| Control | Medición fresca |
|---|---|
| Motor completo | 196: 192 aprobadas, 4 omitidas; 0 errores/fallos; 78,024 s; exit 0 |
| F | passed, 14 raster/2 SVG omitidos; 8 checks 14/14; per_logo_literals=[] |
| F tiempos | 28 ejecuciones, mediana 2177,5 ms, máximo 13296 ms |
| Fixtures 0,3/0,5/0,8 mm | Corrida central, sin auto_fill ni compensación |
| Fixture 1,5 mm | Fallback relleno, filas 0,35 mm, compensación 0,2 mm; satén pendiente |
| Fixture 3 mm | Relleno, filas 0,45 mm, compensación 0,2 mm |
| 1,25 mm² | Omitido con área y aviso; bloque vacío sintético rechazado |

## Caso real

Copia ignorada de `job_c934f8b296d64d59b4547806295c6a26/digitizing/input.svg`; originales intactos. Anillos finos: corrida sin compensación; residuo de color de 1,2462 mm² omitido. SVG: {'fill': 2, 'running': 1}. E1 conserva `path_data_mm`; distribución por objeto/anillo y tamaños mínimos en [mediciones](measurements.json).

JEF nuevo: **8627 puntadas**, 1 hilo, 0 cambios; puntadas por bloque [8627]; 111.00 × 111.40 mm. SHA en [estado](status.json). Avisos nativos conservados en [worker](worker-result.json).

Discrepancia auditada: la lectura binaria fresca del JEF original SHA `5fda3c1d…c0246` cuenta bloques **[7870,75]**, no un segundo bloque vacío. [Antes](before.json): tamaño 111 × 111,6 mm; expansión por lado 0,278/0,2915 mm.

## Límites

Satén con rieles verificados pendiente; fallback autorizado. Apertura cuadrada por área ≠ erosión por distancia de la auditoría; sesgo diagonal hasta √2. Ancho bordable provisional: 0,4 mm, sin alterar thin_features. H3 con David; sin calibración ni ready_for_sewout. Checker, stitchable.plan, _fill_attributes y build_openapi.py intactos (40000000). Sin dependencias nuevas. El intento inicial agotó 240 s; el job histórico tardó 335 s. Ver tiempos finales del worker; límite de producción intacto.

## Repro

Mismo Python/PYTHONPATH de integración ronda B. `python -B -m unittest discover -s tests/engine -p 'test_*.py' -v`; `python -B tests/h2_eval/run_eval.py --worker-path workers/embroidery --out LOCAL.json`. Caso local: `python -B tests/engine/round5_evidence.py --job-dir JOB --out TMP_NUEVO --inkstitch EXE`.

## Referencias

[Motor](motor.log) · [F completo](F.json) · [Técnicas](../../../../workers/embroidery/vectorize/REFERENCE_TECHNIQUES.md)
