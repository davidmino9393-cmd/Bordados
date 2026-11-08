# Técnicas del camino de referencia

Propósito: seleccionar puntadas por ancho medido sin sustituir la máscara registrada de E1 ni habilitar H3.

Contenido: [Medición](#medición), [Selección](#selección), [Límites](#límites), [Referencias](#referencias).

## Medición

- Por anillo exterior con sus huecos: máscara en los centros de píxel y escala de E1; apertura cuadrada de `thin_features._opening` con exterior cero.
- Distribución de área que sobrevive cada apertura: min/p10/p20/mediana/p90 y fracción bajo 0,4/0,6/0,8/1,0 mm. Aperturas y cuantiles usan anchos enteros de píxel; orientación diagonal puede sesgar hasta √2.
- `minimum_feature` y su política no cambian. `LEGIBILITY_RISK`: más del 30% del área del objeto bajo el supuesto provisional de 0,4 mm. Incluye técnica y tamaño mínimo para que el 80% alcance 0,8 mm, calculado con p20; no garantiza lectura ni aprobación física.

## Selección

| Mediana por anillo | Técnica de referencia | Compensación por lado | Filas |
|---|---|---|---|
| <0,9 mm | Corrida por esqueleto Zhang–Suen | 0; atributo ausente | Sin relleno |
| 0,9–<2 mm | Relleno alternativo; satén pendiente | min(0,2; 0,25×mediana) mm | 0,35 mm |
| ≥2 mm | Relleno | min(0,2; 0,25×mediana) mm | 0,45 mm |

- `reference_rings` publica técnica, anchos, parámetros, omisión y derivación por anillo; `stitch_path_mm` contiene la línea central derivada. Un objeto de color puede producir grupos de técnicas distintos, con `data-source-object-id`.
- `path_data_mm` conserva exactamente la máscara de E1; fidelidad contra esa máscara. La corrida no recorre el contorno cerrado: recorre segmentos y ciclos del esqueleto.
- `stitchable.plan`, su mínimo de 1 mm² y su tolerancia permanecen intactos. Después se omiten rellenos con área neta <2 mm² y capas de color cuya área retenida total sea <2 mm². Cada nueva omisión lleva aviso localizado y área medida.
- La relectura binaria del JEF rechaza bloques de hilo sin puntadas, incluidos bloques finales y discrepancias entre tabla y cambios de color. Un export inválido no se entrega como exitoso.

## Límites

Satén: Ink/Stitch 3.2.2 lo admite, pero faltan rieles/correspondencias verificados; se entrega el fallback autorizado. Trazos, rutas y puntadas todavía requieren revisión. No se cambia `_fill_attributes`: H3 atestiguado sigue rechazando corrida/satén no implementados. `digital_readiness_evaluated=false`, `physical_approval=untested`; David mide H3.

## Referencias

- [Pruebas](../../../tests/engine/test_reference_techniques.py)
- [Reproducción del job local](../../../tests/engine/round5_evidence.py)
- [Entrada y reglas](CONTINUAR.md)
