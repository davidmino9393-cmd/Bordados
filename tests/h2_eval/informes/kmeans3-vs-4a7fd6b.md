# Cuantización: MEDIANCUT actual (`4a7fd6b`) frente a MEDIANCUT con `kmeans=3`

Medido con `tests/h2_eval` sobre las 14 imágenes PNG/JPEG del conjunto, a resolución original (no miniaturas), con la misma máscara y el mismo límite de colores. La variante es una **copia temporal** de `4a7fd6b` con `kmeans=3` en la llamada a `quantize`; no es un cambio de producción. La métrica de color mide la fracción de píxeles del primer plano cuyo color dibujado difiere ≥ 64 niveles de canal del original. No mide legibilidad ni valida la suposición de fondo.

Reproducir: extraer cada variante con `git archive` y correr `run_eval.py --worker-path` sobre cada una; luego `compare_reports.py`.

| Imagen | Píxeles con error ≥ 64 (4a7fd6b) | (kmeans=3) | p95 (4a7fd6b) | p95 (kmeans=3) | Error medio (4a7fd6b) | (kmeans=3) | Objetos | Resultado |
|---|---:|---:|---:|---:|---:|---:|---|---|
| logo-sol-01 | 0.0273 | 0.0273 | 6 | 6 | 5.18 | 5.27 | 2 / 2 | mejora |
| logo-hoja-01 | 0.0000 | 0.0000 | 1 | 0 | 0.25 | 0.12 | 2 / 2 | empata |
| logo-escudo-01 | 0.0566 | 0.0023 | 165 | 4 | 10.71 | 0.27 | 3 / 3 | mejora |
| logo-ola-01 | 0.0077 | 0.0078 | 3 | 3 | 1.44 | 1.12 | 3 / 3 | empeora |
| linea-casa-01 | 0.0310 | 0.0310 | 5 | 5 | 9.47 | 9.47 | 1 / 1 | empata |
| letras-nova-01 | 0.0197 | 0.0194 | 29 | 21 | 4.40 | 4.53 | 2 / 2 | mejora |
| monograma-mk-01 | 0.0210 | 0.0210 | 5 | 5 | 4.25 | 4.25 | 2 / 2 | empata |
| anillo-doble-01 | 0.0126 | 0.0127 | 13 | 9 | 2.61 | 2.63 | 2 / 2 | empeora |
| dificil-lineas-finas-01 | 0.6348 | 0.6348 | 136 | 136 | 65.91 | 65.91 | 1 / 1 | empata |
| dificil-texto-chico-01 | 0.0518 | 0.0518 | 77 | 77 | 14.15 | 14.15 | 1 / 1 | empata |
| dificil-degradado-01 | 0.0938 | 0.0301 | 67 | 57 | 10.54 | 6.68 | 3 / 3 | mejora |
| jpeg-simple-01 | 0.1462 | 0.0294 | 199 | 48 | 21.51 | 5.63 | 2 / 2 | mejora |
| anime-socks-150 | 0.0635 | 0.0004 | 69 | 21 | 7.67 | 3.98 | 3 / 3 | mejora |
| anime-socks-126 | 0.0635 | 0.0004 | 69 | 21 | 7.67 | 3.98 | 3 / 3 | mejora |

Mejora 7, empata 5, empeora 2. 4a7fd6b: mediana 620.5 ms, máximo 4504 ms; kmeans=3: mediana 758.0 ms, máximo 3093 ms
