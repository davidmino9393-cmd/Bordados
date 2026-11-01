# Contratos v0.1 concretos

Propósito: propuesta ejecutable **pendiente de revisión humana**, todavía no congelada. Tanda A: Pydantic, estados y mocks; OpenAPI y catálogo completo llegan en Tanda B. No hay API ni worker ejecutable en esta entrega.

Contenido: [Uso](#uso), [documentos](#documentos), [reglas](#reglas), [relacionados](#relacionados).

## Uso

- Python 3.12+, Pydantic 2.14.1; dependencia fijada en `services/api/requirements.txt`.
- Añadir `packages/contracts` al `PYTHONPATH` e importar `embroidery_contracts`.
- Validación: `JobCreate.model_validate(datos)`; JSON Schema: `JobCreate.model_json_schema()`.
- Desde la raíz: `python -m unittest discover -s tests/engine -p test_contracts.py` con ese entorno.
- Objetos Pydantic congelados; solicitudes rechazan campos desconocidos. Cambiar ajustes crea otra revisión, no modifica una generación anterior.
- Inicio: proyecto → asset → revisión inicial (`base_revision_id: null`) → job. Null solo admite la primera revisión; H1 valida esa condición y pertenencia de la revisión base en las siguientes.

## Documentos

| Documento | Archivo | Función |
|---|---|---|
| JobSettings / SourceAsset | settings.py | Tamaño, perfiles versionados y original preservado |
| AnalysisSpec / EmbroideryDocument | design.py | Regiones estimadas frente a geometría preparada/verificada |
| StitchPlan / ValidationReport / ArtifactManifest | results.py | Comandos, controles y referencias a exportación/relectura |
| JobCreate / JobResponse / SewoutRecord | jobs.py | Solicitud, estado digital y muestra física separados |

## Reglas

- `schema_version: "0.1"` identifica documentos; `/api/v1` identifica la API. Los IDs de perfiles son referencias propuestas, no perfiles calibrados incluidos.
- Solo el servidor publicará `ready_for_sewout`. Pydantic comprueba coherencia de referencias, checks y métricas; NO comprueba existencia/bytes de archivos ni ejecución real del worker.
- `approved` solo existe en SewoutRecord. Requiere fecha de muestra y observaciones; la autenticidad de la muestra la registra un usuario autorizado en H1.
- `download` contiene URL privada temporal y vencimiento, nunca rutas internas. Las URLs de mocks usan `example.invalid` y no descargan archivos.
- Revisiones, permisos, almacenamiento, idempotencia y cancelación de procesos deben implementarse en H1. Los modelos no sustituyen esos controles.
- Cambios incompatibles después de revisión requieren nueva versión y ejemplos/impacto acordados con web.

## Relacionados

[Fixtures](fixtures/README.md), [estados](states.md), [unidades](units.md), [propuesta original](../../CONTRATOS_Y_CALIDAD.md).
