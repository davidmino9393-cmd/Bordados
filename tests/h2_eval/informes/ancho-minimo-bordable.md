# Política de ancho mínimo bordable (`e1-pixel-mask-v4`, `thin_features.py`)

**Política: medir y avisar; E nunca borra ni engrosa nada** (regla del proyecto: no eliminar detalles para obtener una exportación aceptable). El ancho mínimo es un **supuesto sin calibrar**: 0,4 mm, hasta que H3 lo fije con muestras cosidas reales.

## Cómo se mide
Para cada color se hace una apertura morfológica (erosión y dilatación) con un elemento cuadrado del menor tamaño impar, en píxeles, que cubre el ancho mínimo (0,4 mm dividido por los mm por píxel de la transformación). Lo que la apertura quita pertenece a trazos más angostos que el elemento. En diagonal el ancho real es hasta 1,41 veces mayor, así que la medición es prudente y puede subestimar lo fino de una línea oblicua. Si 0,4 mm es de un píxel o menos, la resolución es demasiado gruesa para medir y la evidencia dice `measurable: false` en lugar de adivinar.

La evidencia queda en `evidence["minimum_feature"]` (por objeto: píxeles, píxeles finos y fracción) y la incidencia de revisión `DENSITY_REVIEW_REQUIRED` suma `thin_feature_fraction_by_object` y `minimum_feature_mm`. No hace falta ningún código nuevo del catálogo. Qué hacer con lo fino (engrosar, pasar a puntada simple o excluir) lo decide H3.

## Fracción de cada color más fina que 0,4 mm (una por color, de mayor a menor)

| Imagen | Fracción fina por color |
|---|---|
| logo-sol-01 | 0,00 %, 0,00 % |
| logo-hoja-01 | 0,02 %, 0,00 % |
| logo-escudo-01 | 1,30 %, 0,01 %, 0,00 % |
| logo-ola-01 | 1,72 %, 0,52 %, 0,00 % |
| linea-casa-01 | 0,00 % |
| letras-nova-01 | 0,00 %, 0,00 % |
| monograma-mk-01 | 0,00 %, 0,00 % |
| anillo-doble-01 | 0,00 %, 0,00 % |
| dificil-lineas-finas-01 | 100,00 % |
| dificil-texto-chico-01 | 1,86 % |
| dificil-degradado-01 | 0,70 %, 0,01 %, 0,00 % |
| jpeg-simple-01 | 0,02 %, 0,00 % |
| anime-socks-150 | 32,89 % (`#f0c2c3`), 17,08 % (`#9b8287`), 1,77 % (`#fdf9f7`) |
| anime-socks-126 | 32,89 %, 17,08 %, 1,77 % |

## Lectura
- Las líneas finas del conjunto (la trampa de 0,13 mm) salen 100 % finas: es lo esperado y queda a la vista.
- Los logos planos (sol, escudo, ola, anillos, letras, monograma) tienen casi 0 %: no hay nada que advertir.
- En Anime Socks, el 33 % del rosa (contornos de pétalos y estambres) y el 17 % del malva (el trazo de la letra manuscrita) quedan por debajo de 0,4 mm a 150 mm de ancho. Es el mismo en las dos escalas porque el elemento se redondea a 5 píxeles en ambas.
- Costo: la mediana de tiempo de E pasa de 739 ms a 972 ms (máximo 3,6 s).
