# Perfil neutral: F rojo → verde

Propósito: demostrar que el cambio de id cierra F sin modificar reglas ni parámetros físicos.

Contenido: [Secuencia](#secuencia), [Resultados](#resultados), [Repro](#repro), [Referencias](#referencias).

## Secuencia

1. Merge autorizado de main68d7ecd hacia codex/motor: `3e618c0a87b23940900c8fde8489a8e9ac724ef7`. Único conflicto CONTINUAR.md: estructura/relevo Codex con hechos posteriores de main. Main no se cambió.
2. Control sobre ese merge: motor completo 182 pruebas sin fallos, 4 omitidas; F exit1 por dos literales preexistentes (Anime_Socks/anime_socks) en el id del perfil de referencia.
3. Renombre aislado `fcf74682921ea0aa3ca7c456791487e8e83541be`: **solo dos sustituciones** del valor del id, en inkstitch.py y su expectativa de test_api_analysis.py. Nuevo id gabardina_400ppm_referencia. El comentario y la documentación conservan la procedencia Anime Socks con espacio.
4. Corrida posterior: motor completo **182 sin fallos, 4 omitidas**; h2_eval **16 sin fallos, 1 omitida**; F **passed / exit0**, ocho checks 14/14, dos SVG omitidos, cero errores y cero per_logo_literals.

## Resultados

Se conservaron exactamente separación 0,45 mm, largo 2,5 mm, compensación 0,2 mm y ángulos. `git diff 3e618c0 fcf7468` contiene solo las dos sustituciones del identificador. Diff de tests/h2_eval vacío: no se tocó checker, static_review ni listas de aceptados. El cambio no es calibración y mantiene needs_review.

## Repro

Sobre los hashes respectivos, con Python empaquetado y deps locales API/worker:

- `python -B -m unittest discover -s tests/engine -p test_*.py -q`.
- `python -B -m unittest discover -s tests/h2_eval -p test_*.py -q` (después).
- `python -B tests/h2_eval/run_eval.py --worker-path <workers/embroidery> --out <F.json>`.

Los logs y JSON conservan estado, métricas, ruta del motor y tiempos reales. La ampliación posterior a 20 MP es otro commit y otra verificación.

## Referencias

- [Comparación](checks.json) · [F antes](F-before.json) · [F después](F-after.json)
- [Motor antes](motor-before.log) · [Motor después](motor-after.log) · [h2_eval](h2-after.log)
