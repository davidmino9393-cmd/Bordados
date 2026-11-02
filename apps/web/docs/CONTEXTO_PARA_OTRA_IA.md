# Contexto del proyecto para otra IA

Fecha: noviembre de 2026. Escrito por Claude Code (sesión web). Léelo completo antes de tocar nada.

## 1. Qué es el proyecto
Aplicación web privada que convierte una imagen o un SVG de un logo en un bordado para la máquina **Janome MC 550E** (archivo **JEF**), con revisión humana cuando hay dudas.
- Camino principal: crear proyecto → subir imagen/SVG → indicar tamaño en mm, tela, bastidor y colores → generar → revisar o descargar (SVG editable, SVG Ink/Stitch, JEF, vista previa, informe).
- Motor: Inkscape + Ink/Stitch (v3.2.2) y `pyembroidery` para releer el JEF. IA de visión (OpenAI o modelo local Ollama) solo para **analizar imágenes** (H2).
- Documentos de referencia en la raíz: `PLAN_MAESTRO.md`, `CONTRATOS_Y_CALIDAD.md`, `TAREAS_INICIALES.md`, `TRABAJO_CON_VARIAS_IAS.md`, `CLAUDE.md`.

## 2. Personas e IAs y reglas de convivencia
- **David (coordinador humano):** decide merges a `main`, contratos y permisos. Ningún merge sin su autorización.
- **Claude Code (esta sesión):** `claude/web`, worktree `C:\dev\wt-web`. Hizo la web y, con autorización expresa, también contrato, API y pruebas del motor **solo en esa rama**.
- **OpenCode:** hizo H0-04 (API + worker real) y H0-06. **Sin límite de uso** disponible.
- **Codex:** hizo contratos iniciales y el esqueleto de H0-04. **Disponible de nuevo.** Ya leyó este contexto y el plan de H2, tiene `codex/motor` limpia en `af21ed3` y verificó los 14 archivos del conjunto de imágenes. Propuesta: Codex toma el módulo E (vector y geometría); Claude conserva web, conexión con la API y evaluación F. Ver `h2/E-interfaz.md`.
- Worktrees: `C:\dev\bordados` (main), `wt-web`, `wt-opencode`, `wt-motor`. No escribir en el worktree de otro.
- Sin canal directo entre IAs: se usan archivos en `C:\Users\david\AppData\Local\Temp\opencode\` (`CLAUDE_A_OPENCODE.md` y `OPENCODE_A_CLAUDE.md`), mediados por el usuario.
- Idioma de la interfaz y de los mensajes al usuario: **español**.

## 3. Estado del repositorio
- `main`: `af21ed3`. Tags: `contratos-v0.1` (`ad958db`, contratos congelados) y `h0-04-completado` (según el coordinador, en `c6b4db6`).
- `claude/web`: incluye `codex/motor` (E1, merge `76f20d9`) y el arnés F en `tests/h2_eval/`; `tests/fixtures/h2` está en commits exclusivos (`da5e1a1`, `4018d97`). Contiene todo lo hecho por Claude, **sin mergear a `main`**.
- `opencode/h0-06`: `5857315`, revisada y **sin mergear** por orden del usuario.
- Nada se subió con `push`.

## 4. Qué se hizo, en orden
1. **H0-05 y H1 (web):** React + TypeScript + Vite en `apps/web`. Pantallas: proyectos, carga y ajustes, progreso por etapas, comparación original/vector/JEF, revisión localizada, variantes de tamaño, descargas, muestra física. Cliente simulado (mocks) y cliente HTTP real; pruebas Vitest y Playwright.
2. **Contratos v0.1:** congelados (`packages/contracts`, OpenAPI generado). La web tiene tipos escritos a mano.
3. **H0-04 verificado contra el backend real:** flujo proyecto → asset → revisión inicial → job; 202 en ~10 ms; `needs_review` en ~19 s con 14 avisos de satén; 6 artefactos; JEF de 150,0 × 142,8 mm / 6.789 puntadas / 3 bloques (releído con pyembroidery); muestra física y cancelación funcionan.
4. **Endurecimiento de la web:** timeout, códigos de incidencia, reintentos con backoff exponencial y jitter, enlaces de descarga de 300 s que se renuevan, manejo del 409 de artefactos, accesibilidad con axe, formulario de muestra física, mock con la forma exacta del backend real.
5. **H0-06 (regresiones de OpenCode):** revisado, aprobado con observaciones (es una regresión sobre archivos guardados, no re-exporta; el README reescribió frases ajenas; `pytest` no está en `requirements.txt`). **No mergeado.**
6. **H2 (imagen → geometría), preparación:**
   - UI: carga de PNG/JPG/SVG con etiqueta «SVG preparado» vs «Imagen para analizar», selector de proveedor «experimental», pantalla `AnalysisReview` (regiones, texto, colores, dudas, marcar regiones, aprobar, regenerar con otro proveedor).
   - **Contrato H2 aplicado** (`00e6fd2`): `GET /jobs/{id}/analysis`, `POST /jobs/{id}/analysis-decision`, `analysis_retry` en `RevisionResponse.kind` y transición `queued → vectorizing` para la continuación tras aprobar.
   - **Backend** (`87459d7`): interfaz de proveedores, adaptador de OpenAI (Responses API, salida estructurada, transporte inyectable), normalización a `AnalysisSpec`, disponibilidad real en `GET /profiles`, pipeline de imagen y decisión.
   - Manifiesto de las imágenes de prueba (`apps/web/docs/h2/`: esquema, ejemplo y validador).

## 5. Estado actual y límites (importante)
- **Vectorización E1 (Codex, mergeada en `claude/web` y conectada en `runner.py`):** imágenes planas PNG/JPEG → geometría en mm con huecos. El job termina en `needs_review` con `DENSITY_REVIEW_REQUIRED`: técnica y parámetros son provisionales hasta H3; no hay JEF ni `ready_for_sewout`. Límites: Anime Socks (1122×1402) excede la complejidad de E1; sin ejes centrales, satén ni degradados; el SVG editable no se descarga porque el contrato v0.1 exige JEF en el manifiesto.
- **El adaptador de OpenAI nunca se probó contra la red.** Faltan clave y modelo (van solo en la configuración privada del backend).
- **El adaptador de Ollama no existe**; figura «no disponible» en el catálogo.
- **Conjunto de imágenes de prueba:** hay 14 sintéticas en `tests/fixtures/h2/` (14 diseños distintos, hashes verificados, generadas por código). Faltan las dos escalas de Anime Socks para llegar a 15–20: la referencia es `Anime_Socks.png`, idéntica a `Anime_Socks_Bordado/trabajo/Referencia.png`; David debe confirmarla. Más adelante conviene sumar logos reales con permiso.
- El backend actual ejecuta bien `prepared_svg`; el camino de imagen llega hasta el análisis.
- Pruebas al cierre: Vitest 145, Playwright 40 (+2 contra backend real, opcionales), suite del motor 60 (`unittest`).

## 6. Reglas de producto que no se deben romper
- `ready_for_sewout` = archivos reales + controles digitales aprobados; **no** significa muestra aprobada. La muestra física (`untested/approved/needs_adjustment`) es aparte y nunca cambia el estado digital. El cliente no envía estados.
- Todo lo simulado va marcado (`simulated: true`, franja «Datos simulados»). Nunca pasar un mock por resultado real.
- Las claves de proveedores solo en la configuración privada del backend; nunca en la web ni en variables del navegador.
- Nunca cambiar de proveedor de IA en silencio.
- No confundir tamaño de página SVG con tamaño físico de puntadas; las variantes se regeneran desde la geometría.
- Ningún porcentaje de éxito sin medirlo; no declarar éxito general por un solo logo.
- No inventar hashes ni URLs que parezcan reales; no ocultar avisos (los 14 avisos de satén se muestran todos).

## 7. Decisiones del usuario vigentes
- Alcance de Claude: `apps/web` y `tests/e2e`, y backend/contratos/worker **solo en `claude/web`**, sin merge a `main`.
- Reintento = job nuevo sobre la misma revisión (1:N). Todo SVG subido es `prepared_svg` con `ai_provider: none`.
- Autenticación: HTTP Basic desde el navegador (sin `service_token`, o el navegador no pide credenciales).
- Se puede registrar una muestra física con el job en `needs_review`; los archivos de un `needs_review` se muestran con aviso de «no listos para prueba».
- Un análisis sin dudas no pausa; la aprobación obligatoria sería un cambio aparte (H2.1).

## 8. Pendientes y bloqueos
1. Confirmar la referencia de Anime Socks y sumar sus dos escalas al manifiesto.
2. Clave y modelo de OpenAI, tope de costo por trabajo; modelo y hardware para Ollama.
3. Paquete E (vector y geometría, propuesto para Codex): interfaz y reparto en `h2/E-interfaz.md`, pendientes de que David autorice el traslado de los commits de fixtures a `codex/motor` y de que Codex confirme la firma. Paquete F (evaluación, Claude) depende de E.
4. Decisión del usuario sobre mergear H0-06 y, más adelante, `claude/web` a `main`.
5. Deudas menores: «ver más» en listas paginadas, fotos de la muestra (`photo_asset_ids`), foco al cambiar de pantalla, regresión que vuelva a exportar con Ink/Stitch.

## 9. Dónde está cada cosa y cómo verificar
- `apps/web/` (web), `apps/web/mocks/` (fixtures simulados), `apps/web/docs/` (**`H0-05-recorrido-web.md`** es el documento principal; `H2-plan-y-pedidos.md`; `h2/`).
- `tests/e2e/` (Playwright; `playwright.real.config.ts` es opcional y requiere el backend en `localhost:8000`).
- `packages/contracts/`, `services/api/`, `workers/embroidery/`, `tests/engine/`.
- Web: `cd apps/web && npm run typecheck && npm test && npm run build`. E2E: `cd tests/e2e && npx playwright test`.
- Motor: `python -m unittest discover -s tests/engine -p "test_*.py"` con un Python 3.12+ que tenga `fastapi`, `pydantic==2.14.1`, `pillow` y `pyembroidery` (se usó el venv de `wt-opencode` como intérprete).
- Backend local: ver `services/api/docs/CONFIG.md` (`EMBROIDERY_API_CONFIG` apuntando a un JSON privado, ignorado por git).

## 10. Trampas conocidas
- Los archivos del repo mezclan fines de línea (LF/CRLF por `autocrlf`): las ediciones multilínea deben tolerarlo; el parche de contrato se guarda sin conversión (`*.patch -text`).
- No ejecutar `npx` en la raíz del repo (crea una carpeta `node_modules` de caché ahí); usar `npm run` dentro de `apps/web`.
- Existen hallazgos reales del backend ya documentados: 14 avisos idénticos con los mismos `object_ids` (`source_object_mapping_verified: false`), `original_download` nulo para SVG, catálogo de `providers` vacío antes de H2.
