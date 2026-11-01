# H0-05 — Recorrido web y estados

Contratos: **CONTRATOS_Y_CALIDAD.md v0.1 (propuesta, sin congelar)**. Tipos en `src/contracts/` marcados «borrador».

## Contenido
- [Recorrido](#recorrido) · [Estados](#estados) · [Datos simulados](#datos-simulados) · [Cambios propuestos](#cambios-propuestos) · [Ejecución](#ejecución)

## Recorrido

| Ruta | Vista | Datos |
|---|---|---|
| `/` | Proyectos (lista, alta) | `GET/POST projects` |
| `/proyectos/:id` | Carga, ajustes, historial | assets, profiles, jobs |
| `/trabajos/:id` | Progreso → resultado, revisión, falla o cancelación | job, artifacts |

Resultado `ready_for_sewout`: comparación original / vector / preview del JEF, medidas releídas, avisos, descargas, variante de tamaño.

## Estados

| Estado del job | UI |
|---|---|
| `queued`, `analyzing`, `vectorizing`, `digitizing`, `validating` | Etapas, progreso observado, cancelar |
| `ready_for_sewout` | «Listo para prueba (digital)»; muestra física `untested` aparte |
| `needs_review` | Causa, objetos/regiones, correcciones → revisión nueva |
| `failed` | Etapa y causa; reintento = job nuevo |
| `cancelled` | Sin descargas; reintento = job nuevo |

Reglas:
- La UI **nunca envía** un estado; solo lo lee.
- Progreso = etapas observadas (las `skipped` no cuentan). Tiempo restante rotulado «estimación».
- Artefactos con `job_id` ajeno se descartan y se avisa.
- Variante y corrección = `POST revisions` → job nuevo con `parent_job_id`; la web no escala puntadas.
- Sin claves de proveedores en la web; proveedor no disponible → deshabilitado, sin cambio silencioso.

## Datos simulados

| Qué | Dónde |
|---|---|
| Cliente en memoria | `src/mocks/MockApiClient.ts` (`VITE_USE_MOCKS=true`, valor por defecto) |
| Guiones | `src/mocks/scenarios/` — por nombre de archivo: `*fallo*` → falla en `digitizing`; `*revision*` → `needs_review`; SVG → omite análisis y vectorización |
| Imágenes/archivos | `src/mocks/fixtures/` (rotulados «SIMULADO») |
| Cliente real | `src/api/HttpApiClient.ts`: **bloqueado a propósito** hasta que el integrador congele los contratos |

La franja «Datos simulados» se muestra siempre que el cliente sea simulado.

## Cambios propuestos

**Aprobados por el usuario el 2026-11-01** como propuesta para el contrato. Siguen pendientes de implementación por la IA del motor (`codex/motor`) y de congelamiento por el integrador; la web los asume en los tipos borrador y no se conecta al servicio real hasta entonces.

| # | Cambio | Motivo |
|---|---|---|
| 1 | `GET /projects`, `GET /projects/{id}` (assets + jobs) | Listar y reabrir proyectos |
| 2 | `GET` de perfiles: máquinas, bastidores, telas, `max_colors`, disponibilidad de proveedores y límites de subida | No fijar catálogos en la web |
| 3 | `hoop_profile` en `JobSettings` | El texto lo menciona; el ejemplo JSON no |
| 4 | Forma de `Job`: `stages[]` con `pending/running/done/skipped/failed` y `duration_ms` medido, `failure{code,message,stage}`, `review`, `diagnostics`, `parent_job_id`, `sewout_status`, `estimated_remaining_s` | `GET /jobs/{id}` no define respuesta |
| 5 | `SourceAsset.original_filename` | Mostrar el archivo al usuario |
| 6 | Artefactos: `kind`, `job_id`, `filename`, `sha256`, `size_bytes`, `content_type`, `download_url` autorizada | Descarga del trabajo correcto |
| 7 | Artefactos para comparación: SVG editable (vector) y preview PNG del JEF releído | Vista original / vector / JEF |
| 8 | Cuerpo de `POST revisions`: `size_variant{target}` y `correction{exclude_region, set_technique}`; respuesta = `Job` nuevo | Variantes y revisión localizada |
| 9 | Encabezado de idempotencia en `POST jobs`, formato de errores y autenticación | Reintentos sin duplicar |

## Ejecución

```bash
cd apps/web && npm install && npm run dev      # web con datos simulados
cd apps/web && npm test                        # unitarias + flujos (Vitest)
cd tests/e2e && npm install && npx playwright test   # e2e (usa Chrome instalado)
```
