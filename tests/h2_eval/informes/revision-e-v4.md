# Revisión de E (`e1-pixel-mask-v4`) hecha por Claude, sin esperar a Codex

Por indicación de David se revisó sin esperar la revisión de Codex. **Esta revisión la hizo quien escribió los cambios**: sirve para encontrar fallos con sondas y pruebas, no reemplaza una mirada ajena (la IA local de solo lectura y Codex siguen siendo válidas).

## Alcance
`segmentation.py` (cuantización `kmeans=3`, color mediano, filtro de borde), `thin_features.py`, los cambios de `pipeline.py` y las pruebas asociadas.

## Hallazgo corregido: la regla de cobertura abría agujeros en diseños casi blancos con ruido
La primera versión descartaba todo píxel con cobertura < 0,5 respecto del color de su grupo, estuviera donde estuviera. En un diseño a menos de 8 niveles del blanco con ruido de JPEG, muchos píxeles interiores quedaban «con poca cobertura» y se perdían:

| Caso (disco de 120 px, color base, ruido) | Antes (global) | Ahora (solo borde) | Sin la regla |
|---|---|---|---|
| (249, 247, 246) ± 5 | 492 píxeles descartados, 528 huecos | 8–16 descartados, 219–225 huecos | 0 descartados, 227 huecos |

Ahora un píxel débil solo se descarta si **toca el fondo** (vecindad de 8, hasta 2 anillos); los de adentro se conservan. Prueba de regresión: `test_weak_pixels_inside_a_nearly_white_shape_are_kept_so_the_coverage_rule_opens_no_pinholes`. Las 14 imágenes de F no cambian (14 empates, 0 peores) porque su borde suavizado siempre toca el fondo.

## Limitación que ya existía (no la introdujo v4)
La regla de fondo blanco quita **globalmente** los píxeles con los tres canales ≥ 250. En un diseño casi blanco, los píxeles interiores que el ruido lleva a ≥ 250 salen como huecos (≈ 225 en el caso de arriba, igual con o sin cobertura). Ya figura como advertencia `GEOMETRY_REPAIR_AMBIGUOUS` («interpretación del fondo opaco»). No se cambia sin decisión de David: es una regla de producto.

## Casos sondeados sin hallazgos
Color casi blanco con ruido ±2 y ±4; diseño de 1 píxel en 8 × 8; imagen de 1 × 1 y de 2 × 2; imagen toda de diseño, sin fondo blanco; azul junto a casi blanco (2 grupos); transparencia con color casi blanco **opaco** (manda el alfa: sigue siendo diseño, sin cobertura); línea de 1 píxel casi blanca; ruido de ±6 sobre gris claro; 16 y 256 colores sobre un degradado.

## Rendimiento medido (esta máquina, un solo trabajo)
| Entrada | Tiempo de E |
|---|---|
| Logos del conjunto | mediana ≈ 1,0–1,3 s |
| Anime Socks (1122 × 1402) | ≈ 3,5–5 s |
| Anillos de 2000 × 2000 (4 Mpx, 3 colores) | 8,1 s |
| Degradado de 1000 × 1000, 16 colores | 3,7 s |
| Degradado de 1000 × 1000, 256 colores | 16,6 s |

El filtro de borde agregó ≈ 0,3 s de mediana. No hay comprobaciones de cancelación dentro de `_fringe_keep` (una pasada de unas décimas de segundo; la cancelación se atiende antes y después).

## Lo que no se revisó
Memoria máxima, concurrencia de varios trabajos a la vez en E y la calidad física del resultado cosido (H3).
