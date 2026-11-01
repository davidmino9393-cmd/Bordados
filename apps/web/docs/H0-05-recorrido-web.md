# Recorrido web, estados y conexión a contratos v0.1

Contratos: **tag `contratos-v0.1` (commit `ad958db`)**, congelados. Tipos en `src/contracts/` escritos a mano desde `packages/contracts` (sin generación automática).

## Contenido
- [Recorrido](#recorrido) · [Flujo inicial](#flujo-inicial) · [Enlaces con vencimiento](#enlaces-con-vencimiento) · [Estados](#estados) · [Datos simulados](#datos-simulados) · [Supuestos](#supuestos-a-confirmar-en-h1) · [Ejecución](#ejecución)

## Recorrido

| Ruta | Vista | Llamadas |
|---|---|---|
| `/` | Proyectos (lista, alta) | `GET/POST /projects` |
| `/proyectos/:id` | Carga, ajustes, historial | `GET /projects/{id}`, `GET /profiles`, `POST assets` |
| `/trabajos/:id` | Progreso → resultado, revisión, falla o cancelación | `GET /jobs/{id}`, `GET /jobs/{id}/artifacts`, `POST cancel`, `POST /projects/{id}/sewouts` |

## Flujo inicial

`POST /projects` → `POST /projects/{id}/assets` → `POST /projects/{id}/revisions` (`base_revision_id: null`) → `POST /projects/{id}/jobs` (con ese `revision_id`). La UI hace los dos últimos pasos al pulsar «Generar bordado», sin pantalla extra (`src/api/startGeneration.ts`). Las claves de idempotencia derivan de una base por envío: reintentar el mismo contenido no duplica; cambiar los datos genera clave nueva.

## Enlaces con vencimiento

- Los enlaces de descarga y del original vencen a los **300 s**.
- `GET /jobs/{id}/artifacts` se vuelve a pedir ~10 s antes de `expires_at` (`useArtifacts`); el original se renueva con `GET /projects/{id}`.
- Si el usuario descarga un enlace vencido o por vencer, se reconsulta y se usa el nuevo.
- Nada se conserva más allá de `expires_at`; las URLs no son identidad del archivo.
- **Por qué el margen es dinámico** (`src/shared/utils/expiry.ts`): con el TTL real de 300 s se renueva 10 s antes de vencer. El margen es como máximo el 20 % de la vida del enlace y la espera nunca baja de 0,5 s. Con un margen fijo de 10 s, un TTL corto (el mock de pruebas usa 1 s) renovaba sin pausa y generaba un bucle de consultas. Para el contrato (300 s fijos) el comportamiento no cambia.
- **Cuándo hay archivos:** `GET /jobs/{id}/artifacts` responde 200 en `ready_for_sewout` y en `needs_review` (los archivos ya existen); responde 409 `ARTIFACTS_UNAVAILABLE` en `queued`/`digitizing`/`validating` (todavía no existen) y en `failed`/`cancelled` (nunca existirán). La web solo consulta los archivos si el job trae `artifact_manifest`, así que no pide algo que sabe que dará 409.
- **409 aunque el job traiga `artifact_manifest`** (bug, carrera con una cancelación, despliegue parcial): la web muestra «No se pudieron obtener los archivos. Reintentá.» con el código de incidencia, quita los enlaces anteriores y deja usable el resto de la pantalla. El botón «Reintentar» reconsulta primero `GET /jobs/{id}` (el estado pudo cambiar) y después los archivos.

## Reintentos ante errores transitorios

`useJobPolling` reintenta con backoff exponencial: 1, 2, 4, 8, 16 s y tope de 30 s, con ±20 % de jitter (nunca más de 30 s). Se muestra «Reintentando en X s». El contador vuelve a 1 s al recibir una respuesta correcta o al cambiar de trabajo. Solo se reintentan `NETWORK`, `TIMEOUT`, `RATE_LIMITED`, `INTERNAL_ERROR` y `SERVICE_UNAVAILABLE`; 400, 403, 404, 422 y 501 se informan una vez, con su código de incidencia.

## Muestra física

Formulario visible con el trabajo en `ready_for_sewout` **o `needs_review`** (decisión del integrador: se puede registrar una muestra aunque los controles digitales no hayan pasado); no se ofrece en fallos, cancelaciones ni trabajos en curso. Envía un `SewoutRecord` (`POST /projects/{id}/sewouts`) sobre la `revision_id` del trabajo y, al volver `201`, pide de nuevo `GET /jobs/{id}`: `sewout_status` y `sewout_record` son la proyección del servidor y el estado digital no cambia.

| Campo del formulario | Campo del contrato | Nota |
|---|---|---|
| Resultado | `status` | `approved`, `needs_adjustment` o `untested` |
| Fecha de la muestra | `tested_at` | Obligatoria salvo en `untested` (que no la admite); no puede ser futura |
| Tela usada | `fabric_profile` | Es un id de perfil: se elige del catálogo, no es texto libre |
| Estabilizador, Hilo, Observaciones | `stabilizer`, `thread`, `observations` | Texto obligatorio (máx. 2000) |
| — | `photo_asset_ids` | Se envía vacío; sin subida de fotos todavía |

## Estados

| Estado del job | UI |
|---|---|
| `queued`…`validating` | Etapas observadas, cancelar |
| `ready_for_sewout` | «Listo para prueba (digital)»; `sewout_status` aparte (`untested` por defecto) |
| `needs_review` | Causa y objetos/zonas del servidor; corrección → `POST revisions` (202) con job nuevo. Si el servidor ya generó archivos (`artifact_manifest`), se muestran con el aviso «no están listos para prueba»; la muestra física también se puede registrar |
| `failed` | Etapa y causa de `failure`; reintento = job nuevo sobre la misma revisión |
| `cancelled` | Sin descargas. La cancelación (202) solo registra la solicitud: se muestra «Cancelación solicitada» hasta que el servidor publica `cancelled` |

Reglas: la UI nunca envía estados; el progreso sale de etapas observadas (`skipped` no cuenta); `estimated_remaining_s` se rotula estimación; un artefacto con `job_id` ajeno se descarta; sin claves de proveedores en la web; proveedor no disponible → deshabilitado, sin cambio silencioso.

## Datos simulados

| Qué | Dónde |
|---|---|
| Fixtures copiados de `packages/contracts/fixtures` (+ `profiles.json`, derivado del ejemplo de `openapi.json`) | `apps/web/mocks/*.json` (`simulated: true`) |
| Cliente en memoria | `src/mocks/MockApiClient.ts` — activo solo con `VITE_USE_MOCKS=true` |
| Guiones por nombre de archivo | `*fallo*` → falla en `digitizing`; `*revision*` → `needs_review`; SVG → omite análisis y vectorización; SVG `*completo*` → fixture `job-completed-real.json` (`needs_review` con archivos y 14 incidencias de satén) |
| Opciones por URL (solo con mocks) | `?mockDownloadTtlMs=1500` acorta el TTL de las descargas; `?mockTrace=1` anota las operaciones en `window.__mockApiCalls` |
| Cliente real | `src/api/HttpApiClient.ts` — activo por defecto (sin la variable) |

La franja «Datos simulados» aparece siempre que el cliente sea simulado. Sin `VITE_USE_MOCKS=true`, la web habla con `/api/v1` del mismo origen (en desarrollo, `API_PROXY_TARGET` reenvía `/api`).

> `job-completed-real.json` **no es una exportación real**: es la forma de un job con archivos y controles digitales sin aprobar (`digital_checks_passed=false`). Sus medidas (150 × 142,8 mm, 6.789 puntadas) son las del inventario histórico, y los hashes son ficticios. Conserva `simulated: true`.

## Supuestos a confirmar en H1

1. **Reintento:** se crea un job nuevo con el mismo `revision_id` (`states.md`: «nuevo intento separado»). El contrato no dice si `POST jobs` admite varios jobs por revisión.
2. **SVG = `prepared_svg`:** todo SVG subido se envía con `input_kind: prepared_svg` y `ai_provider: none`. El contrato no distingue un SVG que sí necesite análisis.
3. **Autenticación:** el navegador gestiona HTTP Basic en mismo origen; `ServiceBearer` no es utilizable desde el navegador.
4. **Revisión sin cajas:** `review` trae `object_ids`/`region_ids`, no píxeles; no se dibuja overlay sobre el original.
5. **Textos del servidor:** `description`/`message` llegan en inglés; la web traduce por `code` (catálogo) y usa el texto del servidor solo como respaldo.
6. **Paginación:** se muestra la primera página con un aviso si hay `next_cursor`; falta «ver más».
7. **Muestra física, varias por revisión:** el contrato no dice si una revisión admite más de un registro ni cuál manda; la web permite registrar otro y muestra la proyección que devuelve el servidor.
8. **Fecha con hora:** `tested_at` es `AwareDatetime`; el selector es `datetime-local` (hora local) y se envía en UTC.
9. **Fotos de la muestra:** `photo_asset_ids` existe en el contrato, pero no define cómo subir una foto como asset. Queda pendiente (cambio propuesto: indicar el flujo de subida).
10. **Quién puede registrar:** el contrato habla de «usuario autorizado»; si no lo es, el 403 se muestra con su código.

## Deuda menor (H1 completo)

- **Paginación:** primera página de proyectos, assets y trabajos; falta «ver más».
- **Fotos de la muestra:** `photo_asset_ids` queda vacío hasta H2/H3.
- **Test cruzado con el backend:** que el backend valide con Pydantic los fixtures que consume la web, cuando exista el servicio real.

## Ejecución

```bash
cd apps/web && npm install && npm run dev      # con VITE_USE_MOCKS=true en .env.local → datos simulados
cd apps/web && npm test                        # unitarias + flujos (Vitest)
cd tests/e2e && npm install && npx playwright test   # e2e: mocks + cliente real contra stub (usa Chrome instalado)
```
