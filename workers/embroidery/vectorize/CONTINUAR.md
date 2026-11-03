# Continuar Codex motor

Propósito: retomar sin depender del chat. Snapshot: 2026-11-02; verificar entregas más recientes en Git y buzón.

Contenido: [Arranque](#arranque), [Estado](#estado), [Siguiente paso](#siguiente-paso), [Referencias](#referencias).

## Arranque

1. Verificar `Get-Location`, `rtk git status --short --branch` y `rtk git log -6 --oneline`. Ruta esperada: `C:\dev\wt-motor`; rama: `codex/motor`. No cambiar de rama ni crear worktrees.
2. Leer completos [AGENTS](../../../AGENTS.md), [plan maestro](../../../PLAN_MAESTRO.md), [contratos y calidad](../../../CONTRATOS_Y_CALIDAD.md), [tareas iniciales](../../../TAREAS_INICIALES.md) y [trabajo entre IAs](../../../TRABAJO_CON_VARIAS_IAS.md).
3. Leer [reglas vigentes](ESTADO_Y_REGLAS.md), [reproducción](REPRODUCIR.md) y ambos mensajes del [buzón](COORDINACION.md#canal). Respetar cambios más recientes del usuario.
4. Continuar por [PROXIMA_TAREA](PROXIMA_TAREA.md); no repetir inventario, contratos ni el Bridge fallido. CLI es la ruta oficial.

Las skills son opcionales por decisión del usuario; catálogo disponible en `.agents/skills/skill-index.json`. El kit no amplía el alcance ni exige crear otra estructura de proyecto.

## Estado

| Commit | Entrega |
|---|---|
| `094956a` | Fixtures sintéticos de `da5e1a1`, trasladados con permiso |
| `5e9897e` | E1: PNG/JPEG → máscaras → documento mm y SVG editable |
| `0df2dfc` | Contornos compactos; límite 500000 aristas |
| `4a7fd6b` | Regiones incoherentes localizadas en `region_ids` |
| `2fbb6ca` | Investigación de color; no cambia E en producción |

Contrato local: v0.1 congelado, tag `contratos-v0.1` en `ad958db`; los modelos concretos prevalecen sobre propuestas antiguas.

**Actualización (claude/web):** David autorizó promover `kmeans=3` (constante `QUANTIZER_KMEANS_PASSES`, método `e1-pixel-mask-v2`; Anime Socks 425078 → 110028 aristas, SVG ~2 MB) porque Codex se quedó sin tokens; la evidencia de F está en `tests/h2_eval/informes/`. **Revisión hecha por Claude (sin esperar a Codex, por indicación de David):** `tests/h2_eval/informes/revision-e-v4.md`; el filtro de borde ahora solo descarta píxeles débiles que tocan el fondo (antes abría agujeros en diseños casi blancos con ruido). Después: color representativo del grupo = miembro mediano (`e1-pixel-mask-v3`). Los «trazos oscuros perdidos» eran contornos de luminancia 171–191 (ver `tests/h2_eval/informes/trazos-oscuros-anime-socks.md`); **Máscara por cobertura (`e1-pixel-mask-v4`)**: los píxeles de borde con cobertura < 0,5 respecto del color de su grupo salen de la máscara (solo con fondo blanco quitado), los colores se recalculan con el núcleo; evidencia `coverage_threshold` y `fringe_pixels_removed`; informe `tests/h2_eval/informes/cobertura-v4-vs-v3.md`. **Ancho mínimo bordable**: política = medir y avisar, nunca borrar ni engrosar (`thin_features.py`, evidencia `minimum_feature`, fracción por color en la incidencia `DENSITY_REVIEW_REQUIRED`; ancho mínimo provisional 0,4 mm, sin calibrar); informe `tests/h2_eval/informes/ancho-minimo-bordable.md`. Lo que se hace con lo fino lo decide H3. Lo que sigue describe el estado previo.

**Imagen → JEF (claude/web, 2026-11-02, sin commitear):** David pidió una página que devuelva el JEF terminado, así que la compuerta «sin JEF hasta H3» se levantó con parámetros de referencia (Anime Socks: gabardina, estabilizador grueso, 400 ppm; no calibrados, y cada trabajo lo avisa). `inkstitch.py` suma `to_reference_inkstitch_svg` y `reference_issues`; `stitchable.py` quita manchas de menos de 1 mm² y capas casi blancas y simplifica los contornos; la API los usa en `runner._digitize_vectorized` y el worker escribe el código de bastidor del perfil en el JEF. Pendiente de E: satin y puntada corrida para líneas finas (hoy todo es relleno), elegir qué colores se bordan y medir la calidad física. Ver `apps/web/docs/ESTADO_PARA_MAIN.md` (última sección) y `COMO_USAR.md`.

El motor sigue idéntico a `4a7fd6b`. La referencia se traza a ambas escalas: 425078 aristas, 23655 subpaths, 5839 huecos; SVG alrededor de 7 MB. Esto no demuestra fidelidad visual.

Claude reportó F estructural sobre `4a7fd6b`: 14/14 PNG/JPEG, 2 SVG omitidos, 0 errores. El color sigue fallando: la paleta pierde letras y flores. No confundir IoU contra la misma regla de fondo con calidad semántica.

## Siguiente paso

Ya se comparó `kmeans=3` en trazado aislado: [10 casos, 40 ejecuciones](../../../tests/engine/evidence/trace-candidate/README.md). Conserva máscara total y determinismo, pero cambia mucho los huecos por color. Siguiente: controles de topología/texto antes de promoverlo. Sigue experimental, sin JEF/H3.

Claude mantiene API/web/F; Codex mantiene E. La coordinación tiene confirmaciones, pero Codex no montó watcher persistente. El relevo no autoriza merges, push ni cambios de contrato.

## Referencias

- [Interfaz E](README.md) · [Integración para Claude](HANDOFF.md)
- [Investigación y previews](../../../tests/engine/evidence/quantization-research/README.md)
- [Evidencia de complejidad](../../../tests/engine/evidence/h2-complexity/README.md)
