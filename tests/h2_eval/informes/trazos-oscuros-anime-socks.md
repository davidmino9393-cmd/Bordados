# Trazos oscuros de Anime Socks tras `kmeans=3`: qué se pierde y por qué

Pedido: resolver los «5 componentes y 6 huecos grandes de trazos oscuros» que el candidato no conservaba (luminancia < 192).

## Qué es lo que se pierde
Los píxeles del original con luminancia < 192 que el redibujado deja claros son **9.639 px, todos con luminancia entre 171 y 191** (media 183) y todos reemplazados por el rosa intermedio `#e7c6c6` (luminancia 203). Ningún píxel con luminancia < 171 se pierde: **todos los trazos realmente oscuros se conservan**. Lo «perdido» son contornos de pétalos, filamentos de estambres y el cuerpo claro de las hojas: tonos intermedios que quedan más cerca del rosa que del malva `#9f8288` (p. ej. un píxel (190, 170, 172) está a ≈ 50 del rosa y a ≈ 70 del malva). El 83 % de esos píxeles pertenece a líneas de 2 px o menos (0,27 mm a 150 mm de ancho), por debajo de lo que una máquina puede bordar. El corte en 192 cae justo en el borde entre dos grupos del límite de 3 colores.

## Alternativas probadas (todas globales, sin ajustes por logo)
Paleta de 3 colores, medidas en la misma máscara (`error ≥ 64` = fracción de píxeles; estructura = componentes ≥ 16 px / huecos ≥ 16 px / huecos ≥ 64 px en luminancia < 192; el original tiene 34 / 22 / 21):

| Método | error ≥ 64 | error medio | estructura < 192 |
|---|---:|---:|---|
| MEDIANCUT sin refinar (`4a7fd6b`) | 6,35 % | 7,67 | 0 / 0 / 0 |
| `kmeans=3` / 10 / 30 (iguales, converge) | 0,04 % | 3,98 | 29 / 17 / 15 |
| pesos por raíz del conteo | 0,02 % | 11,26 | 31 / 15 / 10 |
| conteo acotado a 20 | 0,03 % | 14,17 | 30 / 16 / 13 |
| conteo acotado a 2 | 0,02 % | 20,78 | 24 / 25 / 12 |
| colores únicos | 0,01 % | 23,24 | 29 / 37 / 18 |

Los métodos con pesos no recuperan la estructura (los huecos grandes empeoran o se inventan) y desplazan todo el disco claro hacia el rosa (error medio de 11 a 23). En los logos planos son desastrosos: `logo-sol-01` pasa de 2,7 % a 98 % de píxeles con error ≥ 64, `linea-casa-01` y `dificil-texto-chico-01` a 97 % y 96 %. Con 3 colores no hay una forma global de repartirlos que conserve a la vez el disco, los pétalos y los contornos de tono intermedio.

## Qué se resolvió en cambio
El color de cada grupo pasa de promedio a miembro mediano (ver `mediana-vs-promedio.md`): el error medio baja a la mitad en los logos planos y Anime Socks pasa de 3,98 a 3,38.

## Qué queda
- Los contornos de tono intermedio (171–191) seguirán en el rosa mientras el límite sea de 3 colores. Forzarlos al malva engrosaría líneas de menos de 0,3 mm y sin calibración física (H3) no hay criterio para elegirlo.
- Una política de tamaño mínimo bordable (qué hacer con líneas de 2 px o menos) corresponde a H3.
