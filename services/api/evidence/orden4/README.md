# Orden 4: SVG, bastidores Janome, límites fijos, telas, sin hilos, 12 colores

Medido el 2026-11-08 con API en 8001 y web (Vite, proxy `/api`) en 5174, Ink/Stitch v3.2.2 real. No se tocó el motor
(`workers/embroidery/vectorize/*`) ni `build_openapi.py`. No se marcó calibración ni `ready_for_sewout`: ambos jobs terminan en `needs_review`.
Los jobs se crearon por HTTP a través del servidor de Vite en 5174 (la UI cubierta por pruebas de web, no por navegador).

## 4.1 SVG de punta a punta

SVG real: `Anime_Socks_InkStitch.svg` (Ink/Stitch preparado, hoja 150,201 x 142,954 mm), SHA256 de entrada
`23f52af8909602833c8ed45e06a0051eed9fd229b81b4876e712a4cc41f3d1a1` (`svg/input.svg`).

| Bastidor | Resultado |
|---|---|
| RE28b (200 x 280) | `needs_review` en 18,1 s. JEF 14 816 bytes, relectura 150,0 x 142,8 mm (se borda a su tamaño, el bastidor es solo el límite), 6 789 puntadas, 3 bloques, 2 cambios de color. Código JEF del encabezado: 4. |
| RE20b (140 x 200) | `failed` con `HOOP_INCOMPATIBLE`: "El diseño (150 x 142.8 mm) no entra en el bastidor re20b (140 x 200 mm)." (`svg-hoop-incompatible/job.json`). Sin `DIMENSIONS_EXCEEDED` duplicado. |

- JEF: `svg/output.jef`, SHA256 `491d6cef33ff2e809c705c5b0e9660d211f7d31e8b52618fc53c165c06daf52a`.
- Un SVG cualquiera sin preparar (sin `width`/`height` ni estructura Ink/Stitch, p. ej. un logo descargado) falla con `INPUT_UNREADABLE`
  `reason: invalid_or_unprepared_svg`: es el comportamiento del motor para un SVG no preparado; no se tocó.

## 4.2 Bastidores de la Janome MC 550E

`sq10b` 100x100 (JEF 0), `sq14b` 140x140 (2), `re20b` 140x200 (2), `sq20b` 200x200 (4, `profile_version` 0.1 sin cambios),
`re28b` 200x280 (4), `re36b` 200x360 (4).

**Límite del formato JEF.** El encabezado JEF solo codifica 5 tamaños (110x110, 50x50, 140x200, 126x110, 200x200). Los bastidores mayores
(RE28b, RE36b) se escriben con el código 4 (200x200): el código no los distingue y **el encaje real lo decide el tamaño del diseño**, que el
servidor mide al releer el JEF y compara con el bastidor elegido. La máquina puede interpretar mal un diseño más grande que 200x200 con ese
código: sin prueba física, no está verificado.

## 4.3 Límites fijos

El ancho/alto máximo del trabajo es el del bastidor; la web ya no tiene campos de ancho/alto. El servidor rechaza (422) un destino mayor que el
bastidor. El diseño no se escala al cambiar de bastidor: si no entra, `HOOP_INCOMPATIBLE` con bastidor y medidas.
La «Variante de tamaño» conserva sus campos (es una petición explícita de otro tamaño, siempre <= bastidor).

## 4.4 Telas / 4.5 sin hilos / 4.6 12 colores

Telas nuevas `algodon`, `gabardina`, `pique`, `polar`, `jean`, `lino` (todas `proposed`, sin registro de calibración) más `gabardina_inicial`.
La web ya no muestra selector de hilo ni la fila «Bloques de hilo»; `thread_profile` sigue en los datos internos. `max_colors` 12 en
`profiles.json` (catálogo y máquina), en la validación y en el texto («Elegí entre 1 y 12 colores» con el catálogo real). El runner no se tocó.

## Logo real (job con 12 colores pedidos)

PNG 1254 x 1254, SHA256 `3ba1cfc1f560fa4dfa47d23b3fe2f5be986b9714f9ad1124bce8cb0bb746f6c8` (`logo/input.png`), sq14b, `algodon`, 12 colores.

| | Orden 3 (130 x 120, límite 3) | Orden 4 (SQ14b 140 x 140, límite 12) |
|---|---|---|
| Colores de paleta | 1 (`#eb0403`) | 1 (`#eb0403`): la paleta sigue fusionando halos; pedir 12 no la infla |
| `colour_limit_requested` / usado | 3 / 1 | 12 / 1 |
| Tamaño releído | 111,0 x 111,6 mm | 129,6 x 130,2 mm |
| Puntadas / bloques / cambios de color | 7 971 / 1 / 0 | 9 714 / 1 / 0 |
| Tiempo | - | 436 s |

- JEF: `logo/output.jef` (20 442 bytes), SHA256 `64c88a1d798c8ceb4d2e28866d7873ce958863c2a7cbcdc0e7b0f10cdd561ec4`, código de bastidor 2.
- Estado `needs_review`; incidencias: `DENSITY_REVIEW_REQUIRED`, `GEOMETRY_REPAIR_AMBIGUOUS`, `VISUAL_MISMATCH`, `ENGINE_DIAGNOSTIC_UNCLASSIFIED` (no calibrado).
- **Consecuencia del límite fijo:** el logo raster toma el bastidor entero como destino (`contain`). Con SQ20b (200 x 200) el mismo logo superó el
  plazo de digitalización de 600 s (`WORKER_TIMEOUT`, `logo/job-sq20b-timeout.json`). Un bastidor grande con una imagen raster puede no terminar.

## Pruebas

Motor + API: 209 OK (6 nuevas: bastidores, telas, 12 colores, destino <= bastidor, `HOOP_INCOMPATIBLE` por API, destino mayor rechazado).
Web: 179 OK; `npm run build` OK.
