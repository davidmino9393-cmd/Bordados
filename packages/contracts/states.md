# Estados digitales v0.1

Propósito: tabla de transiciones de contratos v0.1 congelados, implementada en `embroidery_contracts/states.py`.

Contenido: [Tabla](#tabla), [guardas](#guardas), [relacionados](#relacionados).

## Tabla

| Desde | Siguiente etapa normal | Interrupciones |
|---|---|---|
| queued | analyzing; vectorizing solo para una imagen con el análisis omitido (ver guardas); digitizing solo para SVG preparado | needs_review, failed, cancelled |
| analyzing | vectorizing | needs_review, failed, cancelled |
| vectorizing | digitizing | needs_review, failed, cancelled |
| digitizing | validating | needs_review, failed, cancelled |
| validating | ready_for_sewout | needs_review, failed, cancelled |
| ready_for_sewout | Ninguna | Ninguna |
| needs_review | Ninguna: corrección crea otra revisión/job | Ninguna |
| failed | Ninguna: nuevo intento separado | Ninguna |
| cancelled | Ninguna: nuevo intento separado | Ninguna |

## Guardas

- Revisión → jobs es 1:N. Fallo, reintento o regeneración pueden crear otro job sobre la misma revisión, sin modificarla. Identidad, entrada, ajustes y artefactos terminados de cada job son inmutables; sus estados sí avanzan por esta tabla. Nunca sobrescribir resultados anteriores. Correcciones de geometría/ajustes requieren otra revisión.
- `validate_transition(previous, following)` valida la arista y conserva job/proyecto/revisión/asset/tipo de entrada/ajustes. No es un endpoint para asignar estado desde el cliente.
- Salto queued→digitizing: solo prepared_svg, con analyzing y vectorizing registrados como skipped y motivo explícito.
- Salto queued→vectorizing: solo `raster_image`, con `analyzing` registrado como `skipped` y motivo explícito, y por una de dos vías: (a) continuación de un análisis aprobado, con `parent_job_id`; o (b) imagen enviada con `settings_snapshot.ai_provider = none`, sin padre: la persona eligió procesar sin análisis de IA (`JobCreate` ya no rechaza ese caso). Cualquier otra imagen empieza por `analyzing`.
- Una imagen que llega a `digitizing` (`raster_digitizing`) pasa por `vectorizing → digitizing` y termina en `needs_review` con el JEF y sus avisos: `ready_for_sewout` sigue exigiendo las comprobaciones de la guarda correspondiente.
- `needs_review`: al menos una incidencia review_required vinculada a objetos o regiones.
- `failed`: al menos una incidencia blocking_error con diagnóstico controlado; no basta una lista vacía o informativa.
- `ready_for_sewout`: digitizing/validating completados; reporte aprobado; checks de archivo, dimensiones, bastidor, geometría, satin y recorrido; métricas releídas coincidentes con manifest y misma procedencia.
- No se permiten errores/revisiones pendientes en un resultado listo. Se requieren SVG editable/InkStitch, JEF, preview releída y reporte. El worker comprobará los archivos reales antes de construir esta respuesta.
- `cancellation_requested=true` solo confirma solicitud. El servidor publica cancelled cuando haya detenido los procesos; un terminal no vuelve a correr por recibir cancelación.
- Una cancelación aceptada (202) no se pierde: guardar el resultado del worker y registrar la solicitud releen el job y escriben en la misma transacción (`Store.mutate`). Si la solicitud ya estaba cuando llega el resultado, este se descarta (sin manifiesto, informe ni incidencias) y el job queda `cancelled` con `cancellation_requested=true`, `GET /artifacts` en 409. Si el job ya había llegado a un estado final, la cancelación no lo toca.
- StageRecord incluye resultados observados y duración medida opcional. No hay porcentajes ni ETA inventados.
- Physical status (`untested`, `approved`, `needs_adjustment`) vive en SewoutRecord y no tiene transiciones sobre JobStatus.

## Relacionados

[Modelos](README.md), [fixtures](fixtures/README.md), [máquina ejecutable](embroidery_contracts/states.py).
