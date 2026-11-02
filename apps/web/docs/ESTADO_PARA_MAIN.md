# Estado de `claude/web` para decidir el paso a `main`

Propósito: que David decida con información. **Nada de esto está en `main` ni se subió.** David **ratificó los seis cambios de contrato** de abajo (2026-11-02); falta su decisión sobre el paso a `main`. Lo escribió Claude Code; Codex y OpenCode no revisaron los cambios de `claude/web` posteriores a sus entregas.

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
| Motor (`unittest`) | 114 pruebas OK |
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
- **Revisión pendiente de Codex** sobre mis cambios en `segmentation.py`, `pipeline.py` y `thin_features.py`, que él mantiene.
- **Rendimiento:** E1 en Anime Socks ~3,5 s; mediana de F ~1 s por imagen.

## Decisiones para David
1. ~~¿Se ratifican los seis cambios de contrato?~~ **Ratificados.**
2. ¿Se pasa `claude/web` a `main` ahora, o después de que Codex revise `e1-pixel-mask-v4`?
3. Para destrabar lo no probado: clave y modelo de OpenAI con tope de costo, y modelo de visión y hardware para Ollama.
