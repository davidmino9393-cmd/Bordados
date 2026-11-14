# Entrada PNG/JPEG compartida

Propósito: API y E1 decodifican los mismos píxeles orientados sin modificar la entrada original.

Contenido: [Firma](#firma), [Consumo API](#consumo-api), [Fallos](#fallos), [Referencias](#referencias).

## Firma

`from vectorize.image_input import MAX_INPUT_BYTES, MAX_INPUT_PIXELS, decode_raster`

`decode_raster(data: bytes, media_type: str, cancel=None) -> DecodedRaster`

| Campo / método | Valor |
|---|---|
| `rgba` | imagen Pillow RGBA independiente; EXIF aplicado; metadatos retirados |
| `size` | `(width_px, height_px)` visual, después de orientar |
| `raw_size` | tamaño codificado antes de orientar |
| `orientation` | entero EXIF 1–8; 1 si falta |
| `sha256` | SHA256 de los bytes originales |
| `analysis_png(cancel=None)` | PNG sin pérdida ni EXIF; mismos píxeles RGBA; salida determinista |

Límites únicos: **10485760 bytes**, **20000000 píxeles**, ambos inclusivos. Bytes antes de abrir; píxeles de la cabecera antes de cargar. Un PNG de 20 Mpx puede superar 10 MiB: se rechaza por bytes aunque cumpla el límite de píxeles. Se mantienen las guardas de bombas de Pillow. `cancel`: Event, predicado sin argumentos o None; lanza `JOB_CANCELLED`.

## Consumo API

1. Limitar la lectura de subida con `MAX_INPUT_BYTES`; llamar a `decode_raster(original_bytes, original_media_type)` y traducir sus fallos al error HTTP correspondiente.
2. Guardar **bytes y SHA originales**, sin reescribirlos. Publicar `size` como dimensiones de SourceAsset; `crop_px`, cajas de análisis y coordenadas de fuente se refieren al marco visual orientado, arriba-izquierda/y hacia abajo.
3. Proveedor: enviar `analysis_png()` con MIME `image/png` y dimensiones `size`. Ese PNG derivado no sustituye al original ni su SHA. Puede ocupar más bytes que el JPEG subido; es una representación interna, no otra subida.
4. E1: enviar bytes/MIME originales y el asset con dimensiones visuales. E1 valida identidad, orienta con el mismo helper y recorta después. Nunca volver a aplicar EXIF al PNG de análisis.
5. Publicar estos límites en `/profiles`; un despliegue puede imponer límites menores. **La API todavía tiene que consumir el helper**: compartir el mismo tope de 20 Mpx no integra por sí solo límites ni EXIF.

## Fallos

`VectorizeFailure.issue` conserva catálogo/severidad. PNG/JPEG son los únicos MIME admitidos; WebP/SVG/otros → `INPUT_UNSUPPORTED_FORMAT`, reason `unsupported_media_type`. Bytes/píxeles/bombas → `INPUT_TOO_LARGE`. EXIF corrupto u orientación inválida → `INPUT_UNREADABLE`, reason `invalid_exif`; formato declarado distinto, animación y decodificación también fallan de forma controlada. No se adivina una orientación corrupta.

## Referencias

- [Helper](image_input.py) · [E1](segmentation.py)
- [Pruebas](../../../tests/engine/test_vectorize_input.py) · Matriz
