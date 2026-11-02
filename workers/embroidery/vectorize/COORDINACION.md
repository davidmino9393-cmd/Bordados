# Coordinación E / API / F

Propósito: trabajar en paralelo con responsabilidades separadas y entregas por commit.

Contenido: [Plan](#plan), [Canal](#canal), [Aceptación](#aceptación), [Referencias](#referencias).

## Plan

| Trabajo | Responsable | Área / base |
|---|---|---|
| Conectar E, persistir revisión y mostrar avisos | Claude | API/web; motor `4a7fd6b` fijo |
| Evaluación independiente F | Claude | `tests/h2_eval`; informar hash exacto de E |
| Investigar y corregir paleta sin borrar geometría | Codex | E y pruebas `tests/engine` |
| Traslados de commits y merges | David | Autorización expresa; Codex no fusiona |

### Agents & Skills

| Fase | Agente | Skills |
|---|---|---|
| Trazado compacto | Implementador Python delegado | `core` |
| Regresiones y evidencia | Codex principal | `core` |
| Revisión independiente | Revisor delegado | `core` |

La complejidad quedó corregida en `0df2dfc`; `4a7fd6b` localiza regiones. `2fbb6ca` agrega investigación, sin cambiar E. Claude reportó F estructural 14/14 y color pendiente. Próximo: controles → candidato aislado → trazado/recursos → revisión → nuevo hash → F. Firma, modelos y estados no cambian.

## Canal

Buzón acordado: `C:/Users/david/AppData/Local/Temp/opencode/`.

- Codex escribe `CODEX_A_CLAUDE.md`; Claude escribe `CLAUDE_A_CODEX.md`.
- Cada entrega comunica rama/hash, pruebas, limitaciones y lo que necesita del otro.
- Hay confirmaciones de recepción. Codex no montó watcher persistente: mensaje depositado no equivale a nueva respuesta; leer el buzón al retomar.
- Mientras se edita E, F usa el último commit entregado. Nueva evaluación solo tras el siguiente hash y aviso.
- Usar las rutas absolutas del buzón, no `$env:LOCALAPPDATA`: el sandbox lo redirige. Agregar mensajes sin sobrescribir los anteriores. Los acuerdos permanentes quedan en Git.

## Aceptación

- Reproducir las 425078 aristas medidas de la referencia a las dos escalas sin filtros por tamaño ni reescalado del raster.
- Mantener límite genérico, recursos acotados y cancelación; exceso devuelve incidencia controlada.
- Admitir contornos no demuestra fidelidad visual: conservar avisos de paleta/fondo y H3 pendiente.
- Claude repite F por commit; IoU y evaluación semántica siguen a cargo de F.

## Referencias

- [Interfaz y límites](README.md)
- [Integración para Claude](HANDOFF.md)
- [Entrada del relevo](CONTINUAR.md) · [Próxima tarea](PROXIMA_TAREA.md)
