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

## Verificación contra el backend real (H0-04)

Se corrió la UI completa contra `uvicorn` (commit `c6b4db6`) con el SVG `Anime_Socks_InkStitch.svg`, 150 × 150 mm, `sq20b` y `gabardina_inicial`. Para repetirla: levantar el backend, `cd tests/e2e && npx playwright test -c playwright.real.config.ts` (usa un Vite propio en el puerto 5176 con `API_PROXY_TARGET`).

| Punto | Resultado real |
|---|---|
| Autenticación | HTTP Basic (`test`/`test`). El desafío es Basic solo si el config **no** define `service_token` |
| Latencias (sonda directa) | `POST /projects` 17 ms · `/assets` 30 ms · `/revisions` 22 ms · `POST /jobs` **202 en 10 ms** · `GET artifacts` 17 ms |
| Estados | `digitizing` (0 s) → `needs_review` (18,9 s). Con sondeo cada 0,5 s no se observaron `queued` ni `validating`; `analyzing` y `vectorizing` figuran `skipped` |
| `GET artifacts` | **200 en `needs_review`**, TTL 300 s, `Cache-Control: no-store` |
| Archivos | **6**: `jef`, `editable_svg`, `inkstitch_svg`, `preview_png` (`jef_reread`), `validation_json`, `raw_commands_json` (el mock tiene 4) |
| JEF descargado desde la UI | 14.816 bytes; `pyembroidery`: **150,0 × 142,8 mm, 6.789 puntadas, 3 bloques** |
| Límites releídos | `stitch_bounds_mm` de −75 a 75 y de −71,4 a 71,4 (origen centrado, no 0…150); la UI muestra el ancho y el alto calculados, sin depender del origen |
| Incidencias | 14 `SATIN_RUNG_WARNING` (`review_required`), estado final siempre `needs_review` |
| Muestra física | `POST /sewouts` 201; `sewout_status` pasa a `approved` y el estado digital sigue en `needs_review` |
| Cancelación | `POST /cancel` 202; el siguiente `GET` ya devuelve `cancelled` con `cancellation_requested: true` (~1 s) y sin descargas |

**Diferencias entre el mock y el backend real**
- **Avisos sin asignar a un objeto:** los 14 avisos son idénticos («Satin has no rungs») y cada uno lista los **mismos 14** `object_ids` (`satin_A_descenso_0`, `satin_SOCKS_S_1_0`, …). Su evidencia declara `localization: "candidate columns, native warning unmapped"` y `source_object_mapping_verified: false`: son columnas candidatas, no una relación 1 a 1. Este caso rompió la web (claves repetidas en la lista); ya está corregido con una prueba de regresión. Falta decidir si la UI debe avisar que la asignación no está verificada.
- **Original sin vista previa:** el backend no emite `original_download` (llega `null`). La comparación muestra «—» en «Original» y el formulario dice que la vista previa no está disponible.
- **Catálogo:** `providers` llega vacío; no afecta a los SVG preparados, pero una imagen no mostraría proveedor para elegir.
- **Solo SVG preparado:** PNG/JPG, variantes de tamaño y correcciones todavía no se ejecutan en H0-04; esas partes de la UI no se pudieron probar contra el backend real.
- **Enlaces:** son absolutos (`public_base_url`) y firmados; se abren sin credenciales, con `Content-Disposition: attachment`.

**Mock alineado con el backend real:** el fixture `job-completed-real.json` ahora tiene la forma exacta de la respuesta real (6 artefactos, 14 avisos idénticos con los 14 `object_ids` reales, controles `file`/`dimensions`/`hoop` en `passed` y `geometry`/`satin`/`routing`/`visual` en `not_run`, límites releídos de −75 a 75 y de −71,4 a 71,4). Los ids y hashes son ficticios evidentes (`000…001`, `000…002`), `provenance.simulated` es `true`, y el cliente simulado devuelve `original_download: null` para un SVG, como el backend. Los `object_ids` coinciden con `services/api/evidence/h0-04/job.json`.

## H2 — preparación de la UI de análisis visual (solo mocks)

Lo que existe hoy en la web, **sin backend** (el servidor de H0-04 solo ejecuta SVG preparado):
- **Carga:** acepta PNG, JPG y SVG; muestra la vista previa de la imagen subida y una etiqueta que distingue «SVG preparado» (va directo a la generación) de «Imagen para analizar» (pasa antes por una IA). Para una imagen aparece el selector OpenAI / Ollama con el aviso «Función experimental». Si el catálogo no trae proveedores disponibles, no deja generar una imagen (sí un SVG).
- **Pantalla `AnalysisReview`:** aparece con un job `needs_review`, `input_kind: raster_image` y avisos de etapa `analysis`. Muestra la imagen con las cajas estimadas, la lista de regiones (rol, texto detectado, colores sugeridos, dudas), permite marcar regiones para revisión manual, aprobar y continuar, o regenerar con otro proveedor. Las cajas son una guía no verificada (`estimated_bbox`).
- **Mocks:** `apps/web/mocks/analysis-result.json` (`simulated: true`). Un PNG/JPG cuyo nombre contiene `analisis` (1 región incierta) o `ambiguo` (3 regiones inciertas) activa el flujo; cualquier otra imagen sigue yendo directo a la generación.

