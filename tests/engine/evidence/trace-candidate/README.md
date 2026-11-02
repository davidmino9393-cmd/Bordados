# Candidato de paleta: trazado completo

Propósito: comprobar si el experimento `kmeans=3` llega al documento y SVG completos sin cambiar el módulo E de producción.

Contenido: [Método](#método), [Resultados](#resultados), [Límites](#límites), [Reproducir](#reproducir), [Referencias](#referencias).

## Método

- 10 casos: 6 planos, texto pequeño, degradado y Anime Socks en dos tamaños (9 imágenes distintas).
- Baseline E `4a7fd6b` y copia temporal con MEDIANCUT `kmeans=3`, en subprocesos separados. Se verifica el módulo importado y el hash del código; producción queda intacta.
- 2 ejecuciones por variante/caso: 40 trazados. Documento, SVG y evidencia del método deterministas, sin comparar tiempos.
- 10/10 casos trazan en ambas variantes. Misma máscara de primer plano, cantidad de píxeles, marco y bounds. Colores dentro del límite, parámetros provisionales visibles y ninguna eliminación por tamaño.
- Precancelación devuelve `JOB_CANCELLED` en ambas variantes.

## Resultados

| Caso | Baseline → candidato |
|---|---|
| Anime Socks, ambas escalas | Error RGB medio 7,671 → 3,985; aristas 425078 → 110028 |
| SVG Anime 150 / 126 | 7,05 → 2,11 MB / 6,97 → 2,08 MB |
| Anillos / sol | Error RGB empeora levemente: 2,609 → 2,626 / 5,176 → 5,270 |
| Degradado | RGB mejora, pero dura 2,56–2,64 → 2,94–3,01 s |
| JPEG simple | RGB mejora, pero dura 0,58–0,61 → 0,74–0,83 s |

Los huecos **por color** cambian: Anime 5839 → 337; degradado 377 → 1; JPEG 10 → 7. Esto puede reducir ruido o perder detalles: no demuestra mejora semántica. La unión del primer plano no cambia, pero su reparto por color sí.

## Límites

No se selecciona el candidato para producción. Falta evaluación independiente de topología por color, texto y bordes. El tiempo es una medición local; no se midió RAM ni el peor caso. Se probó precancelación, no cancelación dentro de la llamada nativa de Pillow. Sin JEF, calibración H3 ni aprobación digital/física.

## Reproducir

```powershell
python tests/engine/experiments/trace_candidate.py --output tests/engine/.tmp/trace-new-run
```

Usar el entorno existente (Python 3.12.14, Pillow 12.3.0, Pydantic 2.14.1). La copia aislada queda en `.tmp`; no se usa Git ni se borran fuentes.

## Referencias

- [Comparación](summary.json) · [Baseline](baseline.json) · [Candidato](candidate.json)
- [Script](../../experiments/trace_candidate.py)
- [Investigación previa](../quantization-research/README.md)
