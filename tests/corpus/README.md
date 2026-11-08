# Corpus de pruebas de entrada

Propósito: medir con archivos reales cuántos tipos de diseño y de formato llegan a un JEF, en vez de suponerlo.

Contenido: [Qué hay](#qué-hay) · [Cómo correrlo](#cómo-correrlo) · [Cómo se lee el resultado](#cómo-se-lee-el-resultado) · [Qué cubre y qué no](#qué-cubre-y-qué-no)

Documentos relacionados: [COMO_USAR.md](../../COMO_USAR.md) · [services/api/docs/CONFIG.md](../../services/api/docs/CONFIG.md)

## Qué hay
| Archivo | Qué hace |
|---|---|
| `generate_corpus.py` | Crea los archivos de prueba y `manifest.json` con lo que se espera de cada uno. No hay binarios en el repositorio: todo sale de este script |
| `run_corpus.py` | Los pasa por la API real (Inkscape e Ink/Stitch reales, datos en una carpeta temporal) y mide cada uno |

## Cómo correrlo
Desde la raíz del repo, con el entorno de la API y su configuración privada (`services/api/.runtime/api-config.json`):

```
python tests/corpus/generate_corpus.py --out RUTA_DEL_CORPUS
python tests/corpus/run_corpus.py --dir RUTA_DEL_CORPUS --report RUTA_DEL_INFORME
python tests/corpus/run_corpus.py --dir RUTA_DEL_CORPUS --preconvert
```

| Opción | Qué hace |
|---|---|
| `--preconvert` | Convierte cada archivo con todos los formatos admitidos y sube el PNG resultante: mide cómo andaría un formato que el catálogo todavía no admite |
| `--only TEXTO` | Solo los archivos cuyo nombre contiene el texto |
| `--report RUTA` | Guarda `RUTA.json` con una fila por archivo |
| `--dir` con archivos propios | Sin `manifest.json`, cada archivo se mide sin juicio previo (sirve para probar tus diseños) |

Cada trabajo con Ink/Stitch real tarda de unos segundos a minutos: el corpus completo, unos 10 minutos.

## Cómo se lee el resultado
| Resultado | Significa |
|---|---|
| `BORDADO` | Terminó en `needs_review` con un JEF de entre 50 y 300 000 puntadas |
| `BORDADO_CON_AVISOS` | Igual, con avisos de que el bordado no se parece a la imagen (`VISUAL_MISMATCH`) |
| `BORDADO_SOSPECHOSO` | Hay JEF pero con una cantidad de puntadas fuera de lo razonable |
| `RECHAZADO:CODIGO` | La API no lo aceptó; el código es el del error |
| `FALLA:CODIGO` | El trabajo se creó y falló |

`esperado` en el manifiesto es `ok`, `libre` (se mide y se informa, sin juicio previo), `rechazo:CODIGO` o `falla:CODIGO` (limitación conocida). El ejecutor termina con código 1 si algo no coincide. **`BORDADO` no quiere decir que sirva**: dice que el motor produjo un archivo medible; que cosido quede bien solo se sabe con la muestra física (H3).

## Qué cubre y qué no
- Cubre: PNG, JPEG, SVG común, y con `--preconvert` WebP, GIF, BMP, TIFF y PDF; logos, texto, línea fina, degradado, foto simulada, baja y alta resolución, transparencia, EXIF y archivos rotos.
- No cubre: HEIC (necesita una librería extra), EPS (necesita Ghostscript), fotos reales, ni la calidad al coser.
- Los diseños son sintéticos. Para probar tus propios archivos, ponelos en una carpeta y usá `--dir`.
