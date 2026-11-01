# Recorrido web, estados y conexión a contratos v0.1

Contratos: **tag `contratos-v0.1` (commit `ad958db`)**, congelados. Tipos en `src/contracts/` escritos a mano desde `packages/contracts` (sin generación automática).

## Contenido
- [Recorrido](#recorrido) · [Flujo inicial](#flujo-inicial) · [Enlaces con vencimiento](#enlaces-con-vencimiento) · [Estados](#estados) · [Datos simulados](#datos-simulados) · [Supuestos](#supuestos-a-confirmar-en-h1) · [Ejecución](#ejecución)

## Recorrido

| Ruta | Vista | Llamadas |
|---|---|---|
| `/` | Proyectos (lista, alta) | `GET/POST /projects` |
| `/proyectos/:id` | Carga, ajustes, historial | `GET /projects/{id}`, `GET /profiles`, `POST assets` |
| `/trabajos/:id` | Progreso → resultado, revisión, falla o cancelación | `GET /jobs/{id}`, `GET /jobs/{id}/artifacts`, `POST cancel` |

## Flujo inicial

`POST /projects` → `POST /projects/{id}/assets` → `POST /projects/{id}/revisions` (`base_revision_id: null`) → `POST /projects/{id}/jobs` (con ese `revision_id`). La UI hace los dos últimos pasos al pulsar «Generar bordado», sin pantalla extra (`src/api/startGeneration.ts`). Las claves de idempotencia derivan de una base por envío: reintentar el mismo contenido no duplica; cambiar los datos genera clave nueva.

## Enlaces con vencimiento

- Los enlaces de descarga y del original vencen a los **300 s**.
- `GET /jobs/{id}/artifacts` se vuelve a pedir ~10 s antes de `expires_at` (`useArtifacts`); el original se renueva con `GET /projects/{id}`.
- Si el usuario descarga un enlace vencido o por vencer, se reconsulta y se usa el nuevo.
- Nada se conserva más allá de `expires_at`; las URLs no son identidad del archivo.

## Estados

| Estado del job | UI |
|---|---|
| `queued`…`validating` | Etapas observadas, cancelar |
| `ready_for_sewout` | «Listo para prueba (digital)»; `sewout_status` aparte (`untested` por defecto) |
| `needs_review` | Causa y objetos/zonas del servidor; corrección → `POST revisions` (202) con job nuevo |
| `failed` | Etapa y causa de `failure`; reintento = job nuevo sobre la misma revisión |
| `cancelled` | Sin descargas. La cancelación (202) solo registra la solicitud: se muestra «Cancelación solicitada» hasta que el servidor publica `cancelled` |

Reglas: la UI nunca envía estados; el progreso sale de etapas observadas (`skipped` no cuenta); `estimated_remaining_s` se rotula estimación; un artefacto con `job_id` ajeno se descarta; sin claves de proveedores en la web; proveedor no disponible → deshabilitado, sin cambio silencioso.

## Datos simulados

| Qué | Dónde |
|---|---|
| Fixtures copiados de `packages/contracts/fixtures` (+ `profiles.json`, derivado del ejemplo de `openapi.json`) | `apps/web/mocks/*.json` (`simulated: true`) |
| Cliente en memoria | `src/mocks/MockApiClient.ts` — activo solo con `VITE_USE_MOCKS=true` |
| Guiones por nombre de archivo | `*fallo*` → falla en `digitizing`; `*revision*` → `needs_review`; SVG → omite análisis y vectorización |
| Cliente real | `src/api/HttpApiClient.ts` — activo por defecto (sin la variable) |

La franja «Datos simulados» aparece siempre que el cliente sea simulado. Sin `VITE_USE_MOCKS=true`, la web habla con `/api/v1` del mismo origen (en desarrollo, `API_PROXY_TARGET` reenvía `/api`).

## Supuestos a confirmar en H1

1. **Reintento:** se crea un job nuevo con el mismo `revision_id` (`states.md`: «nuevo intento separado»). El contrato no dice si `POST jobs` admite varios jobs por revisión.
2. **SVG = `prepared_svg`:** todo SVG subido se envía con `input_kind: prepared_svg` y `ai_provider: none`. El contrato no distingue un SVG que sí necesite análisis.
3. **Autenticación:** el navegador gestiona HTTP Basic en mismo origen; `ServiceBearer` no es utilizable desde el navegador.
4. **Revisión sin cajas:** `review` trae `object_ids`/`region_ids`, no píxeles; no se dibuja overlay sobre el original.
5. **Textos del servidor:** `description`/`message` llegan en inglés; la web traduce por `code` (catálogo) y usa el texto del servidor solo como respaldo.
6. **Paginación:** se muestra la primera página con un aviso si hay `next_cursor`; falta «ver más».
7. **Muestra física:** se muestra el estado; falta el formulario de `POST /sewouts` (exige fecha y observaciones para `approved`/`needs_adjustment`).

## Ejecución

```bash
cd apps/web && npm install && npm run dev      # con VITE_USE_MOCKS=true en .env.local → datos simulados
cd apps/web && npm test                        # unitarias + flujos (Vitest)
cd tests/e2e && npm install && npx playwright test   # e2e: mocks + cliente real contra stub (usa Chrome instalado)
```
