# Estado de `claude/web` para decidir el paso a `main`

Propósito: registrar qué pasó a `main` y qué falta. Los 83 commits de abajo pasaron a `main` por merge local (`ffd63b8`, 2026-11-02; sin push). David **ratificó los seis cambios de contrato** de la tabla. Lo posterior —imagen → JEF— está en la última sección y pasó a `main` por el merge `33a9f33` (2026-11-03; sin push): Codex le dio GO para pruebas manuales y David ratificó sus dos cambios de contrato. Lo escribió Claude Code; salvo imagen → JEF, Codex y OpenCode no revisaron los cambios de `claude/web` posteriores a sus entregas.

Contenido: [Qué contiene](#qué-contiene) · [Contratos que cambian](#contratos-que-cambian) · [Verificación](#verificación) · [Riesgos](#riesgos) · [Decisiones](#decisiones-para-david)

## Qué contiene
75 commits respecto de `main`, 284 archivos (+27.997 / −80).

| Área | Archivos | Qué hay |
|---|---:|---|
| `apps/web` | 112 | App React: proyectos, carga, progreso, comparación, revisión, análisis H2, muestra física con fotos, descargas |
| `services/api` | 8 | Análisis H2 (OpenAI con transporte inyectable, sin probar contra la red), pipeline de imagen, `analysis-decision`, `original_download` firmado, `purpose` de assets |
| `workers/embroidery` | 15 | E1 de Codex (`vectorize/`) con mis cambios: cuantización `kmeans=3`, color mediano, máscara por cobertura, ancho mínimo bordable (`e1-pixel-mask-v4`) |
| `packages/contracts` | 7 | Ver abajo |
| `tests` | 150 | Motor, F (`tests/h2_eval`), fixtures H2 (16 entradas), e2e, muestra de calibración física H3 (`tests/calibration/h3`: JEF, planilla y protocolo para coser y medir) |

Incluye H0-06 de OpenCode (regresiones sobre archivos guardados) y la investigación de Codex hasta `cf447b4`.

## Contratos que cambian (ratificados por David)
Todos aditivos o relajaciones sobre `contratos-v0.1`; ninguno cambia el significado de un campo existente.

| Cambio | Por qué |
|---|---|
| `GET /jobs/{id}/analysis`, `POST /jobs/{id}/analysis-decision` (`approve` / `change_provider`) | Análisis visual de H2 |
| `RevisionResponse.kind` admite `analysis_retry` | Cambiar de proveedor crea una revisión |
| Transición `queued → vectorizing` solo para una continuación con padre y `analyzing` omitido con motivo | Un análisis aprobado continúa sin repetirse |
| `ArtifactManifest.reread_metrics` pasa a ser **opcional** | Sin JEF no hay relectura; `ready_for_sewout` sigue exigiéndola (prueba) |
| `SourceAsset.purpose = design \| sewout_photo` (por defecto `design`) | Fotos de muestras físicas, que no son diseños |
| `original_download` ahora lo emite el backend | Antes era siempre nulo |

La relajación de `reread_metrics` es la que más conviene que apruebes: un cliente que dé por hecho que siempre existe tendría que contemplar `null`.

## Verificación
Corrida completa sobre el último commit:

| Suite | Resultado |
|---|---|
| Motor (`unittest`) | 115 pruebas OK |
| Evaluación F (`tests/h2_eval`) | 16 pruebas OK (1 omitida); `run_eval.py`: 14 PNG/JPEG, 0 errores, 8 comprobaciones 14/14 |
| Web (Vitest, typecheck, build) | 156 pruebas OK |
| e2e con mocks (Playwright) | 42 OK |
| e2e contra el backend real | 4 OK (SVG con Ink/Stitch, cancelación, imagen con E1, Anime Socks) |
| Regresión que reexporta con Ink/Stitch | OK: JEF idéntico, comando por comando, al entregado |

## Riesgos
- **Lo no probado:** OpenAI contra la red real (falta clave, modelo y tope de costo) y Ollama (el adaptador existe y está probado solo con transporte falso: falta un modelo de visión real). El análisis de IA de los recorridos reales está simulado y rotulado.
- **Sin JEF desde imágenes:** E1 genera geometría con parámetros provisionales sin calibrar; los trabajos de imagen terminan en `needs_review`. Nada afirma que algo esté listo para coser.
- **Calidad de color:** Anime Socks conserva letras y contornos con 3 colores, pero el rosa de pétalos queda casi blanco. La medición de legibilidad real necesita muestras cosidas (H3).
- **Ancho mínimo bordable:** 0,4 mm es un supuesto sin calibrar; se mide y avisa, no se aplica.
- **Revisión de E:** la hizo Claude, sin esperar a Codex por indicación de David (`tests/h2_eval/informes/revision-e-v4.md`): un fallo real corregido (la regla de cobertura abría agujeros en diseños casi blancos con ruido; ahora solo descarta el borde que toca el fondo). Es una revisión del propio autor: una mirada ajena (Codex o la IA local de solo lectura) sigue siendo recomendable.
- **Rendimiento:** E1 en Anime Socks ~3,5 s; mediana de F ~1 s por imagen.

## Decisiones para David
1. ~~¿Se ratifican los seis cambios de contrato?~~ **Ratificados.**
2. ¿Se pasa `claude/web` a `main` ahora, o después de que Codex revise `e1-pixel-mask-v4`?
3. Coser y medir la muestra de calibración (`tests/calibration/h3`, **pendiente: David la hará más adelante**): sin ella, ancho mínimo, densidad y compensación siguen provisionales y no hay JEF desde imágenes.
4. Para destrabar lo no probado: clave y modelo de OpenAI con tope de costo, y modelo de visión y hardware para Ollama.

## Imagen → JEF (2026-11-02; en `main` desde 2026-11-03)
David pidió una página donde cargar una imagen y recibir el JEF terminado. Guía de uso: [COMO_USAR.md](../../../COMO_USAR.md).

| Qué | Detalle |
|---|---|
| Flujo | Imagen → E1 (píxeles a máscaras) → filtro de lo bordable (`stitchable.py`) → SVG de Ink/Stitch con parámetros de referencia (`inkstitch.py`) → worker real → JEF releído → `needs_review` con el JEF descargable |
| Parámetros | Los de Anime Socks (gabardina, estabilizador grueso, 400 ppm): relleno a 0,45 mm, puntada de 2,5 mm, compensación de 0,2 mm, sin base. **No calibrados**: cada trabajo lo avisa (`DENSITY_REVIEW_REQUIRED`) |
| Filtro de lo bordable | Quita manchas de menos de 1 mm² y capas casi blancas (se toman como fondo y no gastan un hilo); simplifica contornos (0,1 mm o 3/4 de píxel). Lo quitado se avisa con números (`VISUAL_MISMATCH`) |
| Tamaño | Se vectoriza dentro de un destino 0,4 mm más chico: la compensación engorda 0,2 mm por lado y el bordado debe entrar en el pedido |
| Bastidor | El worker escribe en la cabecera del JEF el código del perfil (SQ20b = 4), porque el exportador lo deduce por tamaño (un logo chico sale como 126 × 110 y fallaba `HOOP_INCOMPATIBLE`). La salida cruda queda en `exporter-output.jef` y el cambio, en `jef_header_patch` |
| Web | «Sin análisis de IA» en el selector; tarjeta «Tu archivo de bordado» arriba de todo; una imagen no ofrece correcciones (el servidor solo admite revisiones iniciales) |
| Archivo | El JEF se llama como la imagen subida |
| Variantes de tamaño | `POST /projects/{id}/revisions` con `kind: size_variant` (ya declarado en el contrato) crea una revisión nueva con enlaces al origen y un job hijo que vuelve a generar desde la entrada original; el origen no cambia. Con un SVG preparado, `svg_fit.py` cambia `width` y `height` de la hoja (el `viewBox` queda) antes de digitalizar, y los parámetros en mm no se escalan; sin `viewBox` o sin tamaño absoluto se rechaza con 422. En el job base de un SVG preparado el destino es un límite, no una escala (solo una variante cambia el tamaño; la web lo avisa en el formulario). Solo si el origen terminó (si no, 409) y es del mismo proyecto. Las correcciones siguen sin admitirse. La web ofrece el formulario también en la pantalla de revisión, con aviso si el tamaño no entra en el bastidor |
| Configuración | `raster_digitizing` (`true`), `digitizing_timeout_s` (`600`) |

Contratos que cambian (**ratificados por David el 2026-11-03**):

| Cambio | Por qué |
|---|---|
| `JobCreate`: una imagen con `ai_provider: none` deja de rechazarse | Procesar sin IA es una elección explícita; sin esto, sin OpenAI ni Ollama no hay forma de usar una imagen |
| Transición `queued → vectorizing` también para una imagen con `ai_provider: none` y `analyzing` omitido con motivo | Idem: no hay padre que aprobara un análisis |

Verificación: motor 160 pruebas OK (4 omitidas) y web 163 Vitest, tsc y build de Vite, sobre el árbol de `main` tras el merge `2815531`; real end-to-end (navegador, API y Ink/Stitch reales): anillo en 9 s y Anime Socks en 2,2 min, ambos con JEF releído (código de bastidor 4). Límites conocidos: todo se borda como relleno (sin satin ni corrida), una capa casi blanca real se pierde, el tiempo con diseños complejos es de minutos, y `ready_for_sewout` sigue sin alcanzarse (faltan las comprobaciones geométricas). La calidad física del JEF de una imagen no se probó en tela.

Revisión independiente: Codex dio GO para pruebas manuales a `014e368` (informe en `codex/motor`, `tests/engine/evidence/independent-review/014e368/README.md`): R1 a R5 de la revisión de `c49573d` cerrados; motor 145 y evaluación 16 sin fallos. El GO no declara calibración ni `ready_for_sewout`.

Variantes de tamaño: en `main` desde el merge `2815531` (2026-11-03, sin push), con `da6efbf`, `29f73a8` y `25370ff`. Codex dio NO-GO a `da6efbf` porque la variante de un SVG preparado no cambiaba el tamaño: los tres `input.svg` eran idénticos al original y el JEF se releía 20,0 × 19,8 mm. `29f73a8` lo corrige ajustando `width`/`height` con el `viewBox` intacto; `25370ff` muestra el motivo del 422 en la web. Medición real e independiente sobre `29f73a8` (API + worker + Ink/Stitch reales, JEF releído con pyembroidery): 20×20 → 40×40 da 40,0 × 39,6 mm y 1388 puntadas; → 10×10 da 10,0 × 10,0 y 135; → 60×30 da 30,0 × 29,6 y 812 (con `contain` manda el alto); el job de origen conserva cuerpo y JEF. Con `pull_compensation_mm=0.2`, 40×40 da 40,8 y 10×10 da 10,8 y terminan `failed DIMENSIONS_EXCEEDED` (el original de 20×20 ya fallaba con 20,8); 60×30 da 30,8 × 29,6 y queda en `needs_review`. Nunca se exporta el tamaño original en silencio. Pendiente: revisión acotada de Codex sobre `29f73a8` y `25370ff`, muestra física H3, `codex/motor` y el helper compartido de límites/EXIF.

## Varios bordados por proyecto (2026-11-08)
David no podía generar un segundo archivo en su proyecto: la web crea una revisión inicial por cada «Generar bordado» y la API admitía una sola por proyecto (`REVISION_CONFLICT`, «El proyecto ya tiene una revisión inicial»; la web lo mostraba como «Los ajustes cambiaron desde otra sesión»).
**Contrato ratificado por David el 2026-11-08:** un proyecto admite varias revisiones iniciales, una por cada bordado, cada una con sus ajustes inmutables (el job los sigue exigiendo iguales). Cambió `create_revision` (se quitó el rechazo), el texto de `build_openapi.py` y `openapi.json` (solo `description`/`summary`, ningún esquema) y `packages/contracts/README.md`.
Verificación real (API + worker + Ink/Stitch reales, JEF releído con pyembroidery), tres SVG en un mismo proyecto: 20 mm con destino 40×40 → 20,0 × 19,8 mm; 30 mm con destino 60×60 → 30,0 × 29,6 mm; el de 20 mm otra vez con destino 80×50 → 20,0 × 19,8 mm; las tres revisiones `initial`, tres trabajos `needs_review` y `input_sha256` = `geometry_sha256` = SHA256 del archivo subido. Prueba nueva en `tests/engine/test_api.py`; motor 212 OK y evaluación 16 OK.
