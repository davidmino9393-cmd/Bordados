# Estados digitales v0.1

Propósito: tabla de transiciones implementada en `embroidery_contracts/states.py`, pendiente de revisión humana.

Contenido: [Tabla](#tabla), [guardas](#guardas), [relacionados](#relacionados).

## Tabla

| Desde | Siguiente etapa normal | Interrupciones |
|---|---|---|
| queued | analyzing; digitizing solo para SVG preparado | needs_review, failed, cancelled |
| analyzing | vectorizing | needs_review, failed, cancelled |
| vectorizing | digitizing | needs_review, failed, cancelled |
| digitizing | validating | needs_review, failed, cancelled |
| validating | ready_for_sewout | needs_review, failed, cancelled |
| ready_for_sewout | Ninguna | Ninguna |
| needs_review | Ninguna: corrección crea otra revisión/job | Ninguna |
| failed | Ninguna: nuevo intento separado | Ninguna |
| cancelled | Ninguna: nuevo intento separado | Ninguna |

## Guardas

- `validate_transition(previous, following)` valida la arista y conserva job/proyecto/revisión/asset/tipo de entrada/ajustes. No es un endpoint para asignar estado desde el cliente.
- Salto queued→digitizing: solo prepared_svg, con analyzing y vectorizing registrados como skipped y motivo explícito.
- `needs_review`: al menos una incidencia review_required vinculada a objetos o regiones.
- `failed`: al menos una incidencia blocking_error con diagnóstico controlado; no basta una lista vacía o informativa.
- `ready_for_sewout`: digitizing/validating completados; reporte aprobado; checks de archivo, dimensiones, bastidor, geometría, satin y recorrido; métricas releídas coincidentes con manifest y misma procedencia.
- No se permiten errores/revisiones pendientes en un resultado listo. Se requieren referencias JEF, preview derivada de JEF y reporte. El worker comprobará los archivos reales antes de construir esta respuesta.
- `cancellation_requested=true` solo confirma solicitud. El servidor publica cancelled cuando haya detenido los procesos; un terminal no vuelve a correr por recibir cancelación.
- StageRecord incluye resultados observados y duración medida opcional. No hay porcentajes ni ETA inventados.
- Physical status (`untested`, `approved`, `needs_adjustment`) vive en SewoutRecord y no tiene transiciones sobre JobStatus.

## Relacionados

[Modelos](README.md), [fixtures](fixtures/README.md), [máquina ejecutable](embroidery_contracts/states.py).
