# API H0: especificación, sin servicio HTTP

Propósito: OpenAPI 3.1.1 desde Pydantic: contratos v0.1 B2 candidatos a congelar. Sin handlers, autenticación ni worker; revisión humana pendiente.

Contenido: [Generación](#generacion), [operaciones](#operaciones), [límites](#limites), [relacionados](#relacionados).

## Generacion

- Python 3.12+ con `requirements.txt`: `python services/api/build_openapi.py` desde la raíz.
- Genera `packages/contracts/openapi.json` e `issue-catalog.json`; orden estable, sin timestamps ni rutas de máquina.
- Comprobación mínima: `python -m unittest discover -s tests/engine -p "test_*.py"`.
- Los ejemplos se validan con los modelos que producen los schemas. Se comprueban referencias y reproducción exacta de los archivos; no se ejecutó un linter externo de OpenAPI.

## Operaciones

| Método/ruta (prefijo /api/v1) | Éxito |
|---|---|
| POST /projects | 201 ProjectResponse |
| GET /projects | 200 ProjectList paginado |
| GET /projects/{id} | 200 ProjectDetail; assets/jobs con cursores |
| GET /profiles | 200 ProfileCatalog |
| POST /projects/{id}/assets | 201 SourceAsset; multipart file |
| POST /projects/{id}/revisions | 201 inicial; 202 variante/corrección con JobResponse |
| GET /projects/{id}/revisions | 200 RevisionList paginado |
| POST /projects/{id}/jobs | 202 JobResponse queued |
| GET /jobs/{id} | 200 JobResponse observado |
| GET /jobs/{id}/artifacts | 200 AuthorizedArtifactManifest; 409 si no disponible |
| POST /jobs/{id}/cancel | 202 siempre, incluso terminal |
| POST /projects/{id}/sewouts | 201 SewoutResponse |

## Limites

- BasicAuth O ServiceBearer opaco, sin OAuth. H1 valida usuario/propiedad de IDs, revisiones y descargas; 401/403/404 según diagnóstico autorizado.
- Todo POST requiere Idempotency-Key; mismo contenido lógico y ámbito usuario/proyecto/operación repite status/body. Otro contenido devuelve 409. H1 define retención y persistencia; multipart compara bytes y metadata, no boundaries.
- MAX_UPLOAD_BYTES y MAX_IMAGE_PIXELS deben configurarse y aplicarse antes de procesamiento. Formatos PNG/JPEG/SVG, SVG sanitizado para visualización y comandos del motor acotados. Un SVG admitido no implica bordado válido.
- Descargas: TTL 300s/UTC, no-store. GET artifacts siempre reautoriza/emite URLs nuevas; seguro e idempotente sobre bytes/identidad, sin exportar. Ver [flujo inicial y renovación](../../packages/contracts/B2-protocol.md).
- Cancelación 202 confirma petición, no parada. El worker debe detener procesos antes de cancelled. Un job terminal conserva estado; ninguna llamada reinicia sus artefactos.

## Relacionados

[OpenAPI](../../packages/contracts/openapi.json), [contratos](../../packages/contracts/README.md), [incidencias](../../packages/contracts/incidences.md).

Fuentes: [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/), [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html).
