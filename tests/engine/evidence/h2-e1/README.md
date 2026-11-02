# Evidencia E1

Propósito: mostrar la ejecución real del módulo sobre 6 archivos sintéticos versionados. No reemplaza la evaluación F.

Contenido: [Resultados](#resultados), [Reproducir](#reproducir), [Verificación](#verificación), [Referencias](#referencias).

## Resultados

- Casos: sol, hoja transparente, escudo, olas, anillos y JPEG simple.
- Cada carpeta: `document.json`, `editable.svg`, `evidence.json`, `preview.png`.
- `summary.json`: hashes, bounds físicos, colores, duración y comparación de 2 ejecuciones por caso.
- `verified_mask`: contornos de la segmentación explícita, con huecos. No afirma reconocimiento semántico ni fidelidad de color perfecta.
- Cuantización: diferencia RGB medida y `VISUAL_MISMATCH` visible en los 6 casos. Se pueden observar franjas de color en bordes suavizados; no se ocultaron ni borraron detalles para aprobarlos.
- Parámetros de puntada provisionales: `DENSITY_REVIEW_REQUIRED` y decisiones dentro del documento. Ningún resultado declara aprobación digital o física.
- Análisis IA: no ejecutado en este smoke. No se usó OpenAI/Ollama ni se generaron JEF.
- Previews: render real de los SVG con Inkscape 1.4.2 CLI; no simulación de puntadas.

## Reproducir

Desde la raíz, con Python 3.12+, Pydantic 2.14.1 y Pillow 12.3.0 disponibles:

```powershell
python tests/engine/vectorize_evidence.py --case logo-sol-01 --case logo-hoja-01 --case logo-escudo-01 --case logo-ola-01 --case anillo-doble-01 --case jpeg-simple-01 --output tests/engine/.tmp/e1-new-run
```

Agregar `--inkscape <ruta-del-CLI>` para guardar previews PNG. La duración varía; documento, SVG y evidencia del método se comparan sin ella. Los hashes de entrada se verifican contra el manifiesto, que no se modifica.

## Verificación

`checks.json` registra la suite completa: 46 pruebas aprobadas, 15 nuevas E1. Las pruebas HTTP existentes requirieron salir del sandbox: adentro se bloqueó `asyncio` al crear su socket interno, antes de iniciar Uvicorn. La API no se modificó.

También se verificaron sin reexportar los 2 JEF históricos guardados, 71 referencias originales intactas y 29 archivos de contrato con sus excepciones documentales previas autorizadas.

## Referencias

- [Interfaz E1](../../../../workers/embroidery/vectorize/README.md)
- [Fixtures](../../../fixtures/h2/LEEME.txt)
- [Pruebas E1](../../test_vectorize.py)
- [Adaptador H3](../../test_vectorize_inkstitch.py)
