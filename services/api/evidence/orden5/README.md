# Orden 5: el bastidor es un límite, no el destino de una imagen

Medido el 2026-11-08, API en 8001 y web (Vite, proxy `/api`) en 5174 (`--strictPort`), Ink/Stitch v3.2.2 real, `algodon`, 12 colores pedidos.
No se tocó `vectorize/*` ni `build_openapi.py`. No se marcó calibración ni `ready_for_sewout` (ambos JEF terminan en `needs_review`).

## Cambio
- `legibility.raster_box`: destino de un raster = `min(lado del bastidor, 130 mm)` por lado; el runner lo aplica antes de la compensación de tracción
  (misma regla en el aviso de legibilidad). La relación de aspecto la conserva el motor (`contain`). Nunca supera el bastidor.
- Una variante de tamaño es un pedido explícito de otro tamaño (<= bastidor): no se acota. El SVG preparado conserva su tamaño propio.
- La web no tiene campos libres de ancho/alto (sin cambios).

## Antes / después (logo real 1254x1254, SHA256 de entrada `3ba1cfc1...6f6c8`)
| Caso | Orden 4 | Orden 5 |
|---|---|---|
| SQ14b tamaño releído | 129,6 x 130,2 mm | 120,4 x 121,0 mm |
| SQ14b tiempo | 436 s | 419,5 s (414 s de digitalización) |
| SQ20b tamaño | superó 600 s, `WORKER_TIMEOUT` | 120,4 x 121,0 mm, `needs_review` en 422,3 s |
| Puntadas SQ14b / SQ20b | 9 714 / - | 8 871 / 8 871 |

Los cuatro jobs corrieron a la vez con 2 workers, así que los tiempos incluyen competencia por CPU y cola (los SVG, que digitalizan en ~17 s, esperaron turno).

## SVG real (sin cambios respecto de la orden 4)
| Bastidor | Resultado |
|---|---|
| RE28b | `needs_review`, JEF 14 816 bytes, 150,0 x 142,8 mm, 6 789 puntadas, 3 bloques |
| RE20b | `failed` `HOOP_INCOMPATIBLE` (150 x 142.8 no entra en 140 x 200) |

SHA256 de los JEF en `SHA256SUMS.txt`. El JEF del SVG en RE28b tiene el mismo tamaño y puntadas que en la orden 4 pero distinto SHA256 (491d... antes): no se investigó la causa (probable metadato de fecha del encabezado JEF).
