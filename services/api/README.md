# API H0-04: servicio HTTP y worker real

Propósito: exponer los contratos v0.1 con FastAPI, ejecutar el worker Ink/Stitch en background y entregar artefactos autorizados.

Contenido: [Generación](#generacion), [Operaciones](#operaciones), [Límites](#limites), [Evidencia](#evidencia), [Relacionados](#relacionados).

## Generación

- Python 3.12+ con `requirements.txt`; el entorno verificado usa Python 3.14.4.
- OpenAPI: `python services/api/build_openapi.py` desde la raíz.
- API: `python -m embroidery_api.main` con `EMBROIDERY_API_CONFIG` apuntando a un JSON privado.
- Pruebas: `python -m unittest discover -s tests/engine -p "test_*.py"`.
- Configuración privada: rutas de Python, Ink/Stitch, Inkscape, clave HMAC, credenciales y límites. Los ejecutables no son entradas HTTP.

## Operaciones

| Método/ruta (prefijo /api/v1) | Éxito |
|---|---|
| POST /projects | 201 ProjectResponse |
| GET /projects | 200 ProjectList paginado |
| GET /projects/{id} | 200 ProjectDetail; assets/jobs con cursores |
| GET /profiles | 200 ProfileCatalog |
| POST /projects/{id}/assets | 201 SourceAsset; multipart file |
| POST /projects/{id}/revisions | 201 inicial; 202 variante/corrección en H1 |
| GET /projects/{id}/revisions | 200 RevisionList paginado |
| POST /projects/{id}/jobs | 202 JobResponse queued |
| GET /jobs/{id} | 200 JobResponse observado |
| GET /jobs/{id}/artifacts | 200 AuthorizedArtifactManifest solo en needs_review/ready_for_sewout; 409 en el resto |
| POST /jobs/{id}/cancel | 202 siempre, incluso terminal |
| GET /jobs/{id}/analysis | 200 `AnalysisSpec` del job o, en una continuación, el aprobado de su padre; 404 si no hay |
| POST /jobs/{id}/analysis-decision | 202 `JobResponse` nuevo (`approve` o `change_provider`); 409 si el job no espera la decisión; 422 si no es válida |
| POST /projects/{id}/sewouts | 201 SewoutResponse |

`GET /jobs/{id}/artifacts` vuelve a firmar URLs TTL 300 s. La regla de estados es deliberada: `queued`, `digitizing`, `validating`, `failed` y `cancelled` devuelven `ARTIFACTS_UNAVAILABLE` aunque exista un manifiesto antiguo.

## Límites

- BasicAuth O ServiceBearer opaco, sin OAuth. H1 valida usuario/propiedad de IDs, revisiones y descargas.
- Todo POST requiere `Idempotency-Key`; mismo contenido lógico y ámbito repite status/body. Otro contenido devuelve 409.
- `MAX_UPLOAD_BYTES` y `MAX_IMAGE_PIXELS` se aplican antes de procesar. Formatos PNG/JPEG/SVG; SVG rechaza DTD, entidades, `script` y `foreignObject`.
- Descargas: TTL 300 s/UTC, `no-store`, HMAC, propietario, job, artefacto, SHA-256 y confinamiento al directorio del job.
- Cancelación 202 confirma petición, no parada. El runner detiene el árbol de procesos antes de `cancelled`; un job terminal conserva su estado.
- `prepared_svg` y revisiones iniciales; la cola es de un proceso con SQLite. H1 aporta persistencia y concurrencia.
- H2: una imagen PNG/JPEG (`raster_image`) se analiza con el proveedor configurado y queda en `needs_review` si hay una región incoherente; `approve` sigue en una continuación y `change_provider` crea una revisión `analysis_retry`. **La vectorización todavía no existe**: un análisis sin dudas, o su continuación, termina en `failed` con `WORKER_EXPORT_FAILED` y motivo `vectorization_not_implemented`. Sin pruebas contra un proveedor real.

## Evidencia

La ejecución real con Ink/Stitch v3.2.2 está en [evidence/h0-04](evidence/h0-04/README.md): 202 en 7.65 ms, `needs_review` en 16.7 s, 6 artefactos con hash coincidente, 0 errores bloqueantes y 14 avisos.

## Relacionados

[OpenAPI](../../packages/contracts/openapi.json), [contratos](../../packages/contracts/README.md), [incidencias](../../packages/contracts/incidences.md), [worker](../../workers/embroidery/README.md).
