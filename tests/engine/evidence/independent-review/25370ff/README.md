# GO — revisión acotada 29f73a8 + 25370ff

Propósito: cerrar V1 con los seis casos exigidos por David. Fecha: 2026-11-03.

Contenido: [Dictamen](#dictamen), [Mediciones](#mediciones), [Rechazos y web](#rechazos-y-web), [Comandos](#comandos), [Metodología](#metodología), [Entrega](#entrega), [Referencias](#referencias).

## Dictamen

**GO en el alcance solicitado**, sobre snapshot `25370ff9057a826996946035f3a1d60003c35d62`, que contiene `29f73a8bc3d3a623028ae96c8c3055f117a9a465`. Delta contra da6efbf. V1 de la revisión anterior queda cerrado. No hay bloqueante confirmado en los seis casos.

Código revisado: ajuste y rechazo previo a crear recursos en `services/api/embroidery_api/app.py:384`, transformación antes del worker en `runner.py:186`, `svg_fit.py:58`; presentación del motivo de INVALID_REQUEST en `apps/web/src/api/HttpApiClient.ts:51`. Snapshot extraído por hash mediante git archive; sin escribir en Claude ni modificar main.

## Mediciones

HTTP, API/store/runner, worker e Ink/Stitch reales; relectura independiente pyembroidery. STITCH filtrado por COMMAND_MASK: **puntadas de aguja**, no comandos totales.

| Caso | JEF releído | Puntadas | Comandos totales | Estado |
|---|---:|---:|---:|---|
| Base 20×20 | 20×19,8 mm | 402 | 404 | needs_review |
| 1: destino 40×40 | **40×39,6 mm** | **1388** | 1391 | needs_review |
| 2: destino 10×10 | **10×10 mm** | **135** | 137 | needs_review |
| 3: destino 60×30 | **30×29,6 mm** | **812** | 815 | needs_review |

Los tres casos coinciden exactamente con las referencias indicadas. Contain preserva la proporción: en 60×30 manda el alto. Se mantuvieron los parámetros físicos del fixture; no se escalaron puntadas JEF existentes.

SHA256 del SVG efectivamente recibido por el worker:

| Destino | SHA256 |
|---|---|
| Original | `99c8c4a1450ebc2441e28247e7b45fb64d528109fd44160608bcb90b7cfcd321` |
| 40×40 | `64f869f27bb0b76fd42e2f3640a8dc2990b087099d3b70dddf8428feab30fce1` |
| 10×10 | `8c552697b9ea4493046987e4402c64ab8780eaf91242359a85c3caa15008c4f9` |
| 60×30 | `0ed68f50149678fd0cf064aec66356033df64b1e978adb1a7ec7630392a18089` |

Caso 4: job completo, revisión y seis artefactos del origen permanecen idénticos después de cada variante y al final. JEF original SHA `d700c6d534623e9df12c8c62e7b8be5e768583879a7168f5cdf8f0da0154f0e1`. El manifiesto mantiene input_sha256 original y geometry_sha256 del SVG ajustado. JEF/SVG/raw-commands/resultados y registros conservados en svg-real/; todos los hashes completos constan en variant-api.json.

## Rechazos y web

Caso 5: **dos rechazos HTTP reales** con padres procesados por Ink/Stitch real:

- Sin viewBox: 422 INVALID_REQUEST; detail explica que falta viewBox.
- Con width/height relativos, 100%: 422 INVALID_REQUEST; detail explica que falta width absoluto.
- En ambos: 1 job y 1 revisión antes y después; **no se crean recursos**.

Caso 6: **Chrome real**, API real y un SVG sin viewBox cuyo job base se procesó con Ink/Stitch. El formulario de variante recibe el 422 real y muestra literalmente su detail legible. Después, dos respuestas sintéticas interceptadas solo para comprobar localización: 403 y 404 conservan sus mensajes por código e ignoran el detail sintético. No se usaron interceptores para el 422 ni el procesamiento SVG.

Build TypeScript/Vite correcto; **163 pruebas web aprobadas**. Playwright: **1 prueba aprobada**, 11,4 s. [Captura](browser-422.png), [traza](browser-trace.zip), [resultado](browser-detail.json), [log](browser-run.log). No se repitieron suites fuera del delta sin necesidad.

## Comandos

Desde `C:\dev\wt-motor`:

```powershell
git log -1 --format="%H%n%s" 29f73a8
git log -1 --format="%H%n%s" 25370ff
rtk git diff da6efbf 25370ff -- services/api/embroidery_api/svg_fit.py services/api/embroidery_api/app.py services/api/embroidery_api/runner.py apps/web/src/api/HttpApiClient.ts
git archive --format=zip --output=tests/engine/.tmp/review-25370ff/source.zip 25370ff9057a826996946035f3a1d60003c35d62
Expand-Archive tests/engine/.tmp/review-25370ff/source.zip tests/engine/.tmp/review-25370ff/source -Force
```

Python empaquetado 3.12, -B, PYTHONDONTWRITEBYTECODE=1; PYTHONPATH con services/api/.deps y workers/embroidery/.deps de motor:

```powershell
& $reviewPython -B tests/engine/.tmp/review-25370ff/variant_api_repro.py
& $reviewPython -B tests/engine/.tmp/review-25370ff/serve_audit.py
# cwd copia aislada source/apps/web, dependencias copiadas localmente
npm.cmd run build
npm.cmd test
# cwd tests/engine/.tmp/review-25370ff
node source/tests/e2e/node_modules/playwright/cli.js test -c audit.playwright.config.ts
```

Scripts y configs están conservados en esta carpeta; reconstruir el snapshot y copiarlos junto al directorio source para repetir. API en 127.0.0.1:8387, Vite en localhost:5287; ambos de auditoría y detenidos al cerrar. No se leyó configuración privada de producción.

## Metodología

Evidencia versionada en ronda B: este README, JSON de resultados y logs de texto. PNG, JEF, ZIP/trazas, SVG de entrada y scripts de auditoría quedan como artefactos locales excluidos por .gitignore; los enlaces a esos archivos sirven en el workspace de David, no en una copia nueva del repositorio. Las auditorías anteriores 014e368, c49573d y da6efbf también permanecen locales. Los hashes y medidas quedan conservados en los JSON versionados.

Skills audit/code-review y playwright-expert; L1 requisitos explícitos, informe V1 y mensajes de coordinación; L2/RAG no utilizado; L4 diff, lectura focal, pruebas HTTP/CLI/build/Chrome. Revisor independiente ejecutó tres JEF, inmutabilidad y rechazos; principal build/web/Chrome y consolidación. Archivos escaneados: los 10 del delta mediante diff/lecturas, más helpers de pruebas y config de runtime.

Límites: no calibración física ni IA real; los 403/404 del caso web fueron sintéticos y están rotulados. Los resultados conservan needs_review. Este GO cierra el delta especificado y no declara ready_for_sewout ni corrección general de cualquier SVG posible.

## Entrega

Hito / tarea: Orden 1; GO para 29f73a8 + 25370ff.

Versión de contratos utilizada: v0.1 del snapshot 25370ff, sin cambios de esquema en el delta.

Archivos y rama: evidencia local en codex/motor; ramas de Claude y main intactas por Codex.

Qué funciona con entradas reales: seis casos exigidos, JEF medidos y error 422 presentado en Chrome.

Qué utiliza datos simulados: SVG de prueba sintético; solo respuestas 403/404 interceptadas para verificar traducciones.

Comprobaciones ejecutadas y resultado: tabla y logs; 163 web, build y navegador aprobados.

Limitaciones o bloqueos: sin bloqueantes dentro del alcance; no aprobación física ni digital.

Cambios que necesitás de la otra IA: ninguno por V1; se continúa con el helper de límites/EXIF y luego la integración temporal.

## Referencias

- [Resultados API/JEF y origen](variant-api.json) · [Repro](variant_api_repro.py) · [Rechazos](rejection-fixtures.json)
- [Resultado Chrome](browser-detail.json) · [Build](build-web.log) · [Pruebas web](web-tests.log)
