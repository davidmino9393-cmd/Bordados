# H0-01: entorno y extracción

Propósito: distinguir observaciones actuales, evidencia histórica y verificaciones pendientes.

Contenido: [Entorno](#entorno), [extracción](#extraccion), [relacionados](#relacionados).

## Entorno

| Componente | Observado en este worktree/equipo | Evidencia histórica |
|---|---|---|
| Python en PATH | 3.10.11; sin las 4 bibliotecas del requirements ni Pydantic/FastAPI | Informe declara Python 3.12.14 |
| Python empaquetado | Ejecutable referenciado presente; metadato 3.12.14 | Fallback local de reproducir.mjs |
| Node | v26.13.0 | Versión no fijada en script |
| Inkscape | Fuera del PATH; ejecutable original presente; metadato 1.4.2 | Informe: 1.4.2 |
| Ink/Stitch | Fuera del PATH; ejecutable original presente, sin versión de archivo | Informe: 3.2.2, windows-x86_64, esquema SVG 3 |
| Docker / WSL | Comandos localizados | Daemon, distro y funcionamiento no probados |
| MCP Bridge | No evaluado en H0-01 | Primera alternativa a probar en H0-03 |

Los metadatos no prueban que un ejecutable funcione. No se abrió escritorio, lanzó Inkscape/InkStitch ni ejecutó el pipeline. No se instalaron las dependencias históricas.

## Extraccion

- Adaptador futuro: rutas externas configurables; directorio exclusivo de job; argumentos controlados; timeout/cancelación; stdout binario y stderr íntegro; errores estructurados en lugar de assert.
- Perfil de máquina/formato: bastidor geométrico y código JEF separados, límites de puntada/área/tolerancias y método de conteo explícitos.
- Auditoría: distinguir comandos JUMP crudos de desplazamientos y tripletes cero usados como cortes; no afirmar ejecución física del corte.
- Preview: identificar si deriva del plan o de la relectura JEF; solo esta última sirve como representación del archivo exportado.
- Rellenos y satin: conservar diagnósticos por objeto; reparación con trazabilidad y validación de huecos/raíles. El éxito binario no elimina revisión geométrica.
- H0-03: probar MCP Bridge sin sesión interactiva. Si falla, conservar fallo/versión/logs antes de evaluar Inkscape + CLI y dependencias de display. Ninguna alternativa está declarada viable todavía.
- H0-06: comparar comandos/coordenadas normalizados, no solo SHA-256; variación de fecha JEF no implica cambio de puntadas.

## Relacionados

[Matriz](README.md), [índice y hashes](source-inventory.json), [tareas](../../../TAREAS_INICIALES.md).
