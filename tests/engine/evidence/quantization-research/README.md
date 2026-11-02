# Investigación de cuantización

Propósito: aislar la pérdida de contraste manteniendo intacto el módulo E que Claude evalúa en `4a7fd6b`.

Contenido: [Método](#método), [Hallazgos](#hallazgos), [Reproducir](#reproducir), [Referencias](#referencias).

## Método

- 9 entradas: 6 fixtures planos, texto pequeño, degradado y referencia Anime Socks.
- Misma máscara de fondo de E, mismos píxeles y límite de colores por caso.
- Comparar Pillow MEDIANCUT actual, MEDIANCUT con `kmeans=3` y MAXCOVERAGE. Sin dependencias nuevas.
- `comparison.json`: hash, máscara, paletas, error RGB medio y conservación de píxeles con luminancia menor a 192.
- El umbral 192 es un diagnóstico de contraste, no un criterio de legibilidad ni aprobación. Error medio bajo no garantiza preservar detalles pequeños.
- PNG: previews de color reducidas a 500 px solo para mostrar. No son geometría vectorizada ni preview de puntadas.

## Hallazgos

En Anime Socks se retiran los blancos de fondo y quedan 759420 píxeles. Hay 68534 píxeles originales con luminancia menor a 192, pero MEDIANCUT sin refinamiento deja **0**. La pérdida ocurre al cuantizar, no por un fallo del consenso del borde blanco.

| Método | Error RGB medio | Píxeles originales de contraste conservados |
|---|---:|---:|
| MEDIANCUT actual | 7,671 | 0 |
| MEDIANCUT `kmeans=3` | 3,985 | 58895 |
| MAXCOVERAGE | 7,728 | 68534 |

El refinamiento mejora el error medio en 6 casos, empata 1 y empeora levemente 2 (sol y anillos). MAXCOVERAGE produce errores grandes en varios diseños planos; no es un reemplazo global justificable.

**No se cambia producción.** Falta evaluar topología por color, máscara, texto y costo de cómputo con F. El fondo blanco inferido, los bordes y los parámetros provisionales siguen requiriendo revisión. No se genera JEF.

## Reproducir

```powershell
python tests/engine/experiments/quantization_probe.py --image tests/fixtures/h2/Anime_Socks.png --colors 3 --output tests/engine/.tmp/color-research
python -m unittest discover -s tests/engine -p 'test_quantization_probe.py' -v
```

Usar Pillow 12.3.0 y Pydantic 2.14.1 del entorno existente. El control de 2 colores conocidos comprueba error cero, transparencia, conteos de contraste y determinismo del experimento. No valida una nueva política de E.

## Referencias

- [Resumen de los 9 casos](summary.json)
- [Probe](../../experiments/quantization_probe.py)
- [Coordinación con Claude](../../../../workers/embroidery/vectorize/COORDINACION.md)
