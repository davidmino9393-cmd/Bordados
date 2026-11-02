# Configuración privada de la API

Propósito: documentar el JSON privado que `ApiConfig` carga desde `EMBROIDERY_API_CONFIG`. No es entrada HTTP ni se versiona.

Contenido: [Carga](#carga), [Campos](#campos), [Ejemplo](#ejemplo), [Errores](#errores).

## Carga

```powershell
$env:EMBROIDERY_API_CONFIG = "C:/private/embroidery-api.json"
$env:PYTHONPATH = "services/api"
python -m embroidery_api.main
```

Desde la raíz del repo. `main.py` escucha en `127.0.0.1:8000`. Las rutas relativas se resuelven contra el cwd; usar absolutas.

## Campos

Los nombres son exactos. `requerido` no tiene default.

| Campo | Tipo | Default | Regla |
|---|---|---|---|
| `data_root` | string | requerido | Raíz de `assets/`, `jobs/` y `runs/`; se crea al iniciar. |
| `profiles_path` | string | requerido | JSON del catálogo de perfiles. |
| `python_executable` | string | requerido | Intérprete que ejecuta el worker. |
| `inkstitch_executable` | string | requerido | CLI de Ink/Stitch. |
| `engine_version` | string | requerido | Se pasa al worker tal cual, ej. `v3.2.2`. |
| `signing_key` | string | requerido | Secreto HMAC de al menos 32 bytes UTF-8. |
| `public_base_url` | string | requerido | Origen HTTP(S) usado en URLs de descarga. |
| `service_token` | string/null | `null` | Bearer opaco. |
| `basic_username` | string/null | `null` | Basic auth; requiere también password. |
| `basic_password` | string/null | `null` | Basic auth; requiere también username. |
| `inkscape_executable` | string/null | `null` | Opcional; solo verifica versión. |
| `principal_id` | string | `h0_user` | Propietario único de recursos en H0. |
| `timeout_s` | number | `180` | Finito y > 0. |
| `max_workers` | integer | `1` | >= 1. |
| `max_queued_jobs` | integer | `8` | >= 1; reservados + activos. |
| `dimension_tolerance_mm` | number | `0.2` | Finito y >= 0. |
| `worker_python_paths` | string[] | `[]` | Se unen en `PYTHONPATH` del worker. |
| `worker_script` | string | `workers/embroidery/worker.py` | Ruta del worker; normalmente omitir. |
| `openai_api_key` | string/null | `null` | H2. Clave de OpenAI; solo aquí, nunca en la web ni en variables del navegador. No aparece en `repr`. Va junto con `openai_model`. |
| `openai_model` | string/null | `null` | H2. Modelo con visión y salida estructurada; se elige con ejemplos reales, no hay valor por defecto. |
| `openai_base_url` | string | `https://api.openai.com` | H2. Solo para pruebas o un proxy propio. |
| `analysis_timeout_s` | number | `60` | H2. Espera máxima por respuesta del proveedor; finito y > 0. |

Se requiere `service_token` o el par `basic_username`/`basic_password`. Si ambos están configurados, se aceptan Bearer y Basic, pero el desafío `WWW-Authenticate` es `Bearer`: un navegador no pide usuario y contraseña. Para usar la web con Basic, no definir `service_token`.

## Proveedores de IA (H2)

`GET /api/v1/profiles` informa como disponible solo lo configurado aquí: OpenAI si hay `openai_api_key` y `openai_model`; el modelo local (`ollama`) figura no disponible hasta que exista su adaptador. Si un proveedor falla, el trabajo termina con el código del catálogo; nunca se pasa a otro proveedor en silencio.

## Ejemplo

```json
{
  "data_root": "C:/embroidery-data",
  "profiles_path": "C:/repo/services/api/profiles.json",
  "python_executable": "C:/repo/services/api/.runtime/venv/Scripts/python.exe",
  "inkstitch_executable": "C:/InkStitch/bin/inkstitch.exe",
  "engine_version": "v3.2.2",
  "signing_key": "<secreto-de-32-bytes-o-mas>",
  "public_base_url": "http://127.0.0.1:8000",
  "service_token": "<token-privado>",
  "inkscape_executable": "C:/Program Files/Inkscape/bin/inkscape.com",
  "worker_python_paths": []
}
```

## Errores

- Campo faltante, desconocido o tipo incorrecto: `TypeError` al iniciar.
- Sin auth, `signing_key` corta, URL inválida o límites no positivos: `ValueError`.
- La configuración se lee una vez; reiniciar tras cambiarla.
