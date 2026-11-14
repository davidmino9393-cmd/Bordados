# Worker H0-03

Propósito: probar SVG preparado → JEF → relectura/preview sin escritorio. Standalone, sin FastAPI; contratos v0.1 congelados.

Contenido: [Uso](#uso), [verificación](#verificacion), [regresiones](#regresiones), [salidas](#salidas), [límites](#limites), [relacionados](#relacionados).

## Uso

Python 3.12 con `pip install -r workers/embroidery/requirements.txt` en un entorno aislado. Ejecutables, versión y job-dir son argumentos; sin rutas de esta máquina.

```powershell
python workers/embroidery/worker.py `
  --svg Anime_Socks_Bordado/Anime_Socks_InkStitch.svg `
  --job-dir workers/embroidery/evidence/nuevo-job `
  --inkstitch "$env:INKSTITCH_EXECUTABLE" `
  --inkscape "$env:INKSCAPE_EXECUTABLE" `
  --engine-version "$env:INKSTITCH_VERSION" --timeout 180
```

`--inkscape` solo verifica versión; la exportación usa las CLI de Ink/Stitch. Preview con Pillow desde JEF, sin rasterizar. pyembroidery está en `.deps`: agregarlo a PYTHONPATH o instalar requirements.

## Verificación

```powershell
python workers/embroidery/verify_commands.py workers/embroidery/evidence/cli-main-final/raw-commands.json services/api/evidence/h0-04/raw-commands.json
```

Parsea JSON, no bytes (CRLF/LF no afecta). Reporta conteos, índices y veredicto.

## Regresiones

```powershell
python -m unittest tests/engine/test_regressions.py -v
```

Ambas variantes: dimensiones ±0.2 mm, needle_stitches, thread_blocks y raw-commands contra el JEF. Nueva variante: agregar JEF/raw-commands a `evidence/<caso>/` y el caso al test.

## Salidas

| Archivo | Evidencia |
|---|---|
| output.jef | stdout binario real del exportador |
| preview.png | Trazos desde coordenadas releídas con pyembroidery |
| raw-commands.json | Órdenes/coordenadas acumuladas en 0.1 mm; sin fecha de cabecera |
| diagnostics.svg | Diagnóstico nativo completo, sin listas globales de avisos aceptados |
| *.process.json / *.stderr.txt | Comando, PID, duración, retorno y stderr íntegro |
| result.json | Métricas o fallo controlado; nunca aprobación física/digital |

No reutilizar directorio de job. Código 0 = exportación/relectura completas; 1 = fallo. `ok` no implica ready_for_sewout; diagnósticos sin mapeo quedan en revisión.

## Limites

- Solo SVG preparado de esquema Ink/Stitch 3; no migración silenciosa ni digitalización de otros logos.
- stdin cerrado, shell desactivado, ventanas ocultas y DISPLAY/WAYLAND_DISPLAY retirados. Windows arranca suspendido, asigna Job Object y luego reanuda; SIGKILL por grupo en POSIX (no probado aquí).
- No es sandbox de SVG ni worker multiusuario. H0-04 integra perfiles/contratos, geometría y permisos.
- Prueba Windows sin interacción; NO certifica Linux ni servicio Windows en sesión 0.

## Relacionados

Resultados, Bridge, inventario, [tests](../../tests/engine/test_worker.py), [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
