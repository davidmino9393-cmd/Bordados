# Continuar Codex motor

Propósito: retomar sin el chat. Snapshot: 2026-11-02; contrastar Git y buzón antes de actuar.

Contenido: [Arranque](#arranque), [Estado actual](#estado-actual), [Siguiente trabajo](#siguiente-trabajo), [Referencias](#referencias).

## Arranque

1. Verificar `Get-Location`, `rtk git status --short --branch` y `rtk git log -6 --oneline`: `C:\dev\wt-motor`, rama `codex/motor`. No crear ramas/worktrees ni deshacer cambios ajenos.
2. Leer [AGENTS](../../../AGENTS.md), [plan maestro](../../../PLAN_MAESTRO.md), [contratos](../../../CONTRATOS_Y_CALIDAD.md), [tareas](../../../TAREAS_INICIALES.md) y [trabajo entre IAs](../../../TRABAJO_CON_VARIAS_IAS.md).
3. Leer [reglas](ESTADO_Y_REGLAS.md), [reproducción](REPRODUCIR.md), [próxima tarea](PROXIMA_TAREA.md) y ambos mensajes del [buzón](COORDINACION.md#canal).

Skills opcionales por decisión del usuario; catálogo `.agents/skills/skill-index.json`. El kit no amplía el alcance.

## Estado actual

La base integrada es `051d8ce`: `main` se propagó a este worktree por Claude con autorización de David. No fue un merge ejecutado por Codex. Incluye fixtures completos, H2, seis cambios de contrato ratificados, E v4 y material H3. **No repetir la investigación ni la promoción inicial de `kmeans=3`; `4018d97` ya está integrado.**

E usa `e1-pixel-mask-v4`: cuantización refinada, color representativo mediano y cobertura de borde. `thin_features.py` mide y avisa: nunca borra ni engrosa; 0,4 mm sigue provisional.

Codex revisó E v4 independientemente. La corrección `2507edf` usa kernel `ceil` incluso par, exterior cero y filtro acotado; corrige igualdad física afectada por coma flotante. No cambia geometría, paleta ni calibración. Ver [hallazgos y resultados](../../../tests/engine/evidence/v4-review/README.md).

Cierre verificado: motor 121 pruebas (4 omitidas); evaluación 16 (1 omitida); sin fallos. F: 14 raster, 8 comprobaciones 14/14 y 2 SVG omitidos.

Los dos exports JEF históricos están identificados por SHA y comparados con sus referencias: comandos y paletas coinciden; difieren bytes de cabecera. Eso **no identifica qué archivo copió/renombró y cosió David**, ni aprueba físicamente candidatos.

## Siguiente trabajo

La aplicación no está terminada: imagen → JEF aún requiere técnicas/calibración H3. David postergó coser la muestra; no iniciar esa actividad por leer este relevo. Se puede continuar revisión software con nueva evidencia y coordinar condiciones/archivo cosido cuando existan.

OpenAI real, Ollama con visión/hardware reales y licencia EmbroideryPart15 siguen pendientes externos reportados por Claude.

## Referencias

- [Interfaz](README.md) · [Integración](HANDOFF.md)
- [Identidad de JEF](../../../tests/engine/evidence/v4-review/jef-identity.json)
- [Protocolo H3](../../../tests/calibration/h3/PROTOCOLO_H3.md)
