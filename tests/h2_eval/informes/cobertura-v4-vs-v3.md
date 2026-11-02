# Máscara por cobertura (método `e1-pixel-mask-v4`) frente a «todo lo que no es blanco» (`v3`)

Medido con `tests/h2_eval` sobre las 14 imágenes PNG/JPEG, a resolución original. Antes, todo píxel que no fuera casi blanco (≥ 250) entraba al primer plano, así que cada borde suavizado agregaba 1–2 píxeles de grosor a las líneas. Ahora un píxel de borde solo se queda si tiene al menos la mitad del color de su grupo (cobertura ≥ 0,5, como un trazador a 50 %); los colores del grupo se recalculan con los píxeles que quedan. Solo con fondo blanco quitado: con transparencia manda el alfa. Una regla global.

La columna «Error borroso» compara original y redibujado tras un desenfoque de 2 px sobre toda la imagen (incluido el fondo): es la medida que ve el cambio de grosor de una línea. Antes de este cambio no existía: la fracción de píxeles con error ≥ 64 y el IoU contra «todo lo que no es blanco» no distinguen una línea engrosada.

| Imagen | Píxeles con error ≥ 64 (v3) | (v4) | p95 (v3) | p95 (v4) | Error medio (v3) | (v4) | Error borroso (v3) | (v4) | Objetos | Resultado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| logo-sol-01 | 0.0278 | 0.0090 | 0 | 0 | 2.68 | 0.82 | 0.488 | 0.0973 | 2 / 2 | mejora |
| logo-hoja-01 | 0.0000 | 0.0000 | 0 | 0 | 0.12 | 0.12 | 0.0481 | 0.0481 | 2 / 2 | empata |
| logo-escudo-01 | 0.0023 | 0.0013 | 0 | 0 | 0.16 | 0.10 | 0.0433 | 0.0207 | 3 / 3 | empata |
| logo-ola-01 | 0.0081 | 0.0012 | 0 | 0 | 0.69 | 0.33 | 0.1619 | 0.0643 | 3 / 3 | mejora |
| linea-casa-01 | 0.0313 | 0.0104 | 0 | 0 | 4.93 | 1.43 | 0.2858 | 0.0647 | 1 / 1 | mejora |
| letras-nova-01 | 0.0198 | 0.0039 | 0 | 0 | 2.34 | 0.65 | 0.4578 | 0.0992 | 2 / 2 | mejora |
| monograma-mk-01 | 0.0214 | 0.0076 | 0 | 0 | 2.11 | 0.69 | 0.4753 | 0.0948 | 2 / 2 | mejora |
| anillo-doble-01 | 0.0128 | 0.0042 | 0 | 0 | 1.31 | 0.43 | 0.3567 | 0.0717 | 2 / 2 | mejora |
| dificil-lineas-finas-01 | 0.3131 | 0.1759 | 159 | 97 | 63.58 | 27.21 | 1.9252 | 0.4839 | 1 / 1 | mejora |
| dificil-texto-chico-01 | 0.0545 | 0.0186 | 86 | 0 | 7.64 | 2.22 | 0.6743 | 0.1287 | 1 / 1 | mejora |
| dificil-degradado-01 | 0.0302 | 0.0302 | 57 | 57 | 6.55 | 6.55 | 6.3433 | 6.3433 | 3 / 3 | empata |
| jpeg-simple-01 | 0.0302 | 0.0025 | 8 | 4 | 3.72 | 0.54 | 0.7169 | 0.079 | 2 / 2 | mejora |
| anime-socks-150 | 0.0004 | 0.0004 | 24 | 24 | 3.38 | 3.38 | 1.6118 | 1.6118 | 3 / 3 | empata |
| anime-socks-126 | 0.0004 | 0.0004 | 24 | 24 | 3.38 | 3.38 | 1.6118 | 1.6118 | 3 / 3 | empata |

Mejora 9, empata 5, empeora 0. v3: mediana 617.0 ms, máximo 2397 ms; v4: mediana 739.0 ms, máximo 3057 ms

Lectura: nada empeora. Las 10 imágenes con bordes suavizados contra el blanco reducen el error borroso a entre la mitad (escudo) y la décima parte (JPEG): sol 0,49 → 0,10; letras 0,46 → 0,10; línea de casa 0,29 → 0,07; líneas finas 1,93 → 0,48; JPEG 0,72 → 0,08). En las líneas finas el error medio baja de 63,6 a 27,2 y la fracción de píxeles con error ≥ 64 de 31 % a 18 %. La hoja, Anime Socks y el degradado no cambian (su primer plano no depende de bordes suavizados contra el blanco). Probé también umbrales de cobertura de 0,35 y 0,65: 0,5 fue el mejor en todas las imágenes con borde suavizado. La mediana de tiempo pasa de 617 ms a 739 ms.

Con esto el IoU de F deja de ser 1: el primer plano medido por F es «todo lo que no es blanco» y E ahora descarta los bordes con menos de la mitad de cobertura; ese faltante es lo que se quería sacar.
