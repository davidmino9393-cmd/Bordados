# Color representativo del grupo: promedio frente a miembro mediano (producción `kmeans=3` → `e1-pixel-mask-v3`)

Medido con `tests/h2_eval` sobre las 14 imágenes PNG/JPEG, a resolución original. Antes, el color de cada grupo era el **promedio** de sus píxeles; el promedio mezcla el color del diseño con los píxeles suavizados del borde (mezcla con el fondo) y lo aclara. Ahora es el **miembro mediano por distancia al blanco**, determinista (se ordena por distancia y RGB). Una sola regla global, sin ajustes por logo. La asignación de píxeles a grupos no cambia, así que la topología queda igual.

El veredicto de la tabla usa primero la fracción de píxeles con error de canal ≥ 64 (diferencias menores a 0,1 punto porcentual son empate) y, si empata, el error medio.

| Imagen | Píxeles con error ≥ 64 (kmeans=3 (promedio)) | (mediana) | p95 (kmeans=3 (promedio)) | p95 (mediana) | Error medio (kmeans=3 (promedio)) | (mediana) | Objetos | Resultado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| logo-sol-01 | 0.0273 | 0.0278 | 6 | 0 | 5.27 | 2.68 | 2 / 2 | mejora |
| logo-hoja-01 | 0.0000 | 0.0000 | 0 | 0 | 0.12 | 0.12 | 2 / 2 | empata |
| logo-escudo-01 | 0.0023 | 0.0023 | 4 | 0 | 0.27 | 0.16 | 3 / 3 | mejora |
| logo-ola-01 | 0.0078 | 0.0081 | 3 | 0 | 1.12 | 0.69 | 3 / 3 | mejora |
| linea-casa-01 | 0.0310 | 0.0313 | 5 | 0 | 9.47 | 4.93 | 1 / 1 | mejora |
| letras-nova-01 | 0.0194 | 0.0198 | 21 | 0 | 4.53 | 2.34 | 2 / 2 | mejora |
| monograma-mk-01 | 0.0210 | 0.0214 | 5 | 0 | 4.25 | 2.11 | 2 / 2 | mejora |
| anillo-doble-01 | 0.0127 | 0.0128 | 9 | 0 | 2.63 | 1.31 | 2 / 2 | mejora |
| dificil-lineas-finas-01 | 0.6348 | 0.3131 | 136 | 159 | 65.91 | 63.58 | 1 / 1 | mejora |
| dificil-texto-chico-01 | 0.0518 | 0.0545 | 77 | 86 | 14.15 | 7.64 | 1 / 1 | empeora |
| dificil-degradado-01 | 0.0301 | 0.0302 | 57 | 57 | 6.68 | 6.55 | 3 / 3 | mejora |
| jpeg-simple-01 | 0.0294 | 0.0302 | 48 | 8 | 5.63 | 3.72 | 2 / 2 | mejora |
| anime-socks-150 | 0.0004 | 0.0004 | 21 | 24 | 3.98 | 3.38 | 3 / 3 | mejora |
| anime-socks-126 | 0.0004 | 0.0004 | 21 | 24 | 3.98 | 3.38 | 3 / 3 | mejora |

Mejora 12, empata 1, empeora 1. kmeans=3 (promedio): mediana 569.5 ms, máximo 2150 ms; mediana: mediana 650.5 ms, máximo 2356 ms

Lectura: en los logos planos el color pasa a ser el real del diseño (azul `#14285a` y naranja `#ff9900` en lugar de `#172a5c` y `#fe9b06`) y el error medio se reduce a la mitad. La única fila que empeora es `dificil-texto-chico-01`: el error medio baja de 14,15 a 7,64 pero la fracción de píxeles con error ≥ 64 sube de 5,18 % a 5,45 % (los bordes suavizados quedan más lejos de un azul más oscuro). En `dificil-lineas-finas-01` el color de la línea pasa de un gris (`#646464`, promedio con el blanco) a `#4d4d4d` y la fracción con error ≥ 64 baja de 63 % a 31 %; la línea sigue más gruesa que en el original porque la máscara incluye los píxeles suavizados (otro problema, de geometría).
