# GO independiente — e426456

Propósito: revisar B2/B3 y el aviso web como delta sobre main68d7ecd. Fecha: 2026-11-03.

Contenido: [Dictamen](#dictamen), [Pruebas](#pruebas), [Comandos](#comandos), [Metodología](#metodología), [Evidencia](#evidencia), [Entrega](#entrega).

## Dictamen

**GO para `e42645661d3c51c4ce3181c289e4871319d5e0c4`** contra `68d7ecdfef23f34e5becd9e5ccb0be9de65244bf`. Ocho archivos del delta, ninguno de motor ni contratos. Sin bloqueantes confirmados. Revisado mediante git archive aislado en wt-motor; no se editaron archivos ni rama de Claude.

`services/api/embroidery_api/app.py:389–407`: lectura/ajuste dentro del build idempotente, antes de crear recursos. `app.py:482–484`: destino del SVG base es límite. `apps/web/src/features/settings/SettingsForm.tsx:98` y `copy/es.ts:164`: aviso solo para prepared_svg.

Observación menor de redacción: «el trabajo se rechaza» puede confundirse con un 422 al crear; para un SVG base demasiado grande se crea el job y falla después con DIMENSIONS_EXCEEDED. El texto no promete escalado y la conducta medida es coherente; no bloquea.

## Pruebas

| Punto requerido | Evidencia propia |
|---|---|
| 422 sigue síncrono | Sin viewBox y con width/height relativos: 422 INVALID_REQUEST, detail legible, cero job/revisión nuevos; padres procesados con Ink/Stitch real. |
| Replay | Misma clave devuelve exactamente 202/cuerpo inicial. Guards independientes: **cero lecturas del archivo original**, cero ajustes API/runner y cero recursos extra. |
| Base | SVG de 20×20 con destinos límite 40×40 o 20×20: JEF **20×19,8 mm / 402 puntadas STITCH**, bytes de entrada al worker idénticos; input_sha256=geometry_sha256=original. |
| Base fuera del límite | Destino 10×10: SVG sin cambios, **failed / DIMENSIONS_EXCEEDED**, no reducción silenciosa. |
| Cadena base→A→B | A40×40: **40×39,6 / 1388 STITCH**; B10×10 desde A: **10×10 / 135 STITCH**. Ambos reciben el asset original; guard de bytes y hashes, no inferencia por un JEF diferente. |
| Inmutabilidad | Jobs/revisiones/cada uno de los seis hashes de artefactos de base y A idénticos después de B. |
| Aviso web | **Chrome real**, API real, sin interceptores: visible al subir SVG; ausente al reemplazar por PNG. |

SHA256 de entrada al worker: original `99c8c4a1450ebc2441e28247e7b45fb64d528109fd44160608bcb90b7cfcd321`; A `64f869f27bb0b76fd42e2f3640a8dc2990b087099d3b70dddf8428feab30fce1`; B `8c552697b9ea4493046987e4402c64ab8780eaf91242359a85c3caa15008c4f9`. Los manifiestos conservan SHA original para input y ajustado para geometry.

**Motor: 164 pruebas sin fallos, 4 omitidas**, 58,422 s. **Web: 163 pruebas**, build TypeScript/Vite y **Chrome: 1 prueba**, todos aprobados. Las cuatro regresiones nuevas también se ejecutaron aisladamente: 4/4 con su worker falso declarado. Tienen asserts de bytes, códigos, cuerpos y ajustes; el repro independiente añade el guard de lectura que el test de replay suministrado no verifica por sí solo.

## Comandos

Desde `C:\dev\wt-motor`:

```powershell
git log -1 --format="%H%n%s" e426456
rtk git diff --stat 68d7ecd e426456
git archive --format=zip --output=tests/engine/.tmp/review-e426456/source.zip e42645661d3c51c4ce3181c289e4871319d5e0c4
Expand-Archive tests/engine/.tmp/review-e426456/source.zip tests/engine/.tmp/review-e426456/source -Force
```

Python empaquetado, -B, PYTHONDONTWRITEBYTECODE=1, PYTHONPATH a deps API/worker de motor:

```powershell
& $auditPython -B tests/engine/.tmp/review-e426456/audit_api.py
& $auditPython -B -m unittest discover -s tests/engine/.tmp/review-e426456/source/tests/engine -p 'test_*.py' -q
& $auditPython -B tests/engine/.tmp/review-e426456/serve_audit.py
# cwd snapshot source/apps/web
npm.cmd run build
npm.cmd test
# cwd tests/engine/.tmp/review-e426456
node source/tests/e2e/node_modules/playwright/cli.js test -c notice.config.ts
```

API local 8388 y Vite 5288. Dependencias existentes copiadas al snapshot, sin escribir en Claude. API de auditoría detenida con backend.stop; Vite y Chrome cerrados por Playwright.

## Metodología

Skills audit/code-review y playwright-expert. L1: requisitos, delta y cuatro regresiones; L2/RAG no usado; L4: Git/lectura focal, HTTP/InkStitch/pyembroidery, build y Chrome. Un revisor independiente verificó API; principal consolidó suites y web. Leídos los ocho archivos del delta, helpers/API/runner/modelos asociados y scripts de repro.

No se afirma prueba física ni calibración. Medidas API independientes provienen de Ink/Stitch real; las cuatro pruebas suministradas usan worker falso rotulado. El aviso de navegador no requiere generar un job y no se presenta como otro sewout ni exportación.

## Evidencia

Versionados: README, JSON y logs de texto. PNG/ZIP/JEF/trazas, SVG y scripts de auditoría quedan locales bajo .tmp/review-e426456; no se agregan binarios. Los JSON conservan hashes, medidas, conteos, guards y rutas de runtime. Auditorías anteriores 014e368/c49573d/da6efbf permanecen locales.

- [API/JEF/replay/cadena](audit-api.json) · [Chrome](browser-notice.json) · [Resultado navegador](browser-results.json)
- [Motor](engine-tests.log) · [Web](web-tests.log) · [Build](build-web.log) · [Chrome log](browser-run.log)

## Entrega

Hito / tarea: ronda B Orden1, GO e426456. Versión de contratos utilizada: v0.1, sin cambios de esquema. Archivos y rama: evidencia en codex/motor; candidato intacto. Qué funciona con entradas reales: 422, replay, base, cadena, inmutabilidad y aviso Chrome. Qué utiliza datos simulados: SVG/PNG sintéticos y worker falso en regresiones suministradas. Comprobaciones ejecutadas y resultado: tablas y logs. Limitaciones o bloqueos: ninguno en el delta; no aprobación física/digital. Cambios que necesitás de la otra IA: comunicar hash nuevo de main tras integración autorizada para la preparación final.
