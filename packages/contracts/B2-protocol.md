# B2: flujo y acceso

Propósito: cerrar bootstrap, descargas y proyecciones; v0.1 B2 candidato a congelar, pendiente de integrador humano. Especificación sin servidor implementado.

Contenido: [Inicio](#inicio), [descargas](#descargas), [estado](#estado), [relacionados](#relacionados).

## Inicio

1. POST /api/v1/projects → 201 project_id.
2. POST /api/v1/projects/{id}/assets → 201 asset_id; preservar original.
3. POST /api/v1/projects/{id}/revisions con base_revision_id:null y ajustes → 201 revision_id.
4. POST /api/v1/projects/{id}/jobs con asset_id, revision_id y ajustes coincidentes → 202 queued.

revision_id es obligatorio: POST jobs NO crea revisión implícita. La UI añade la llamada inicial, sin otra pantalla ni confirmación. `openapi.json → x-initial-flow` contiene los 4 requests/responses y headers, con IDs encadenados y ejemplos versionados simulados.

Variante: `{kind:size_variant,parent_job_id,target}`. Corrección: `{kind:correction,parent_job_id,corrections:[...]}`. exclude_region admite exactamente object_id O region_id; set_technique exige object_id/technique. POST revisions devuelve 202 con revisión/job nuevos y snapshot. H1 valida pertenencia y targets; no sobrescribe artefactos.

## Descargas

- TTL fijo **300 s**: issued_at y expires_at UTC; expires_at=issued_at+300s. download_url/expires_at planos deben coincidir con download anidado.
- GET /api/v1/jobs/{id}/artifacts siempre reautoriza y emite URLs nuevas. Es seguro e idempotente sobre identidad/bytes de job y artefactos; el JSON puede cambiar. No exporta ni genera otro job. Sin endpoint refresh adicional.
- Cache-Control:no-store en manifest y respuestas con URLs. Vencida una URL, la UI reconsulta GET artifacts y reintenta con la nueva. H1 revalida permisos al emitir y usar URL. La expiración no cambia estado digital.
- Manifest de worker/GET job admite URLs null (snapshot). GET artifacts 200 usa AuthorizedArtifactManifest: todas las URLs presentes. Antes de descargar, renovar allí. Originales: original_download se renueva en GET project.
- URLs no son identidad ni parte del hash de contenido. No exponer rutas de almacenamiento.

## Estado

- Cancelación aceptada responde **202 siempre**, también si ya terminal. Conserva estado observado; no declara parada al recibir solicitud ni reinicia un terminal.
- JobStatus no contiene approved. sewout_status es proyección readOnly de sewout_record de esa revision_id; aprobación/ajuste necesitan ID de registro, fecha y observaciones. Sin registro: untested.
- Failure/review/diagnostics derivan de issues; no se pueden presentar espejos contradictorios. failed mantiene diagnóstico bloqueante obligatorio. estimated_remaining_s es estimación opcional, nunca duración medida.

## Relacionados

[Mapa de cambios](B2-web-mapping.md), [estados](states.md), [OpenAPI](openapi.json), [API](../../services/api/README.md).
