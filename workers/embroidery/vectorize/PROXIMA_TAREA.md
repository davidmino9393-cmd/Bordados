# Próxima tarea: paleta con contraste verificable

Propósito: evaluar el refinamiento de cuantización sin romper firma, contratos ni la comparación de F por commit.

Contenido: [Base](#base), [Agents & Skills](#agents--skills), [Ejecución](#ejecución), [Aceptación](#aceptación), [Referencias](#referencias).

## Base

Motor: `4a7fd6b`; investigación: `2fbb6ca`. Mantener `vectorize(image, media_type, asset, analysis, settings, *, job_id, revision_id, cancel)` y los cinco campos de `VectorizeResult`.

MEDIANCUT actual deja 0 píxeles L<192 de los 68534 originales de contraste en Anime Socks. `kmeans=3` retiene 58895 y baja error RGB medio 7,671→3,985. Ese umbral es diagnóstico, no legibilidad. MAXCOVERAGE empeora otros diseños: no adoptarlo globalmente.

## Agents & Skills

| Orden | Responsable | Skills / escritura |
|---|---|---|
| 1 | `tester` | `core`, `test`; pruebas E en `tests/engine` |
| 2 | `backend-developer` | `core`; candidato en E y evidencia |
| 3 | `code-reviewer` | `core`, `code-review`; revisión independiente |
| 4 | Claude, evaluación F | Su arnés; sin escritura de Codex |

Corrección interna E ya autorizada. Aplicar la cadena al implementar, sin otra aprobación rutinaria. Orquesta el principal; los delegados no crean agentes.

## Ejecución

1. Leer buzón y fijar hashes. Registrar errores de F por caso y distinguir mediciones de inferencias.
2. Escribir controles pequeños: dos colores exactos, color escaso, bordes suavizados, texto fino como máscara/anotación, islas y huecos. Comprobar determinismo y cancelación.
3. Ensayar MEDIANCUT `kmeans=3` en copia aislada bajo `tests/engine/.tmp`, sin alterar la base que Claude mide. Pasar por trazado real a resolución original; guardar paleta, aristas, huecos por color, hashes, duración y recursos.
4. Comparar conjunto disponible y ambas escalas. Documentar especialmente sol/anillos, donde el error medio empeora levemente. No borrar el disco pálido automáticamente: puede ser relleno intencional.
5. Revisar y ejecutar las pruebas pertinentes. Si hay ventaja defendible, comunicar política/método y nuevo hash antes de pedir F. No presentar el experimento como producción terminada.

## Aceptación

- Controles estructurales, unidades `contain`, límite de colores, recursos y cancelación conservados.
- Sin cambio de firma/modelos, coordenadas por logo, resize silencioso ni descarte de detalles.
- Medir máscara y topología por color, contraste y costo; documentar cualquier regresión. No inventar umbrales de aprobación semántica por falta de ground truth.
- Claude repite F por hash fijo y revisa texto/bordes. Error RGB medio o IoU dependiente del mismo fondo no bastan para aceptar.
- Incidencias y H3 pendiente visibles; sin JEF ni aprobación física.

## Referencias

- [Inicio](CONTINUAR.md) · [Comandos](REPRODUCIR.md)
- [Experimentos](../../../tests/engine/evidence/quantization-research/README.md)
