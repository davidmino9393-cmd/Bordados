# Continuar Codex motor

Propósito: entrada única para retomar el trabajo sin depender del chat. Corte: 2026-11-02, antes del commit documental de este relevo.

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

El motor sigue idéntico a `4a7fd6b`. La referencia se traza a ambas escalas: 425078 aristas, 23655 subpaths, 5839 huecos; SVG alrededor de 7 MB. Esto no demuestra fidelidad visual.

Claude reportó F estructural sobre `4a7fd6b`: 14/14 PNG/JPEG, 2 SVG omitidos, 0 errores. El color sigue fallando: la paleta pierde letras y flores. No confundir IoU contra la misma regla de fondo con calidad semántica.

## Siguiente paso

Probar MEDIANCUT con `kmeans=3` en un candidato aislado y en el recorrido completo de E. La investigación mejora error RGB en 6/9 casos, empata 1 y empeora 2. No se incorporó a producción ni habilita JEF/H3.

Claude mantiene API/web/F; Codex mantiene E. La coordinación tiene confirmaciones, pero Codex no montó watcher persistente. El relevo no autoriza merges, push ni cambios de contrato.

## Referencias

- [Interfaz E](README.md) · [Integración para Claude](HANDOFF.md)
- [Investigación y previews](../../../tests/engine/evidence/quantization-research/README.md)
- [Evidencia de complejidad](../../../tests/engine/evidence/h2-complexity/README.md)
