# B2: coordinación con web

Propósito: **contratos v0.1 candidatos a congelar**, revisión B2; no congelados. Registra los 9 cambios aprobados sin renombrar campos canónicos ya implementados.

Contenido: [Fuente](#fuente), [mapa](#mapa), [relacionados](#relacionados).

## Fuente

Basado en el documento del recorrido web H0-05.

SHA-256: `4f807df992677e8420e6f5c671bac350e4774abd51dba86906e7f478f31c6c8a`.

## Mapa

| # | Contrato B2 y adaptación web |
|---|---|
| 1 | GET projects: items/next_cursor. GET project: project/assets/jobs; assets_next_cursor/jobs_next_cursor permiten seguir historia sin truncarla. id del borrador → project_id/job_id/asset_id. |
| 2 | GET profiles: máquinas, bastidores, telas, max_colors, proveedores y límites bytes/píxeles/MIME. IDs y versiones explícitos. machine.hoop_profile_ids referencia hoops plano. thread_profiles completa el thread_profile que ya exigía JobSettings. Ejemplos propuestos, no calibrados. |
| 3 | hoop_profile obligatorio y coincidente con hoop.profile_id. Se conservan snapshot hoop y versiones de perfiles; resolverlos desde catálogo, sin valores fijos en web. |
| 4 | JobResponse mantiene asset_id/settings_snapshot. stages: state→outcome; done→completed; duration_ms→measured_duration_ms. failure/review/diagnostics son vistas tipadas derivadas de issues, con guardas contra contradicción. parent_job_id, estimación opcional y sewout_status con evidencia de registro para la misma revisión. |
| 5 | SourceAsset.original_filename: basename solo para mostrar. original_url→original_download.url temporal; consultar GET project para renovarla. Dimensiones SVG pueden ser null. |
| 6 | Cada Artifact exige job_id del manifest. size_bytes→byte_size; content_type→media_type. download_url/expires_at son vistas planas de download, no valores independientes. metrics→reread_metrics; ancho/alto se derivan de stitch_bounds_mm. |
| 7 | Ready exige editable_svg e inkstitch_svg, JEF, preview_png desde relectura y validation_json. Tipos borrador svg_editable/svg_inkstitch/jef_preview_png/report se mapean a esos nombres. |
| 8 | POST revisions: inicial 201 exige base:null, sin parent/job; se elimina rama legacy 201 con base no-null. size_variant/correction 202 con nuevo job/revision y parent. exclude_region exige object_id O region_id (XOR); set_technique exige objeto. GET revisions conserva enlaces. |
| 9 | BasicAuth O ServiceBearer simple; sin OAuth. Idempotency-Key en todos los POST. ProblemResponse con application/problem+json conserva forma y códigos. |

review conserva object_ids/region_ids: no inventa cajas de píxeles. evidence sigue siendo JSON estructurado; suggested_fix del borrador → suggested_correction. La UI copia de nuevo los 6 JSON B2: simulated=true y schema_version=0.1 permanecen.

## Relacionados

[Protocolo](B2-protocol.md), [OpenAPI](openapi.json), [fixtures](fixtures/README.md), [modelos](README.md).
