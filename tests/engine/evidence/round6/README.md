# Orden 6: logo real según la guía de bordado

Propósito: medir antes/después del logo real (1254×1254 px, SQ14b, algodón, 12 colores) con Ink/Stitch 3.2.2 y JEF releído. Sin calibración ni aprobación física: `needs_review`.

Contenido: [Medición](#medición) · [Técnicas](#técnicas) · [Cortes](#cortes) · [Límites](#límites) · [Repro](#repro)

## Medición

| Medida (JEF releído) | Antes (orden 5) | Después |
|---|---|---|
| Puntadas | 8 871 | 9 905 |
| Bloques / cambios de color | 1 / 0 | 1 / 0 |
| Saltos JEF (crudos / con desplazamiento) | 212 / 209 | 188 / 74 |
| Trims leídos (pyembroidery, `trim_at=3`) | 32 | 38 |
| Cortes explícitos (3 saltos nulos) | 1 | 38 |
| Recorrido de salto | 2 394,7 mm | 705,0 mm |
| Tamaño | 120,4 × 121,0 mm | 120,0 × 120,6 mm |
| Digitalización (procesos Ink/Stitch) | 414,1 s | 217,0 s |
| Troubleshoot | `Border crosses itself` | ninguno |

Margen al bastidor ≥9,7 mm por lado. SHA256: PNG `3ba1cfc1…6f6c8`, E1 `8fb87ee0…936c0`, SVG previo al ruteo `be02413c…3f0b7`, SVG final `2983e84c…5c1e6`, JEF `2a4c933d…32aa9`. Todos en [measurements.json](measurements.json).

## Técnicas

| Ancho local | Unidades | Técnica |
|---|---|---|
| <1 mm | 354 | corrido 2,5 mm; curvas 1,25 mm |
| 1–<1,5 mm | 124 | satén micro 0,55 mm, sin underlay |
| 1,5–4 mm | 155 | satén 0,40 mm, inset 0,15, máx. 7 mm, center-walk |
| >4–<7 mm / ≥7 mm | 2 / 2 | tatami 0,35 mm, underlay 5 mm, inset 1,5 mm, ⟂ |

Tras `auto_satin`: 288 columnas con 2 rieles + 1 travesaño (155 a 0,40; 133 a 0,55). Compensación 0,25 mm.

## Cortes

Clasificación de cada salto contra la máscara E1 dilatada 0,30 mm ([script](../../round6_evidence.py)):

| Salto | Antes | Después |
|---|---|---|
| Cruza tela vacía | 38 (2 334,5 mm) | 32 |
| … cortado explícitamente | 0 | 32 |
| … solo por regla de 3 saltos | 31 | 0 |
| … hilo flotante visible | 7 (máx. 22,4 mm) | 0 |
| Corte dentro de una pieza | 0 | 5 |

Mínimo físico: 28 componentes ⇒ 27 cruces. El "32" de antes no cortaba: dejaba 7 puentes visibles. Exceso actual: 5 cruces y 5 cortes internos, porque `auto_satin` decide su ruta interna y hay piezas unidas solo a través del relleno, que se borda antes.

## Límites

Sin bordado físico. El JEF cambia de hash en cada export (fecha en la cabecera); los conteos se reproducen. El runner del API deriva el inset de la constante: 0,4 → 2×0,25 = 0,5 mm, sin editar `services/api`.

## Repro

`python -B tests/engine/round6_evidence.py --baseline-dir <orden5/logo-sq14b> --source-run <job_917dd22d…> --out <nuevo> --inkstitch <exe>`; pruebas: [evidencia](../../test_round6_evidence.py), [puentes](../../test_piece_bridges.py).
