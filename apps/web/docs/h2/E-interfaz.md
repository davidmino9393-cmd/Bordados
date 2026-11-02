# Módulo E (vector y geometría): interfaz propuesta y reparto

Estado: **propuesta para cerrar entre Codex y Claude**; nada de E está implementado. Modelos usados: los congelados en `contratos-v0.1` (`AnalysisSpec`, `EmbroideryDocument`, `JobSettings`, `SourceAsset`, `Issue`). No se pide ningún cambio de contrato.

## 1. Entrada y salida exactas

Función pura en `workers/embroidery/vectorize/` (sin FastAPI, sin base de datos, sin leer configuración del servidor):

```python
def vectorize(image: bytes, media_type: str, asset: SourceAsset, analysis: AnalysisSpec,
              settings: JobSettings, *, job_id: str, revision_id: str,
              cancel: threading.Event | None = None) -> VectorizeResult

@dataclass(frozen=True)
class VectorizeResult:
    document: EmbroideryDocument      # contrato congelado
    issues: tuple[Issue, ...]         # solo códigos del catálogo; avisos localizados por object_ids/region_ids
    editable_svg: str                 # el mismo documento dibujado en mm, para el artefacto editable_svg
    evidence: dict                    # método, versiones, parámetros y duraciones (JSON), para la procedencia
    duration_ms: int

class VectorizeError(Exception):      # fallo bloqueante controlado
    code: IssueCode                   # INPUT_UNREADABLE, GEOMETRY_INVALID, ...
    reason: str
```

Reglas de la salida:
- **Unidades:** mm, origen arriba a la izquierda, x a la derecha, y hacia abajo. `CoordinateFrame.source_px_to_mm` lleva la transformación afín explícita desde píxeles del original (sumando `crop_px` si lo hubo) con ajuste `contain` al tamaño objetivo. `page_bounds_mm` y `object_bounds_mm` son campos distintos; los límites de puntadas los mide después la relectura del JEF.
- **Las regiones de la IA son pistas, no geometría.** Las cajas `estimated_bbox` pueden orientar, pero cada objeto sale de los píxeles. `geometry_kind` solo puede ser `verified_curve` o `verified_mask`; nunca `estimated_*`. `source_region_id` enlaza con `region_id` cuando corresponde.
- **Huecos y texto:** los huecos se conservan; el texto detectado es una anotación, jamás se sustituye por una fuente.
- **Colores:** como máximo `settings.color_limit`, en `work_color` (`#RRGGBB`).
- **Técnicas:** E solo propone (`proposed_technique`; `effective_technique` igual, provisoria); la decisión por ancho físico es H3.
- **Determinista y sin constantes por logo:** misma entrada, mismo documento; sin nombres de archivo, tamaños de imagen ni coordenadas especiales en el código.
- **Avisos:** `GEOMETRY_INVALID`, `GEOMETRY_REPAIR_AMBIGUOUS`, `GEOMETRY_HOLES_CHANGED` u otro del catálogo. Si hace falta un código nuevo, se propone como cambio de contrato.
- **Cancelación:** revisa `cancel` entre etapas y termina limpio.

### Acuerdos de las dos precisiones de Codex
- **Valores provisionales (`effective_technique` y `parameters` son obligatorios en `EmbroideryObject`).** Sin cambiar el contrato: (a) E toma `effective_technique = proposed_technique` y `parameters` de **una sola tabla con nombre** (`PROVISIONAL_PARAMETERS`, por técnica; no por logo), con un comentario que diga «sin calibrar, hasta H3»; (b) por cada objeto, E agrega al documento un `DesignDecision` con `origin: "rule"`, `field: "effective_technique"` / `"parameters"`, `previous_value: null`, `new_value` el valor asignado y `reason` que empiece con `provisional_until_h3: sin calibración física`; (c) `evidence["parameters_status"] = "provisional_uncalibrated"`. Así la web y la evaluación pueden mostrar «parámetros provisionales» sin presentarlos como calibrados. Si H3 prefiere un campo explícito, se propone como cambio de contrato aparte; no se hace en E.
- **Determinismo.** Con las mismas entradas, `document` y `editable_svg` son idénticos byte a byte. `duration_ms` y los tiempos quedan fuera de la comparación: `evidence` separa `timings` (no determinista) del resto (determinista).

Adaptador aparte (mismo dueño): `document_to_inkstitch_svg(document) -> str` en `workers/embroidery/`, para que el worker actual lo consuma como SVG preparado y produzca el JEF sin cambios.

## 2. Reparto de archivos

| Dueño | Archivos |
|---|---|
| **Codex** | `workers/embroidery/vectorize/**`, `workers/embroidery/inkstitch_adapter.py` (o similar), `tests/engine/test_vectorize*.py`, `tests/engine/test_document_to_svg.py`, sección de E en `workers/embroidery/README.md` |
| **Claude** | `services/api/**` (conexión de E al pipeline), `packages/contracts/**` (solo con propuesta acordada), `tests/engine/test_api_analysis.py`, `apps/web/**`, `tests/e2e/**`, `tests/h2_eval/**` (evaluación F), `tests/fixtures/h2/manifest.json` |
| **Solo lectura para ambos** | `tests/fixtures/h2/nuevos/**` (imágenes), el worker existente (`worker.py`, `verify_commands.py`), `tests/engine/test_regressions.py` |

**Quién conecta E con la API:** Claude, en `services/api/embroidery_api/runner.py`: la continuación tras aprobar el análisis llama a `vectorize()`, escribe el SVG con el adaptador y ejecuta el worker existente. Codex entrega la función y el adaptador con pruebas propias; no toca la API.

## 3. Commits que necesita `codex/motor`

E usa solo modelos ya presentes en `af21ed3`. **No necesita** el contrato H2 (`00e6fd2`) ni el pipeline de la API (`87459d7`).

| Commit | Contenido | Para qué |
|---|---|---|
| `da5e1a1` | solo `tests/fixtures/h2/**` (14 imágenes sintéticas, `Anime_Socks.png`, manifiesto, generador) | Imágenes de prueba con ruta estable |
| `4018d97` | solo `tests/fixtures/h2/**`: dos entradas de Anime Socks (150×142,8 y 126,2×120 mm); 16 entradas | Completar el conjunto; el validador pasa con `--check-files` |

Traslado: `git cherry-pick` de esos commits sobre `codex/motor`, con autorización de David y sin tocar `main`. La integración posterior va en sentido contrario: Claude mergea `codex/motor` en `claude/web` (no en `main`) para conectar E; David decide el paso final a `main`.

## 4. Evaluación F (Claude, `tests/h2_eval/`)
Corre `vectorize()` sobre el manifiesto y mide: IoU entre el documento redibujado y la máscara de la imagen; huecos conservados; límites dentro del tamaño objetivo (`contain`); colores ≤ límite; texto presente como anotación; determinismo (dos corridas, mismo resultado); duración; y una revisión estática que impida nombres de archivo, tamaños o coordenadas de las imágenes en el código de E. Sin porcentajes inventados: se informa lo medido.

## 5. Para cerrar
1. ~~David confirma la referencia de Anime Socks~~ **Hecho**: `Anime_Socks.png` = `trabajo/Referencia.png`.
2. ~~David autoriza el cherry-pick~~ **Hecho** (sin merges ni push); lo ejecuta Codex en su propio worktree.
3. Codex confirma o corrige la firma de `vectorize()` y los campos de `VectorizeResult`.
4. Primer entregable de Codex: `vectorize()` sobre las imágenes planas (logos y formas con huecos) con sus pruebas, antes de line art y casos difíciles.
