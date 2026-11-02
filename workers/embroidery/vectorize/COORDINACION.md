# Coordinación E / API / F

Propósito: trabajar en paralelo con responsabilidades separadas y entregas por commit.

Contenido: [Plan](#plan), [Canal](#canal), [Aceptación](#aceptación), [Referencias](#referencias).

## Plan

| Trabajo | Responsable | Área / base |
|---|---|---|
| Conectar E1, persistir revisión y mostrar avisos | Claude | API/web; E1 `5e9897e` fijo |
| Evaluación independiente F | Claude | `tests/h2_eval`; informar hash exacto de E |
| Corregir límite de complejidad sin borrar geometría | Codex | `workers/embroidery/vectorize`, `tests/engine` |
| Traslados de commits y merges | David | Autorización expresa; Codex no fusiona |

### Agents & Skills

| Fase | Agente | Skills |
|---|---|---|
| Trazado compacto | Implementador Python delegado | `core` |
| Regresiones y evidencia | Codex principal | `core` |
| Revisión independiente | Revisor delegado | `core` |

Orden: medir máscara → reducir almacenamiento → verificar exactitud/cancelación/límite → revisar → commit → avisar a Claude. La firma, los modelos y los estados no cambian.

## Canal

Buzón acordado: `C:/Users/david/AppData/Local/Temp/opencode/`.

- Codex escribe `CODEX_A_CLAUDE.md`; Claude escribe `CLAUDE_A_CODEX.md`.
- Cada entrega comunica rama/hash, pruebas, limitaciones y lo que necesita del otro.
- Mensaje depositado no equivale a recibido. Confirmación en respuesta; sin watcher David debe pedir la lectura.
- Mientras se edita E, F usa el último commit entregado. Nueva evaluación solo tras el siguiente hash y aviso.
- Los acuerdos permanentes quedan en Git; los mensajes del buzón coordinan su ejecución.

## Aceptación

- Reproducir las 425078 aristas medidas de la referencia a las dos escalas sin filtros por tamaño ni reescalado del raster.
- Mantener límite genérico, recursos acotados y cancelación; exceso devuelve incidencia controlada.
- Admitir contornos no demuestra fidelidad visual: conservar avisos de paleta/fondo y H3 pendiente.
- Claude repite F por commit; IoU y evaluación semántica siguen a cargo de F.

## Referencias

- [Interfaz y límites](README.md)
- [Integración para Claude](HANDOFF.md)
