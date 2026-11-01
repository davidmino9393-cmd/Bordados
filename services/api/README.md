# API H0: especificación, sin servicio HTTP

Propósito: generar OpenAPI 3.1.1 a partir de los modelos Pydantic. Propuesta v0.1 pendiente de revisión humana; handlers, autenticación y worker se implementarán en H1.

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
| POST /projects/{id}/assets | 201 SourceAsset; multipart file |
| POST /projects/{id}/revisions | 201 RevisionResponse |
| POST /projects/{id}/jobs | 202 JobResponse queued |
| GET /jobs/{id} | 200 JobResponse observado |
| GET /jobs/{id}/artifacts | 200 ArtifactManifest; 409 si no disponible |
| POST /jobs/{id}/cancel | 202 solicitud; 200 si ya terminal |
| POST /projects/{id}/sewouts | 201 SewoutResponse |

## Limites

- Bearer opaco: mecanismo/proveedor de sesión no fijado aquí. H1 comprueba usuario y pertenencia de todos los IDs, revisiones y descargas; 401/403/404 según diagnóstico autorizado.
- Todo POST requiere Idempotency-Key; mismo contenido lógico y ámbito usuario/proyecto/operación repite status/body. Otro contenido devuelve 409. H1 define retención y persistencia; multipart compara bytes y metadata, no boundaries.
- MAX_UPLOAD_BYTES y MAX_IMAGE_PIXELS deben configurarse y aplicarse antes de procesamiento. Formatos PNG/JPEG/SVG, SVG sanitizado para visualización y comandos del motor acotados. Un SVG admitido no implica bordado válido.
- Descargas: URLs privadas limitadas a artefacto/usuario y con expires_at; H1 comprueba hash, archivo y permiso antes de emitirlas. Reconsultar manifest renueva URL. No se expone ubicación interna.
- Cancelación 202 confirma petición, no parada. El worker debe detener procesos antes de cancelled. Un job terminal conserva estado; ninguna llamada reinicia sus artefactos.

## Relacionados

[OpenAPI](../../packages/contracts/openapi.json), [contratos](../../packages/contracts/README.md), [incidencias](../../packages/contracts/incidences.md).

Fuentes: [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/), [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html).
