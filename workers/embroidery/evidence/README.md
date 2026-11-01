# H0-03: evidencia observada

Propósito: demostrar exportación/relectura real y fallos controlados. No equivale a aprobación digital completa ni muestra física.

Contenido: [Resultados](#resultados), [fallos](#fallos), [entorno](#entorno), [verificación](#verificacion), [relacionados](#relacionados).

## Resultados

| Job | mm desde JEF | Aguja | Bloques | Cortes interpretados | Avisos nativos |
|---|---|---:|---:|---:|---:|
| cli-main-final | 150×142.8 | 6789 | 3 | 53 | 14 |
| cli-small-final | 126.2×120 | 5600 | 3 | 53 | 14 |

Ambos se generaron desde copias de SVG preparados, con Ink/Stitch v3.2.2; pyembroidery 1.5.1 releyó archivos nuevos. Los hashes binarios cambian por cabecera temporal; comandos/coordenadas normalizados y tabla de paleta coinciden con sus referencias. No se usaron conteos como condición de éxito del worker.

Cada job conserva JEF, preview desde JEF, diagnóstico SVG completo, comandos, hashes y logs. La paleta de preview es la aproximación del catálogo JEF, no los tonos físicos ideales. Todos los avisos “Satin has no rungs” permanecen como revisión pendiente, sin atribuirles objetos que no fueron mapeados.

## Fallos

- invalid-svg: INPUT_UNREADABLE, XML mal formado, antes de lanzar motor.
- missing-binary: WORKER_EXPORT_FAILED, WinError 2; stderr/registro de lanzamiento guardados.
- timeout-final: WORKER_TIMEOUT usando **Ink/Stitch real**, plazo deliberado de 0.001 s. Arranque suspendido → asignación al job → ejecución; TerminateJobObject confirma 0 procesos activos.
- timeout: intento anterior conservado; taskkill falló por credenciales del sandbox. Se sustituyó por Windows Job Objects. El test automatizado además crea padre+hijo reales y comprueba que ambos terminan.
- Bridge: [instalación y exportación fallidas](bridge/README.md), registradas antes del pivot.

## Entorno

Windows; Inkscape 1.4.2 verificado por --version; Ink/Stitch v3.2.2 contrastado con VERSION y hash del ejecutable. Procesos sin consola visible, stdin cerrado y sin manipulación de escritorio.

Docker Linux: pipe dockerDesktopLinuxEngine no disponible. WSL: solo docker-desktop detenido en consulta autorizada. **No probado Linux ni servicio Windows en sesión 0**; no se deduce su viabilidad de este resultado.

## Verificacion

`python workers/embroidery/verify_evidence.py` con deps del worker: relee artefactos y comprueba 71 originales y 29 archivos congelados. Solo admite las 2 notas documentales 1:N aprobadas, con hashes y schemas intactos (documentation-clarification.json). Resultado: summary.json.

Pruebas: `python -m unittest discover -s tests/engine -p "test_*.py"`: 16 aprobadas. Las fallas inyectadas son deliberadas; los dos JEF y previews son reales.

## Relacionados

[Resumen JSON](summary.json), [JEF grande](cli-main-final/output.jef), [JEF pequeño](cli-small-final/output.jef), [worker](../README.md), [Bridge](bridge/README.md).
