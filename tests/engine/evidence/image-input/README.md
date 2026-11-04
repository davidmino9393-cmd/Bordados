# Entrada orientada: medición y ampliación a 20 MP

Propósito: justificar el límite con E1 real antes de cambiarlo. Fecha: 2026-11-03.

Contenido: [Medición](#medición), [Decisión](#decisión), [Pruebas](#pruebas), [Repro](#repro), [Referencias](#referencias).

## Medición

Proceso hijo Python 3.12.14 / Pillow 12.3.0, E1 real, dos PNG de 4000×5000. Solo para medir se permitió 20 MP en memoria; no se redujeron píxeles durante vectorize. Bytes limitados a 10 MiB y guarda geométrica 500.000 intactos.

| Entrada | Bytes PNG | Tiempo E1 | Pico working set | Pico commit | Resultado |
|---|---:|---:|---:|---:|---|
| Sintética, 3 colores y hueco | 96.079 | 35,8355 s | 999.141.376 B | 995.065.856 B | Vectorización correcta |
| Referencia ampliada, contain | 3.813.610 | 36,5612 s | 980.721.664 B | 975.429.632 B | GEOMETRY_INVALID / boundary_edge_limit 500000 |

RAM física total 25.073.807.360 B; inicialmente libre ~3,98 GB. Los dos primeros preflights no ejecutaron E1 por la guarda relativa inicial del 20% libre. Después se usó Windows Job Object con límite duro de commit 1,5 GiB aplicado antes de reanudar cada hijo y reserva de 1,5 GiB libre, muestreada cada 50 ms. Mínimo libre observado ~2748,59 MiB; sin aborto de memoria/timeout (600 s). Los preflights se conservaron.

El fallo de la referencia es de complejidad, no memoria. No se afirma que esa imagen ampliada produzca un documento ni un JEF.

## Decisión

Tras ver ambas mediciones David respondió explícitamente: **«Subir a 20 MP conservando la guarda geométrica»**. Se aplica MAX_INPUT_PIXELS=20_000_000, importado por segmentation. MAX_INPUT_BYTES sigue 10 MiB: un PNG de 20 MP puede superar bytes y será rechazado. Sin downscale, cambio de densidad ni relajación de la guarda geométrica.

## Pruebas

- 20 MP exactos (PNG real 4000×5000): aceptado.
- 20.000.001 píxeles (PNG genuino de un bit, ancho 20.000.001): INPUT_TOO_LARGE/pixel_limit **antes de load**.
- 16 pruebas de entrada aprobadas; matriz de 16 orientaciones PNG/JPEG y 6 EXIF corruptos actualizada, SHA original conservado.
- Motor completo tras ampliación: **182 pruebas sin fallos, 4 omitidas**, 47,110 s.

La normalización API todavía requiere consumo del helper por Claude. Igualar el catálogo a 20 MP no integra automáticamente EXIF ni el ejemplo OpenAPI, que anunciaba 40 MP.

## Repro

Python empaquetado: `python -B tests/engine/evidence/image-input/benchmark_20mp.py`. Solo Windows; ejecuta hijos acotados y conserva JSON/log. Puede detenerse por reserva de RAM si el entorno cambia. Imágenes de medición quedan locales bajo tests/engine/.tmp, sin binarios en este commit.

## Referencias

- [Medición](benchmark-20mp.json) · [Log](benchmark-20mp.log) · [Motor](motor-20mp.log)
- [Matriz EXIF](matrix.json) · [Contrato del helper](../../../../workers/embroidery/vectorize/IMAGE_INPUT.md)
