# H2 — imagen → geometría: plan, material preparado y pedidos

Estado: **autorizado (parche y backend en `claude/web`, sin merge a `main`)**. Hechos: paquete A (contrato) y paquete D (pipeline de imagen) con proveedores falsos en las pruebas y el adaptador de OpenAI sin probar contra la red. Faltan los insumos #3, #4 y #5 para B real, C, E y F.

| Paquete | Estado |
|---|---|
| A. Contrato | **Hecho** (commit `00e6fd2`), 37 pruebas del motor |
| B. Adaptador OpenAI | **Código y pruebas con transporte falso** (9). Sin clave ni modelo no se probó con OpenAI real |
| C. Adaptador Ollama | Pendiente; figura «no disponible» en el catálogo |
| D. Pipeline de imagen | **Hecho**: `analyzing`, `analysis`, `analysis-decision`, `analysis_retry`, continuación (14 pruebas HTTP). La continuación ejecuta E1 y termina en `needs_review` (`DENSITY_REVIEW_REQUIRED`), sin JEF |
| E. Vector y geometría | **E1 hecho por Codex** (planas, huecos; PNG/JPEG) y conectado en `runner.py`. Pendiente: Anime Socks excede el límite de complejidad, SVG, ejes centrales, satén |
| F. Evaluación | **Arnés listo** (`tests/h2_eval/`, 6 pruebas); espera `vectorize()` de Codex. IoU, huecos y texto aún sin medir |
| G. Web | Pendiente del backend real con una clave |