### Cambios propuestos para el backend (H2) — esperan confirmación, no implementados

Mensaje para quien implemente el backend (OpenCode), listo para copiar:

> La web de H2 ya funciona con mocks y necesita estas operaciones. Ninguna existe en OpenAPI v0.1; propongo la forma y espero confirmación antes de que la implementes.
>
> 1. `GET /api/v1/jobs/{id}/analysis` → 200 `AnalysisSpec` (forma congelada en `design.py`). Solo para un job de imagen que ya terminó el análisis; 404/409 en otro caso. `region_id` debe coincidir con los `region_ids` de los avisos `ANALYSIS_REGION_INCOHERENT`.
> 2. `POST /api/v1/jobs/{id}/analysis-decision` (con `Idempotency-Key`) con cuerpo `{"action":"approve","flagged_region_ids":[...]}` o `{"action":"change_provider","ai_provider":"openai|ollama"}` → 202 `JobResponse` **nuevo** con `parent_job_id` = `{id}`; el job original en `needs_review` no cambia. 409 `REVISION_CONFLICT` si ese job no está en `needs_review` por análisis; 422 si el proveedor no está disponible. Alternativa equivalente: nuevos `kind` en `POST /projects/{id}/revisions`.
> 3. En el job que continúa tras aprobar, `analyzing` figura `skipped` con motivo («análisis aprobado en {id}»).
> 4. Duda: `needs_review` exige un aviso `review_required` localizado, así que un análisis sin dudas no se detendría. ¿Hace falta una pausa opcional de aprobación?
> 5. Duda: ¿en qué marco están `bounds_px` (original completo o recorte `crop_px`)?
> 6. Duda: ¿qué hace el backend con `flagged_region_ids` (revisión manual en H3)?
> 7. El catálogo de perfiles hoy devuelve `providers: []`; para imágenes debe listar `openai` y `ollama` con su disponibilidad.
> 8. Para una imagen, `original_download` debería traer el enlace del original (la web lo usa para la vista previa).

En el cliente real (`HttpApiClient`), `getAnalysis` y `decideAnalysis` **no llaman a la red**: devuelven un error controlado «no implementado» hasta que estas operaciones se aprueben.

## Accesibilidad

Se corre **axe-core** (`@axe-core/playwright`, solo en `tests/e2e`) sobre la UI real en Chrome, en escritorio y en móvil (Pixel 7), con las etiquetas WCAG 2.0/2.1/2.2 A y AA más las buenas prácticas de axe, contraste incluido. Pantallas escaneadas: proyectos (vacío y con uno), proyecto sin imagen, con imagen y error de validación y con aviso de bastidor, trabajo en curso, fallido y cancelado, resultado listo (con y sin errores del formulario de muestra), revisión con archivos (14 incidencias) y la pantalla de error 501 con el cliente real.

| Hallazgo | Corrección |
|---|---|
| `region`: el aviso «Datos simulados» quedaba fuera de un landmark | Pasó a estar dentro de `<header>`; la navegación quedó en `<nav aria-label="Principal">` |
| `color-contrast`: texto verde sobre verde claro de la insignia «Listo para prueba» (4,40:1) | `--color-ok` de `#2e7d4f` a `#226640` (6,02:1 sobre el fondo de la insignia) |

Mejoras que axe no detecta y se hicieron igual:
- Título de pestaña descriptivo por pantalla (WCAG 2.4.2): «Proyectos», nombre del proyecto y «Generación del bordado», todos seguidos de «· Bordados con IA».
- Los cambios de estado del trabajo se anuncian a lectores de pantalla (`role="status"` oculto visualmente).
- Prueba de teclado: se crea un proyecto sin mouse y cada elemento enfocable con Tab muestra contorno de foco (≥ 2 px).

**Sin resolver**
- **Foco al cambiar de pantalla:** tras navegar, el foco no se mueve al título. Es una decisión de diseño de navegación; conviene probarla con un lector de pantalla antes de elegir la solución.
- **Cobertura de axe:** analiza solo lo renderizado en cada estado. No cubre `:hover`, controles deshabilitados en cada estado, zoom al 200 % ni reflujo a 320 px, ni modo oscuro (no existe).
- **Sin prueba manual con lector de pantalla** (NVDA/VoiceOver): axe no sustituye esa revisión.
- **Fotos de la muestra:** cuando exista la subida, habrá que revisar su texto alternativo.

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
