# Reproducir y verificar

Propósito: ejecutar evidencia y pruebas con el entorno existente, sin instalar dependencias globales.

Contenido: [Entorno](#entorno), [Comandos](#comandos), [Resultados previos](#resultados-previos), [Referencias](#referencias).

## Entorno

Desde `C:\dev\wt-motor`, PowerShell:

```powershell
$enginePython = 'C:\Users\david\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$PWD/services/api/.deps;$PWD/workers/embroidery/.deps"
$env:TEMP = "$PWD/tests/engine/.tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
& $enginePython -c 'import sys,PIL,pydantic; print(sys.version); print(PIL.__version__,pydantic.__version__)'
```

Observado: Python 3.12.14, Pillow 12.3.0, Pydantic 2.14.1. Dependencias aisladas: API `.deps` con FastAPI 0.162.0/Uvicorn 0.54.0; worker `.deps` con pyembroidery 1.5.1. La ruta del intérprete es del entorno local, no configuración de producción.

## Comandos

```powershell
& $enginePython -m unittest discover -s tests/engine -p 'test_vectorize*.py' -v
& $enginePython -m unittest discover -s tests/engine -p 'test_quantization_probe.py' -v
& $enginePython tests/engine/experiments/quantization_probe.py --image tests/fixtures/h2/Anime_Socks.png --colors 3 --output tests/engine/.tmp/color-research
& $enginePython -m unittest discover -s tests/engine -p 'test_*.py' -v
```

La suite completa inicia HTTP en `127.0.0.1`. Dentro del sandbox se bloqueó `asyncio` en su socket interno antes de Uvicorn; repetir mediante escalación autorizada, no modificar API para resolverlo. Los directorios temporales van bajo el workspace: el temp global puede redirigirse en cada ejecución.

Preferir RTK para Git/búsqueda/lectura compatibles; fallback original si falla. El índice Git reside fuera del worktree (`C:\dev\bordados\.git/worktrees/wt-motor`): add/commit pueden requerir escalación. No ampliar operaciones Git autorizadas.

## Resultados previos

- Verificación final en `2fbb6ca`, antes de este relevo: **50/50 pruebas completas**, 0 fallos/errores, 19,337 s, fuera del sandbox. Incluye las 49 previas y el control de investigación.
- Revisión del trazado: 300 máscaras multicolor, paridad por píxel y determinismo.
- F reportado por Claude: 14/14 raster estructural, 2 SVG omitidos, mediana 0,64 s, máximo 5,1 s. IoU de primer plano 1 usa la misma regla de fondo y no demuestra calidad.
- Previews del probe a 500 px: solo visualización. Métricas calculadas a resolución original; no son puntadas.

## Referencias

- [Inicio](CONTINUAR.md) · [Evidencia de complejidad](../../../tests/engine/evidence/h2-complexity/README.md)
- [Investigación](../../../tests/engine/evidence/quantization-research/README.md)