## Contenido
- [Qué está listo](#qué-está-listo) · [Pedidos](#pedidos-de-autorización-y-de-insumos) · [Paquetes de trabajo](#paquetes-de-trabajo-de-h2) · [Riesgos](#riesgos-y-límites) · [Orden](#orden-propuesto)

## Qué está listo

| Material | Dónde | Verificación |
|---|---|---|
| UI de análisis visual con mocks (carga, `AnalysisReview`, regenerar con otro proveedor) | `apps/web`, `tests/e2e` | 145 Vitest, 40 e2e, axe |
| Cambio de contrato H2 como parche | `h2/contrato-h2.patch` | Aplicado en una copia de `main`: **37 de 37** pruebas del motor; `git apply --check` OK sobre `claude/web` |
| Esquema, ejemplo y validador del manifiesto de las 18 imágenes | `h2/manifest.schema.json`, `h2/manifest.example.json`, `h2/validate_manifest.py` | Probado con un conjunto sintético válido y 8 casos que deben fallar |

### El parche de contrato (8 archivos, no aplicado)
Cambio **aditivo** sobre `contratos-v0.1`, con las decisiones que confirmó OpenCode:
- `GET /api/v1/jobs/{id}/analysis` → `AnalysisSpec` y `POST /api/v1/jobs/{id}/analysis-decision` (aprobar con regiones marcadas, o cambiar de proveedor).
- `RevisionResponse.kind` admite `analysis_retry` (solo en respuestas).
- `packages/contracts/embroidery_contracts/analysis_decision.py` (modelos nuevos) y su exportación.
- **Hallazgo nuevo, no estaba en la confirmación de OpenCode:** la máquina de estados no permitía que un job de continuación arranque en `vectorizing` con `analyzing` omitido. El parche agrega `queued → vectorizing`, permitido solo si el job es de imagen, tiene `parent_job_id` y `analyzing` figura `skipped` con motivo. Un job común sigue sin poder saltar el análisis.
- `services/api/build_openapi.py`, `packages/contracts/openapi.json` (regenerado) y pruebas en `tests/engine`.

Aplicarlo (con tu autorización):
```bash
git apply --ignore-whitespace -p1 apps/web/docs/h2/contrato-h2.patch
python services/api/build_openapi.py
python -m unittest discover -s tests/engine -p "test_*.py"
```

## Pedidos de autorización y de insumos

| # | Pedido | Quién decide | Para qué |
|---|---|---|---|
| 1 | Aplicar el parche de contrato en `claude/web` | Vos | Desbloquea backend y cliente real de H2 |
| 2 | Permiso para modificar `services/api`, `workers/embroidery` y `packages/contracts` en `claude/web` (sin merge a `main`) | Vos | Hoy solo escribo en `apps/web` y `tests/e2e` |
| 3 | Las 15–20 imágenes con permiso de uso y su `manifest.json` (validar con `validate_manifest.py`) | Vos | Conjunto de evaluación de H2; incluye las dos escalas de Anime Socks y ≥ 5 diseños nuevos |
| 4 | OpenAI: clave en la configuración **privada del backend**, modelo elegido y tope de costo por trabajo | Vos | Adaptador de nube. Las imágenes se envían a un tercero: confirmá que aceptás ese envío |
| 5 | Ollama: modelo de visión y hardware disponible (¿GPU?) | Vos | Adaptador local; sin esto no se puede verificar |
| 6 | Política de pausa: por defecto un análisis sin dudas **no** pausa (decisión de OpenCode). ¿Querés aprobación siempre? | Vos | Si sí, es H2.1: ajuste `require_analysis_approval` + aviso `ANALYSIS_APPROVAL_REQUIRED` |

## Paquetes de trabajo de H2

| Paquete | Contenido | Criterio de aceptación | Depende de |
|---|---|---|---|
| A. Contrato | Parche de arriba | Pruebas del motor en verde; OpenAPI regenerado | #1 |
| B. Adaptador OpenAI (H2-01) | `analyze(imagen, ajustes) → AnalysisSpec` con Responses API y salida estructurada; clave solo en backend; caché por imagen+recorte+ajustes+proveedor/modelo+versión de prompt; guarda respuesta original y normalizada (`provider_raw_json`) | Maneja rechazo, salida incompleta, esquema incorrecto, región incoherente, límite de uso y fallo de conexión con los códigos del catálogo | A, #2, #4 |
| C. Adaptador Ollama (H4-01 adelantado) | Mismo contrato; disponibilidad real en `GET /profiles`; **nunca** cambia a la nube sin que lo pidas | Modelo con visión verificado y métricas del hardware real | A, #2, #5 |
| D. Pipeline de imagen | Valida píxeles decodificados, etapa `analyzing`, persiste el `AnalysisSpec`, rutas `analysis` y `analysis-decision`, jobs de continuación y `analysis_retry` | Una imagen llega a `needs_review` por análisis y la continuación llega a `vectorizing`; `bounds_px` dentro del original | A, B |
| E. Vector y geometría (H2-02/03) | Segmentación y contornos o ejes centrales, huecos, identidad del texto; `EmbroideryDocument` con unidades y trazabilidad | Procesa varios logos **nuevos** sin nombres, tamaños de imagen ni coordenadas especiales en el código; regiones estimadas separadas de máscaras verificadas | D, #3 |
| F. Evaluación (H2-06) | Arnés que corre el conjunto y mide fidelidad visual, geometría, costo, latencia y recursos | Informe reproducible; ningún porcentaje de éxito inventado | E, #3 |
| G. Web (mío) | Cliente real de análisis ya conectado; falta: comparación original/vector con máscaras verificadas, corrección localizada (H2-05) y pruebas contra el backend real | e2e contra backend real con una imagen | D |

## Riesgos y límites
- **Las cajas de la IA son estimaciones.** El trazado preciso sale de algoritmos de imagen o de corrección asistida, nunca de las coordenadas del modelo.
- **Un JSON válido puede ser una interpretación equivocada:** hay que validarlo contra los píxeles.
- **E es la parte de investigación**; sin el conjunto (#3) no se puede estimar ni aceptar.
- **Privacidad y costo de la nube** (#4) y **hardware local** (#5) no se pueden decidir sin vos.
- **No hay semanas ni presupuesto fijados**, como pide el plan, hasta tener un primer resultado de E.

## Orden propuesto
1. #1 y #2 → paquete A (parche) y arrancar B y D con un proveedor simulado en el backend.
2. #3 en paralelo (lo prepares vos; el validador te dice qué falta).
3. #4 → B real; #5 → C.
4. E y F con el conjunto.
5. G cuando D esté disponible.
