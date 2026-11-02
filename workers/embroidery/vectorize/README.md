# E1: geometría de imágenes planas

Propósito: obtener geometría editable desde píxeles, antes de seleccionar puntadas en H3.

Contenido: [Interfaz](#interfaz), [Límites](#límites), [Integración](#integración), [Referencias](#referencias).

## Interfaz

```python
from vectorize import vectorize, VectorizeFailure

result = vectorize(
    image_bytes, media_type, asset, analysis, settings,
    job_id=job_id, revision_id=revision_id, cancel=event,
)
```

- Entrada: bytes originales PNG/JPEG; `SourceAsset`, `AnalysisSpec | None`, `JobSettings` v0.1.
- Cancelación: `threading.Event`, función sin argumentos que devuelve bool, o `None`.
- Salida: `VectorizeResult.document`, `.issues`, `.editable_svg` (bytes), `.evidence`, `.duration_ms`.
- Fallo: `VectorizeFailure.issue` conserva código, severidad y etapa del catálogo. `JOB_CANCELLED` es informativo; no convertirlo en fallo bloqueante.
- Función sin disco, red ni subprocesos. Duración medida fuera del contenido determinista; mismos bytes/modelos/identificadores y versión de Pillow producen igual documento y SVG.

## Límites

- Geometría `verified_mask`: fronteras de una máscara segmentada, no curvas suavizadas ni fidelidad semántica certificada.
- Los huecos usan `fill-rule="evenodd"`. No se eliminan detalles pequeños para obtener una exportación aceptable.
- Cajas de IA: orientación/anotación; no sustituyen contornos ni prueban máscaras. Texto observado no crea fuentes ni glifos.
- SVG de entrada usa el recorrido existente de SVG preparado; E1 lo rechaza explícitamente.
- Ejes centrales, satén, degradados y calibración física quedan pendientes. El conjunto sintético no demuestra generalización a logos reales.

## Integración

Claude conserva `services/api`, web y evaluación F. Este módulo no cambia estados del job ni contratos.

`EmbroideryObject` exige técnica efectiva y parámetros: E1 los completa con valores **provisionales**, emite `DENSITY_REVIEW_REQUIRED` localizado y deja `h3_validation_required` en evidencia. No habilitan `ready_for_sewout`.

`vectorize.inkstitch.to_inkstitch_svg(result, h3_document=...)` solo serializa rellenos de un documento suministrado explícitamente por H3, con idéntica geometría. Sin él se bloquea. El argumento expresa responsabilidad del llamador; no prueba calibración, controles digitales ni aprobación física. Las incidencias originales se conservan en metadatos. No se ejecuta el CLI ni se genera JEF en E1.

## Referencias

- [Continuar en otro chat](CONTINUAR.md)
- [Próxima tarea de paleta](PROXIMA_TAREA.md)
- [Modelos congelados](../../../packages/contracts/embroidery_contracts/design.py)
- [Fixtures de entrada](../../../tests/fixtures/h2/LEEME.txt)
- [Evidencia reproducible](../../../tests/engine/evidence/h2-e1/README.md)
- [Atributos oficiales Ink/Stitch](https://inkstitch.org/developers/inkstitch/namespace/)
