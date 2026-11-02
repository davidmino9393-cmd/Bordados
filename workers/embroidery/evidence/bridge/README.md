# Evaluación MCP Bridge

Propósito: registrar el intento anterior al pivot CLI. Resultado: instalación/exportación bloqueada en este entorno; no un fallo gráfico demostrado ni una imposibilidad universal del Bridge.

Contenido: [Versiones](#versiones), [fallos](#fallos), [reproducir](#reproducir), [relacionados](#relacionados).

## Versiones

- Bridge 0.1.0, commit `89b96b6e85dc1dc67923371d941eb29da8ec3fe3`.
- Submódulo Ink/Stitch: `102bc89cc282b7d7f1af6c8b4435ee86b944280b` (sin versión de release verificada).
- Python portable 3.11.9; prueba del runner desde Python 3.12.14 con lxml 6.1.1.
- inkex: archivo oficial del tag EXTENSIONS_AT_INKSCAPE_1.4.1, descargado por HTTPS. No se ejecutó git clone/submodule ni se modificó el upstream.
- Inkscape local comprobado: 1.4.2 (f4327f4). No fue usado por la ruta Bridge.

## Fallos

1. Instalación en `.tools/bridge-deps`: `BackendUnavailable: Cannot import 'poetry.core.masonry.api'` (`install.log`). La distribución portable no propaga el entorno de build aislado.
2. Instalados backends localmente y reintentado sin build isolation: metadata inválida de inkex, `Expected matching RIGHT_PARENTHESIS ... lxml (>=4.5.0,<5.0.0 || >=5.0.0,<6.0.0)` (`install-retry.log`). No se parchearon constraints para fingir instalación correcta.
3. Invocación real del runner Bridge sobre copia del SVG: retorno 1, payload 0 bytes, `ModuleNotFoundError: No module named 'inkex'`; ver export-probe/result.json y stderr.txt.

No se alcanzó la ejecución gráfica. wxPython/SDK MCP no quedaron instalados; no se ejercitó el transporte MCP stdio. El test fue del runner real de exportación, no un servidor MCP saludable. Los fuentes/portable descargados permanecen locales e ignorados; logs y hashes sí están versionados.

Se avisó al usuario del fallo antes de comenzar el fallback. El error de instalación queda para retomar el Bridge con un entorno completo compatible; no se afirma que dependa de Inkscape.

## Reproducir

`python workers/embroidery/probe_bridge.py --bridge-root RUTA --inkstitch-root RUTA --engine-python RUTA --svg SVG --out DIRECTORIO_NUEVO`

Conservar las revisiones exactas indicadas y los requisitos upstream. El probe copia el SVG y captura bytes, stderr y retorno.

## Relacionados

[Repositorio](https://github.com/GreerBK/InkStitchMCP), [commit](https://github.com/GreerBK/InkStitchMCP/commit/89b96b6e85dc1dc67923371d941eb29da8ec3fe3), [resultado](export-probe/result.json), [worker](../../README.md).
