# H0-04: evidencia HTTP con motor real

Propósito: demostrar que la API crea un job, responde antes de ejecutar el worker, conserva el estado observado y entrega un JEF real mediante una URL autorizada de corta duración. No es aprobación digital ni muestra física.

Contenido: [Resultados](#resultados), [Verificación](#verificacion), [Límites](#limites), [Relacionados](#relacionados).

## Resultados

| Dato | Valor |
|---|---|
| Entrada | `Anime_Socks_Bordado/Anime_Socks_InkStitch.svg` (207834 bytes) |
| `POST /jobs` | 202 en 7.65 ms; estado inicial `queued` |
| Duración observada | 16663.34 ms |
| Estado final | `needs_review` |
| Etapas | analysis/vectorization omitidas; digitizing y validating completadas |
| JEF | 14816 bytes; SHA-256 `747d0f44ca0ef4e059dad98d8213cd6a1199ba01dd97ee38af912112c2b455e3` |
| Descargas | 6/6 con HTTP 200, hash coincidente y `Cache-Control: no-store` |
| Relectura JEF | 150×142.8 mm; 6789 puntadas; 3 bloques; 53 cortes interpretados |
| Avisos | 14 `review_required`; 0 errores bloqueantes |
| Aprobación física | `untested` |

Los comandos/coordenadas normalizados coinciden con la referencia `cli-main-final`. La cabecera temporal cambia el hash binario; el artefacto auditado es el descargado en esta ejecución.

## Verificacion

- `summary.json`: latencia, duración, etapas, hashes, comparación normalizada, descargas, métricas y límites.
- `job.json`: respuesta observada de `GET /jobs/{id}` en `needs_review`.
- `validation.json`: reporte de validación descargado, con checks no ejecutados y avisos nativos.
- `output.jef` y `preview.png`: artefactos descargados y comprobados contra el manifiesto.
- Pruebas automatizadas: `python -m unittest discover -s tests/engine -p "test_*.py"`; 27 aprobadas, incluidas 4 de API con worker falso.

## Limites

- `digital_checks_passed=false`: geometría, satin, recorrido y revisión visual no están implementados.
- No se verificó ejecución física de cortes ni costuras.
- Observado en Windows con procesos ocultos y stdin cerrado; no se deduce comportamiento en Linux ni sesión 0.
- La API es un único proceso con SQLite; autenticación multiusuario y persistencia de producción quedan para H1.

## Relacionados

[Resumen](summary.json), [Job](job.json), [Validación](validation.json), [JEF](output.jef), [Preview](preview.png), [Comandos](raw-commands.json), [API](../../README.md), [Worker](../../../workers/embroidery/README.md).
