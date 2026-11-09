# Técnicas del camino de referencia

Propósito: derivar puntadas por ancho local sin modificar `path_data_mm`, identidad ni coordenadas E1.

Contenido: [Medición](#medición), [Parámetros](#parámetros), [Rutas](#rutas), [Límites](#límites), [Documentos relacionados](#documentos-relacionados).

## Medición

- Máscara derivada en centros de píxel, registrada con la transformación E1; nunca se repara el original.
- Esqueleto Zhang-Suen: cadenas entre extremos/ramas; normales locales intersectan ambos bordes del trazo. Rieles y segmentos se verifican dentro de la máscara. No se decide por el ancho total del objeto.
- `reference_rings`: unidades locales con `ring_index` original, ancho local mínimo/mediano/máximo, técnica, rieles, guías, microdetalle y derivación.
- Apertura cuadrada: cuantiles y riesgos de legibilidad históricos; sesgo diagonal hasta √2. La selección local usa normales, no esos cuantiles.
- Contornos derivados: separar contactos repetidos y simplificar solo si conservan topología; conservar todos los huecos, incluso menores a 1 mm².

## Parámetros

| Ancho local | Técnica | Parámetros |
|---|---|---|
| <1 mm | Corrido central | Recto 2,5 mm; curvo 1,25 mm; compensación 0 |
| 1-4 mm | Satín real | 2 rieles y 1 guía de 2 nodos, en un único path |
| >4-<7 mm | Tatami conservador | Evita puntadas de satín largas y flotantes; requiere revisión |
| ≥7 mm | Tatami | Filas 0,35 mm; puntada máxima 5 mm |

- Satín: sin relleno; ancho de trazo medido; zigzag 0,40 mm; recorte 0,15; máximo 7 mm; corrido central inferior activo.
- Micro satín: altura original <5 mm o trazo <1,5 mm; zigzag 0,55 mm; sin contorno ni zigzag inferior; corrido central solo en tela elástica (piqué, polar), desactivado en tela estable.
- Compensación por lado: 0,25 mm estable; 0,35 mm si `fabric_profile` identifica elasticidad o punto.
- Tatami: refuerzo abierto, filas 5 mm, inset 1,5 mm, puntada máxima 5 mm, ángulo perpendicular al superior. Solape objetivo 1,5 mm bajo satines vecinos, limitado a píxeles E1.
- Islas <1 mm², rellenos netos <2 mm² y capas retenidas <2 mm² mantienen omisión informada. Los huecos nunca son ruido descartable.

## Rutas

- Componente: anillos E1 cuyas máscaras se tocan tras dilatar 0,30 mm (compensación 0,25 + redondeo JEF 0,05). Orden por vecino más próximo; cada componente se entra y se termina una vez.
- Dentro del componente: rellenos primero, en cadena; hueco ≤3 mm verificado dentro de la máscara → `ending_point`/`starting_point` sin corte; si no, corte. `autoroute_start` en el trazo más cercano al último relleno.
- Puentes corridos ≤3 mm, de un extremo a la línea central de otra pieza, solo si todo el segmento cae dentro de la máscara dilatada. `auto_satin` (o `auto_run` sin satín) por componente; Ink/Stitch 3.2.2 une ≤0,7 mm y corta a 1,0 mm ([prueba](../../../tests/engine/test_piece_bridges.py)).
- Corte siempre a la salida de cada componente y en cambios de color. Medición: cruces sobre tela vacía, todos cortados; ninguno queda flotante.

## Límites

Sin calibración ni aprobación física: `digital_readiness_evaluated=false`, `physical_approval=untested`, revisión pendiente. El adaptador H3 conserva su validación explícita independiente.

## Documentos relacionados

- [Pruebas](../../../tests/engine/test_reference_techniques.py)
- [Evidencia reproducible](../../../tests/engine/round6_evidence.py)
- [Entrada y reglas](CONTINUAR.md)
