# Unidades y evidencia v0.1

Propósito: convenciones explícitas para intercambiar imagen, geometría y medidas sin confundirlas.

Contenido: [Convenciones](#convenciones), [evidencia](#evidencia), [relacionados](#relacionados).

## Convenciones

| Dato | Unidad / marco |
|---|---|
| Imagen y región estimada | px; origen superior izquierdo, x derecha, y abajo |
| Geometría editable y raíles | mm; design_top_left, x derecha, y abajo |
| Transformación imagen→documento | `[a,b,c,d,e,f]`: x_mm=a*x_px+c*y_px+e; y_mm=b*x_px+d*y_px+f |
| Transformación motor→documento | Misma convención afín, entrada/salida mm; incluye inversión de eje y traslación si corresponde |
| Espaciado, underlay, compensación, longitud | mm; dirección en grados `[0,360)` |
| Duración de proceso | ms medidos; null si no disponible |
| Bounds | min/max x/y explícitos; ancho=max_x-min_x, alto=max_y-min_y |

`page_bounds_mm`, `object_bounds_mm` y `stitch_bounds_mm` son campos distintos. Un SVG preparado puede no tener marco de píxeles: su transformación desde píxeles queda null. El adaptador debe registrar cómo convierte unidades SVG a mm antes de producir el documento.

## Evidencia

- AnalysisRegion es estimated_bbox; su texto observado no sustituye automáticamente letras por tipografía.
- EmbroideryObject conserva tipo de geometría, técnica propuesta/efectiva, parámetros, región de origen y decisiones. Satin exige datos de raíles y correspondencia; el contrato no demuestra topología válida.
- Medidas JEF: comandos normalizados en mm, contador de aguja, JUMP crudo y tras interpretación, cortes y método de conteo. La codificación de cortes no prueba ejecución en máquina.
- Colores de trabajo y aproximaciones del catálogo JEF permanecen separados por bloque.
- Hash de bytes preserva integridad. Regresión normalizada de órdenes/coordenadas, tolerancias y exclusión de fecha JEF se implementarán en H0-06.
- `provenance.simulated=true` identifica ejemplos. Incluso `false` es una declaración del emisor; el worker debe respaldarla con archivos/versiones/logs y relectura real.

## Relacionados

[Modelos](README.md), [estados](states.md), inventario.
