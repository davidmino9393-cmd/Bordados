# Integración ronda B — árbol candidato verde, main pendiente

Propósito: verificar la combinación propuesta sin mover main. Fecha: 2026-11-03.

Contenido: [Identidad](#identidad), [Resultados](#resultados), [Límites](#límites), [Repro](#repro), [Referencias](#referencias).

## Identidad

| Elemento | SHA |
|---|---|
| main observado, no modificado por Codex | `68d7ecdfef23f34e5becd9e5ccb0be9de65244bf` |
| candidato posterior auditado | `e42645661d3c51c4ce3181c289e4871319d5e0c4` |
| motor probado | `96695e47b74c564fe1b7e4969e66bd4a6869a48f` |
| merge-tree / árbol archivado | **`8e57b556bcd2e198699283b80574329f90aa56ed`** |

Sin conflictos en este merge-tree. CONTINUAR.md conserva la resolución ya commiteada en el merge autorizado de main68 hacia motor: estructura y revisión Codex, con los hechos de main. No se efectuó otro merge en ramas ni se creó worktree.

**GO técnico para este árbol candidato.** La Orden 5 no se declara cerrada contra el main posterior: sigue pendiente recibir/verificar ese hash. El pedido posterior de un buzón para mover main contradice la última instrucción directa de David («No tocar main»); Codex conservó la restricción. Si main pasa exactamente a e426456, el árbol de esta tabla es reproducible con ese hash; si pasa a otro hash, se debe preparar el nuevo delta antes de extender este GO.

## Resultados

- Motor completo del archive: **186 pruebas sin fallos**, 4 omitidas, 54,702 s.
- h2_eval: **16 sin fallos**, 1 omitida, 0,135 s.
- F real: **passed / exit0**, 14 raster y 2 SVG omitidos, cero errores, cero per_logo_literals, ocho checks 14/14.
- Repro API/JEF repetido sobre el archive: GO. Base 20×20 sin escalado con límites 20/40; límite10 falla controlado. Cadena A40→B10 desde el original: 40×39,6 mm/1388 STITCH y 10×10/135 STITCH. Orígenes inmutables, replay sin leer/ajustar y dos rechazos422 sin recursos nuevos.

Los SHA completos del SVG visto por el worker, medidas y STITCH están en audit-api.json. Input original `99c8c4a1450ebc2441e28247e7b45fb64d528109fd44160608bcb90b7cfcd321`; A `64f869f27bb0b76fd42e2f3640a8dc2990b087099d3b70dddf8428feab30fce1`; B `8c552697b9ea4493046987e4402c64ab8780eaf91242359a85c3caa15008c4f9`.

JEF de base, A y B reabiertos otra vez con pyembroidery, verificando dimensiones y STITCH independientemente del JSON del worker: [hashes y medidas](jef-hashes.json). No se agregan los archivos JEF al repositorio.

## Límites

Helper/E1 y catálogo API coinciden ahora en **20 MP**, bytes **10 MiB**. Consumo API del helper para EXIF/dimensiones visuales pendiente de Claude. El ejemplo de build_openapi.py aún anuncia 40 MP; se comunicó al dueño API. El presente GO no afirma que esa integración de consumo esté realizada ni que el ejemplo esté corregido.

Las mediciones de 20 MP justifican tiempo/memoria observados; no garantizan cualquier imagen. La referencia ampliada excede 500000 aristas y se rechaza controladamente. La guarda y parámetros físicos se conservaron. Sin calibración física ni ready_for_sewout.

## Repro

```powershell
git merge-tree --write-tree e42645661d3c51c4ce3181c289e4871319d5e0c4 96695e47b74c564fe1b7e4969e66bd4a6869a48f
git archive --format=zip --output=<temporal>/source.zip 8e57b556bcd2e198699283b80574329f90aa56ed
```

Extraer dentro del workspace; Python empaquetado -B, PYTHONDONTWRITEBYTECODE=1 y PYTHONPATH a deps API/worker. Ejecutar unittest discover de source/tests/engine y source/tests/h2_eval. F: source/tests/h2_eval/run_eval.py --worker-path <source/workers/embroidery> --out F.json. El repro API local de e426 se repitió junto al nuevo source en .tmp/integration-round-b/audit_api.py; no modifica el candidato.

Versionados solamente README/JSON/logs; JEF, SVG, PNG y archivos ZIP permanecen locales. Los JEF se releyeron con pyembroidery real; las cuatro regresiones incluidas en el repro usan su worker falso rotulado. La medición de base/cadena/422 usó Ink/Stitch real.

## Referencias

- [Preparación](preparation.json) · [Estado de refs](status.json) · [F](F.json)
- [Motor](motor.log) · [h2_eval](h2_eval.log) · [JEF/API](audit-api.json) · [Log](jef-audit.log)
- [Medición20MP](../image-input/README.md) · [Control rojo/verde](../reference-profile-neutral/README.md)
