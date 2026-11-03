# Revisión independiente de E v4

Propósito: cerrar la revisión de cobertura y los fallos reproducibles de medición de ancho, sin cambiar la calibración ni la geometría.

Contenido: [Hallazgos](#hallazgos), [Alcance](#alcance), [JEF identificados](#jef-identificados), [Reproducir](#reproducir), [Referencias](#referencias).

## Hallazgos

| Caso | Antes | Corrección |
|---|---|---|
| Figura toda de color, 8×8 px a 0,01 mm/px | 0 % fino aunque mide 0,08 mm y el supuesto es 0,4 mm; Pillow replicaba bordes | Apertura con exterior cero; figura inferior al kernel se informa toda fina |
| Línea de 4 px a 0,1 mm/px o 2 px a 0,2 mm/px | Kernel impar 5/3: marcaba como fino el ancho exacto de 0,4 mm | Kernel `ceil(min_px)`, también par; sin desplazamiento |
| 253 px con escala `0.4/253` | La división inversa daba 253,00000000000003 y elegía 254 | Verificar el producto físico antes de sumar un píxel; sin tolerancia arbitraria |
| Escala 1e-9 mm/px | Pedía un filtro de 400000001 px | No se construye ese filtro: si excede la dimensión menor, apertura vacía |

La medición sigue siendo una apertura cuadrada, orientada a ejes, con discretización de hasta 1 píxel. Se informa el ancho efectivo y el método. El supuesto de 0,4 mm sigue **sin calibrar**; no se cambian etiquetas, contornos ni puntadas.

## Alcance

Cobertura: revisión independiente y 7 pruebas existentes aprobadas. Se sondearon el umbral, blanco puro y un núcleo débil encerrado; sin nuevos fallos funcionales confirmados. Se corrigió el comentario que confundía mediana ponderada con color más frecuente.

La regla global de blanco ≥250 y la cancelación dentro de helpers nativos siguen como límites conocidos. No se altera esa política ni se afirma seguridad o calidad física general.

## JEF identificados

[jef-identity.json](jef-identity.json) verifica los dos exports H0-03 preservados contra `Optimizado` y `13x12`: comandos normalizados y paletas idénticos, hashes completos y offsets distintos registrados. No se ejecutaron originales ni se reexportó JEF.

No hay evidencia para decidir cuál de ellos fue copiado/renombrado y cosido por David. No atribuir aprobación física a todos los candidatos.

## Reproducir

```powershell
python -m unittest discover -s tests/engine -p 'test_vectorize_thin.py' -v
python -m unittest discover -s tests/engine -p 'test_*.py'
```

Usar el entorno y directorios temporales de [REPRODUCIR](../../../../workers/embroidery/vectorize/REPRODUCIR.md). Resultado final de esta entrega: `checks.json`.

## Referencias

- [Medición](../../../../workers/embroidery/vectorize/thin_features.py)
- [Regresiones](../../test_vectorize_thin.py)
