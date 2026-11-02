# Topología del candidato de paleta (`kmeans=3`, Codex `cf447b4`) frente a producción `4a7fd6b`

**Producción sigue en `4a7fd6b`.** Este informe solo mide; no promueve nada. El candidato es una copia temporal de `4a7fd6b` con `kmeans=3` en `quantize` (la misma variante de `tests/engine/experiments/trace_candidate.py`).

## Pregunta
Codex informó que los huecos **por color** de Anime Socks bajan de 5.839 a 337 con el candidato. ¿Se pierden detalles del diseño o se elimina ruido?

## Método (`topology_report.py`, independiente de la paleta de cada variante)
1. **Por capa:** huecos de cada capa de color (fondo 4-conexo que no toca el borde) con su área, sumados. Es la medida de Codex, recalculada en píxeles del original.
2. **Estructura frente al original:** se redibuja cada variante a resolución completa y se compara con el original la topología de «los trazos con luminancia menor a T»: componentes (8-conexos) y huecos, contando solo los de al menos 16 y 64 píxeles para no contar motas. Las tablas muestran `componentes ≥ 16 px / huecos ≥ 16 px / huecos ≥ 64 px`.

## Lectura
- **La baja de huecos por capa no es pérdida de detalle.** Con la paleta actual, Anime Socks usa tres tonos casi blancos (`#dec8c8`, `#fdf8f7`, `#fdf9f8`): cada capa se llena de fragmentos de los otros dos tonos y suma 11.370 huecos (310 de ≥ 64 px). Un hueco de una capa suele ser solo un trozo de otra capa, no un hueco visible del dibujo. En el umbral pálido (230) la estructura es la misma con ambas paletas (11 / 22 / 17 en el original, la base y 11 / 23 / 17 en el candidato).
- **Lo que decide es la estructura de los trazos oscuros (umbral 192):** el original tiene 34 componentes ≥ 16 px y 22 huecos ≥ 16 px (21 de ≥ 64 px). La base **no conserva ninguno** (0 / 0 / 0); el candidato conserva 29 / 17 / 15 (85 %, 77 % y 71 %). No es completo: se pierden 5 componentes y 6 huecos grandes.
- **Debajo de luminancia 128** el original aún tiene 26 componentes ≥ 16 px (el núcleo de los trazos más oscuros); ninguna variante los reproduce porque el tono más oscuro del candidato (`#9f8288`, luminancia ≈ 134) no llega. Es un límite de tener 3 colores, no de la topología.
- **Otros casos:** el escudo recupera su hueco (base 0, candidato 1, original 1); el JPEG pasa de 306 motas a una sola figura en el umbral 128 (original: 1); el degradado baja de 569 a 1 hueco por capa y pierde en ambas variantes el único hueco del umbral 192 (sin diferencia entre ellas); el texto chico y las letras son idénticos en las dos paletas.

## Qué no demuestra
Que el resultado sea legible o bordable. Los umbrales de luminancia son una forma de mirar la estructura, no un criterio de aceptación. Los componentes y huecos perdidos del candidato no se identificaron uno por uno. No se midió memoria.

## Tablas
### logo-escudo-01

Paletas: base #444950, #c81e28, #c9232a; candidato #14285a, #c81e28, #f9c72c.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 3 / 1 / 1; candidato 1 / 1 / 1.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| 215 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| 192 | 1 / 1 / 1 | 1 / 0 / 0 | 1 / 1 / 1 |
| 128 | 1 / 1 / 1 | 1 / 0 / 0 | 1 / 1 / 1 |

### letras-nova-01

Paletas: base #14285a, #ec991d; candidato #15295b, #f99e15.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 2 / 2 / 2; candidato 2 / 2 / 2.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 5 / 2 / 2 | 5 / 2 / 2 | 5 / 2 / 2 |
| 215 | 5 / 2 / 2 | 5 / 2 / 2 | 5 / 2 / 2 |
| 192 | 5 / 2 / 2 | 5 / 2 / 2 | 5 / 2 / 2 |
| 128 | 4 / 2 / 2 | 4 / 2 / 2 | 4 / 2 / 2 |

### dificil-texto-chico-01

Paletas: base #1d3060; candidato #1d3060.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 6 / 6 / 4; candidato 6 / 6 / 4.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 15 / 6 / 4 | 15 / 6 / 4 | 15 / 6 / 4 |
| 215 | 15 / 6 / 4 | 15 / 6 / 4 | 15 / 6 / 4 |
| 192 | 15 / 6 / 4 | 15 / 6 / 4 | 15 / 6 / 4 |
| 128 | 15 / 6 / 4 | 15 / 6 / 4 | 15 / 6 / 4 |

### dificil-degradado-01

Paletas: base #d0784c, #f2f6f5, #f5f5f5; candidato #929292, #db6f39, #f5f5f5.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 569 / 78 / 3; candidato 1 / 1 / 1.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| 215 | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| 192 | 1 / 1 / 1 | 1 / 0 / 0 | 1 / 0 / 0 |
| 128 | 1 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

### jpeg-simple-01

Paletas: base #142557, #373c54; candidato #14285a, #fbab30.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 110 / 1 / 1; candidato 88 / 0 / 0.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 2 / 0 / 0 | 3 / 0 / 0 | 3 / 0 / 0 |
| 215 | 2 / 0 / 0 | 3 / 0 / 0 | 3 / 0 / 0 |
| 192 | 2 / 0 / 0 | 3 / 0 / 0 | 3 / 0 / 0 |
| 128 | 1 / 0 / 0 | 3 / 0 / 0 | 1 / 0 / 0 |

### anime-socks-150

Paletas: base #dec8c8, #fdf8f7, #fdf9f8; candidato #9f8288, #e7c6c6, #fdf7f5.

Huecos sumando las capas (≥ 1 / ≥ 16 / ≥ 64 px): base 11370 / 1718 / 310; candidato 1771 / 71 / 31.

| Trazos con luminancia menor a | Original | base | candidato |
|---|---|---|---|
| 230 | 11 / 22 / 17 | 11 / 22 / 17 | 11 / 23 / 17 |
| 215 | 16 / 15 / 10 | 11 / 22 / 17 | 11 / 23 / 17 |
| 192 | 34 / 22 / 21 | 0 / 0 / 0 | 29 / 17 / 15 |
| 128 | 26 / 4 / 2 | 0 / 0 / 0 | 0 / 0 / 0 |

