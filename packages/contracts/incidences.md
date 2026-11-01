# Incidencias y errores v0.1

Propósito: catálogo concreto pendiente de revisión humana. Fuente ejecutable: `embroidery_contracts/issues.py`; exportación versionada: `issue-catalog.json`.

Contenido: [Clasificación](#clasificacion), [reglas](#reglas), [HTTP](#http), [relacionados](#relacionados).

## Clasificacion

| Severidad | Consecuencia digital |
|---|---|
| blocking_error | Detener; no ready_for_sewout |
| review_required | Corrección/revisión localizada; no ready_for_sewout |
| info | Conservar aviso y evidencia; no autoriza por sí solo |

| Familia | Etapa / casos |
|---|---|
| INPUT_* | input: formato, lectura, límites |
| ANALYSIS_* / PROVIDER_* / LOCAL_MODEL_* | analysis: rechazo, incompleto, esquema, región incoherente, límite, conexión/modelo ausente |
| GEOMETRY_* | geometry: invalidez, reparación ambigua, huecos modificados |
| SATIN_* | satin: raíles, ancho, aviso de guías y nodos correspondientes verificados |
| ROUTING_* / DENSITY_* | routing: precedencias, recorrido visible, densidad por inspeccionar |
| DIMENSIONS_* / HOOP_* | dimensiones físicas y bastidor/código |
| JEF_* | file: integridad y órdenes desconocidas |
| WORKER_* / JOB_CANCELLED | worker: fallo, timeout y cancelación completada |
| VISUAL_MISMATCH / PHYSICAL_ADJUSTMENT_REQUIRED | visual / sewout |

## Reglas

- Cada código fija etapa y severidad. No se rebajan avisos cambiando el texto o mediante una lista global de aceptados.
- Conservar texto crudo, objeto/región, medidas y logs en evidence. Un diagnóstico nativo desconocido se mapea a ENGINE_DIAGNOSTIC_UNCLASSIFIED (review_required); nunca se descarta porque no esté en el enum.
- SATIN_RUNG_WARNING exige revisión. SATIN_PAIRED_NODES_VERIFIED registra evidencia por objeto; no elimina el aviso original. El flujo para resolver revisión debe conservar diagnóstico y decisión en la nueva revisión.
- Densidad es un indicador para inspección calibrada, no prueba de ausencia de fruncido. PHYSICAL_ADJUSTMENT_REQUIRED pertenece al registro físico; no invalida retrospectivamente bytes digitales.
- Fallo local no se transforma silenciosamente en proveedor de nube. Un error HTTP al crear/consultar no equivale a un fallo asíncrono del worker: este último vive en JobResponse/issues.

## HTTP

`application/problem+json`: type URN estable, title/status/detail/instance, code, request_id y errors por campo. El catálogo publica códigos y status 400/401/403/404/409/413/415/422/429/500/503. Los endpoints documentan sus subconjuntos y ejemplos.

## Relacionados

[Catálogo JSON](issue-catalog.json), [OpenAPI](openapi.json), [estados](states.md), [modelos](README.md).
