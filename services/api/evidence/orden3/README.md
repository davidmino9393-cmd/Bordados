# Orden 3: paleta honesta, aviso de legibilidad y gate visible

Medido el 2026-11-08 sobre el logo real del job `job_c934f8b296d64d59b4547806295c6a26` (PNG 1254 x 1254, SHA256
`3ba1cfc1f560fa4dfa47d23b3fe2f5be986b9714f9ad1124bce8cb0bb746f6c8`), pedido a 130 x 120 mm con 3 hilos. API en 8001, web en 5174.
No se tocó el motor (`workers/embroidery/vectorize/*`) ni parámetros de costura.

## 3.1 Paleta (antes / después, mismo motor, misma imagen)

| | Antes (limite 3) | Antes (flujo viejo: limite inflado a 4) | Después |
|---|---|---|---|
| Colores de paleta del vectorizador | 3 (`#ec0303`, `#ed7c77`, `#fcf6f7`) | 4 (`#e45453`, `#ec0402`, `#f6a1a5`, `#fef6f6`) | **1** (`#eb0403`) |
| Anillos (subpaths) trazados | 23 239 | 30 076 | **119** |
| Objetos | 3 | 4 | **1** |
| Capas omitidas por casi blancas | 1 | 2 | **0** |
| `colour_limit_used` / pedido | - | 4 / 3 | **1 / 3** |
| Bloques de hilo en el JEF (relectura real, Ink/Stitch v3.2.2) | - | 2, el segundo sin puntadas, 1 cambio de color | **1, 0 cambios de color** |
| Puntadas / saltos / trims / límites | - | 7 945 / 182 / 30 / 111,0 x 111,6 | 7 971 / 194 / 31 / 111,0 x 111,6 |

Regla declarada en `evidence.stitching.palette_cleaning` (rule + thresholds + counts): 36 136 colores exactos de entrada ->
1 tinta; 25 239 fusionados por regla de mezcla tinta->blanco (tolerancia 30 RGB), 9 359 por vecindad (radio 40), 1 535 casi blancos
(halo); 1 tinta menor (< 1 % de la figura, a <= 80 RGB de otra) fusionada. De 314 450 píxeles de figura, 79 173 (25 %, el borde
suavizado y los casi blancos) vuelven al fondo y 235 277 quedan. Es limpieza de ruido de compresión, declarada como tal
(`is_noise_cleanup_not_geometry_removal: true`); no marca ningún check. El asset original (bytes, SHA, dimensiones) no cambia: el motor
recibe un PNG limpio (`cleaned_sha256 d29d57b7...`) y `evidence.input_sha256` lo declara.

## 3.2 / 3.4 Aviso previo (`GET /projects/{id}/assets/{asset_id}/legibility`)

Medido por apertura morfológica ponderada por largo de trazo (ver `legibility.py`). Mismo logo, mismo servidor:

| Tamaño pedido | Tinta | Trazo < 0,6 mm (largo / área) | Trazo < 0,8 mm | Aviso | Tamaño mínimo (80 % > 0,8 mm) |
|---|---|---|---|---|---|
| 130 x 120 | 110,5 x 111,1 | 13 % / 5 % | 24 % | **no** (límite 30 %) | ~121 x 121 mm, entra en 140 x 140 |
| 60 x 55 | 50,5 x 50,7 | 72 % / 57 % | 94 % | **sí** | ~122 x 123 mm, entra en 140 x 140 |

Texto exacto a 60 x 55: "El 72% del trazo mide menos de 0,6 mm; a 51 mm las letras no van a quedar legibles. El tamaño mínimo para que el 80% del
trazo supere 0,8 mm es de ~122 x 123 mm." Cuando el mínimo no entra en el bastidor (prueba `test_thin_strokes_warn...`): "...haría
falta un dibujo de ~N x M mm, que no entra en el bastidor (W x H mm): no hay un tamaño útil para este dibujo; conviene simplificarlo...".
Margen (3.4): +7,6 % (110,5 x 111,1 -> 119,0 x 119,6 mm), "Es solo más tamaño: no resuelve el problema de las letras finas."

**Discrepancia con la auditoría.** La auditoría midió "51,5 % < 0,6 mm" contando píxeles que no sobreviven k erosiones: eso es la
banda de borde de todo trazo, no su ancho (un trazo de 1,2 mm cuenta ~50 % como "fino"). Con el ancho real de trazo, a 130 x 120 el
logo NO dispara el aviso del 30 %: la mayor parte del trazo mide 1,1-1,5 mm. No se ajustó ningún umbral para que dispare. Lo que sí dice
la medición es que el 80 % > 0,8 mm exige ~121 mm de dibujo (hoy 111). Las contraformas finas (huecos de 0,3-0,6 mm que cierra la
compensación de 0,2 mm por lado) no las mide este aviso: eso es del motor (ronda 5 de Codex).

## 3.3 Gate visible

`JefHero`: título "todavía no está validado para coser"; estado digital y físico explícitos; lista de checks con `NO SE EJECUTÓ` en
negrita; incidencias `LEGIBILITY_RISK` (si el motor las emite) con la técnica por objeto si la evidencia la trae; descarga bloqueada
hasta marcar una confirmación que lista los pendientes. En el job real: `digital_checks_passed: false`, `file/dimensions/hoop`
passed, `geometry/satin/routing/visual` not_run, `sewout_status: untested`.

## Pruebas

- Motor + API (`tests/engine`): 203 OK (13 nuevas en `test_palette_legibility.py`, 4 de endpoint en `test_api_analysis.py`).
- Web: 179 OK (16 nuevas: `jefGate`, `JefHero`, `LegibilityNotice`); `npm run build` OK.
