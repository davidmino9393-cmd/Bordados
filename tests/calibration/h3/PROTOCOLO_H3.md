# Protocolo de la muestra de calibración H3

Propósito: medir en tela lo que hoy son parámetros **provisionales y sin calibrar**: ancho mínimo bordable, densidad y compensación del satin, separación del relleno y pespunte de línea fina. Nada de esto se afirma hasta que haya medidas físicas. Referencias previas de la máquina y de la digitalización: [REFERENCIAS_JANOME_MC550E.md](REFERENCIAS_JANOME_MC550E.md).

Contenido: [Archivos](#archivos) · [Cómo coser](#cómo-coser) · [Qué medir](#qué-medir) · [Para qué sirve](#para-qué-sirve) · [Límites](#límites)

## Archivos
| Archivo | Para qué |
|---|---|
| `muestra_h3.jef` | Se carga en la Janome MC 550E (150 × 160 mm de hoja; se borda un marco de 140 × 150 mm) |
| `muestra_h3.svg` | Origen editable (Ink/Stitch). Regenerar: `python generar_muestra.py` |
| `muestra_h3_vista_previa.png` | Cómo se ve releyendo el JEF (no es una foto de bordado) |
| `planilla_h3.csv` | Una fila por elemento: valor nominal, medida digital y columnas vacías para lo físico |

## Cómo coser
1. Misma tela, estabilizador e hilo que se usarán en producción (anotarlos). Bastidor SQ20b.
2. Una sola pasada, sin ajustar velocidad ni tensión a mitad de camino; anotar velocidad y aguja.
3. Dejar la tela en el bastidor hasta medir (el retiro cambia las medidas).

## Qué medir
Con calibre o regla milimetrada, sobre el bordado ya cosido (sin planchar):

| Fila | Elemento | Medir |
|---|---|---|
| A (8) | Satin de ancho 0,6 a 6 mm | Ancho real de cada columna |
| B (6) | Satin de 3 mm, separación 0,30 a 0,60 mm | Si se ve la tela entre puntadas; ancho real |
| C (5) | Satin de 3 mm, compensación 0 a 0,4 mm | Ancho real (la compensación debería acercarlo a 3,0) |
| D (6) | Relleno 12 × 12 mm, separación 0,3 a 0,8 mm (el último con base) | Lado real; cobertura; fruncido |
| E (6) | Líneas de 25 mm, pespunte simple, triple, quíntuple | Largo y grosor visibles |
| Marco | 140 × 150 mm | Retiro de la tela en cada eje |

En `planilla_h3.csv`: `ancho_medido_mm`, `aspecto` (uno de `bien`, `hueco_se_ve_la_tela`, `fruncido`, `hilo_roto`, `borde_irregular`, `no_se_distingue`) y `notas`. Fotografiar la muestra entera y cada fila de cerca: las fotos se suben desde la web en «Registrar muestra física» (hasta 4 por muestra).

## Para qué sirve
- **Ancho mínimo bordable** (hoy 0,4 mm provisional en `thin_features.py`): el menor ancho de la fila A con aspecto `bien`.
- **Perfil de tela** (`calibration_status`): pasa de `proposed` a `physically_calibrated` solo con un registro de calibración que cite esta muestra.
- **Densidad y compensación** que usa H3 al elegir técnica por ancho físico.

## Límites
Una muestra representa una tela, un estabilizador, un hilo y una máquina: otra combinación necesita otra muestra. El valor digital de la planilla es lo que el motor predice; la diferencia con lo medido es el dato de calibración.
