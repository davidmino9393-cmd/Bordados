# Worker H0-03

Propósito: probar SVG preparado → JEF → relectura/preview sin intervención de escritorio. Standalone, sin FastAPI; contratos v0.1 congelados sin modificar.

Contenido: [Uso](#uso), [salidas](#salidas), [límites](#limites), [relacionados](#relacionados).

## Uso

Python 3.12 con `pip install -r workers/embroidery/requirements.txt` en un entorno aislado. Ejecutables, versión y directorio de job son argumentos; no hay rutas de esta máquina en el código.

```powershell
python workers/embroidery/worker.py `
  --svg Anime_Socks_Bordado/Anime_Socks_InkStitch.svg `
  --job-dir workers/embroidery/evidence/nuevo-job `
  --inkstitch "$env:INKSTITCH_EXECUTABLE" `
  --inkscape "$env:INKSCAPE_EXECUTABLE" `
  --engine-version "$env:INKSTITCH_VERSION" --timeout 180
```

`--inkscape` solo verifica versión: la exportación se invoca directamente mediante las extensiones CLI de Ink/Stitch. Preview por Pillow desde JEF; no rasterización del vector. El entorno usado aquí tiene pyembroidery en `.deps`: añadir ese directorio a PYTHONPATH; no es necesario si se instala requirements en el venv.

## Salidas

| Archivo | Evidencia |
|---|---|
| output.jef | stdout binario real del exportador |
| preview.png | Trazos desde coordenadas releídas con pyembroidery |
| raw-commands.json | Órdenes/coordenadas acumuladas en 0.1 mm; sin fecha de cabecera |
| diagnostics.svg | Diagnóstico nativo completo, sin listas globales de avisos aceptados |
| *.process.json / *.stderr.txt | Comando, PID, duración, retorno y stderr íntegro |
| result.json | Métricas o fallo controlado; nunca aprobación física/digital |

No reutilizar directorio de job: se rechaza sin sobrescribir archivos. Código de salida 0 = exportación/relectura completadas, 1 = fallo. `ok` no significa ready_for_sewout. Los diagnósticos sin mapeo de objetos verificado quedan pendientes de revisión.

## Limites

- Solo SVG preparado de esquema Ink/Stitch 3; no migración silenciosa ni digitalización de otros logos.
- stdin cerrado, shell desactivado, ventanas ocultas y DISPLAY/WAYLAND_DISPLAY retirados. Windows arranca suspendido, asigna Job Object y luego reanuda; SIGKILL por grupo en POSIX (no probado aquí).
- No es sandbox de contenido SVG ni worker multiusuario de producción. H0-04 debe integrar perfiles/contratos, validación de geometría y permisos.
- Prueba Windows sin interacción; NO certifica Linux ni servicio Windows en sesión 0.

## Relacionados

[Resultados](evidence/README.md), [Bridge](evidence/bridge/README.md), [inventario](inventory/README.md), [tests](../../tests/engine/test_worker.py), [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
