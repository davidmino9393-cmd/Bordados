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
| `raster_digitizing` | boolean | `true` | Una imagen termina en un JEF generado con los parámetros de referencia de Anime Socks (no calibrados) y queda en `needs_review`. `false`: el trabajo se queda en la geometría de E1, sin JEF. |
| `digitizing_timeout_s` | number | `600` | Plazo del worker para generar el JEF de una imagen; finito y > 0. Ink/Stitch calcula el plan dos veces (diagnóstico y exportación): Anime Socks tarda unos 2 min. |
| `database_url` | string/null | `null` | Dónde se guardan proyectos, archivos, revisiones, trabajos y muestras (los datos, no los archivos). Sin ella, SQLite en `data_root/metadata.sqlite3`. Con una URL `postgresql://usuario:clave@host:puerto/base`, PostgreSQL. Es un secreto: no aparece en `repr`. Ver [Guardar en PostgreSQL](#guardar-en-postgresql). |
| `openai_api_key` | string/null | `null` | H2. Clave de OpenAI; solo aquí, nunca en la web ni en variables del navegador. No aparece en `repr`. Va junto con `openai_model`. |
| `openai_model` | string/null | `null` | H2. Modelo con visión y salida estructurada; se elige con ejemplos reales, no hay valor por defecto. |
| `openai_base_url` | string | `https://api.openai.com` | H2. Solo para pruebas o un proxy propio. |
| `ollama_model` | string/null | `null` | H2. Modelo de visión local de Ollama con salida estructurada (debe aceptar imágenes: un modelo solo de código no sirve). Sin él, `ollama` figura no disponible. No hay valor por defecto. |
| `ollama_base_url` | string | `http://127.0.0.1:11434` | H2. Origen HTTP(S) del servidor de Ollama; puede ser otra máquina de la red. |
| `ollama_timeout_s` | number | `120` | H2. Espera máxima por respuesta del modelo local; finito y > 0. Un modelo local es más lento que uno en la nube. |
| `analysis_timeout_s` | number | `60` | H2. Espera máxima por respuesta del proveedor; finito y > 0. |

`public_base_url` es el origen de las URLs de descarga. En Windows, con `localhost` y el servidor escuchando solo en `127.0.0.1`, un cliente que no sea el navegador (Python, curl) espera ~2 s por cada descarga (intenta primero IPv6); en desarrollo conviene `http://127.0.0.1:8000`. Medido con el SVG de Anime Socks: 2,1 s con `localhost`, 6 ms con `127.0.0.1`.

Se requiere `service_token` o el par `basic_username`/`basic_password`. Si ambos están configurados, se aceptan Bearer y Basic, pero el desafío `WWW-Authenticate` es `Bearer`: un navegador no pide usuario y contraseña. Para usar la web con Basic, no definir `service_token`.

## Guardar en PostgreSQL

`database_url` pasa los datos de SQLite a PostgreSQL; la API funciona igual sobre cualquiera de los dos. Las tablas (`resources`, `idempotency`) se crean solas al iniciar. Lo que **no** va a la base son los archivos (originales, JEF, vistas previas): siguen en `data_root`, y las rutas guardadas valen mientras esa carpeta no cambie de lugar. Tiene que estar en un disco que no se borre (no dentro de una carpeta temporal ni de un worktree) y respaldarse junto con la base.

| Paso | Qué hacer |
|---|---|
| 1 | Una base PostgreSQL vacía y un usuario con permiso sobre ella. Para desarrollo: `docker run -d --name bordados-postgres -e POSTGRES_USER=bordados -e POSTGRES_PASSWORD=<clave> -e POSTGRES_DB=bordados -p 127.0.0.1:5433:5432 -v bordados_pgdata:/var/lib/postgresql postgres:18` |
| 2 | Poner `"database_url": "postgresql://bordados:<clave>@127.0.0.1:5433/bordados"` en la configuración privada (una base alojada, como Supabase, suele pedir `?sslmode=require`) |
| 3 | Con la API detenida, pasar lo que ya hay: `python services/api/migrate_sqlite_to_postgres.py --config <la configuración privada> --dry-run` y, si cuenta lo esperado, sin `--dry-run`. Copia filas en una sola transacción, no toca el SQLite y se niega a escribir en una base que ya tiene datos |
| 4 | Reiniciar la API |

Una sola instancia de la API por base es lo probado; si se corta la conexión entre dos pedidos, se reconecta sola, y si se corta en medio de una escritura esa escritura se pierde y el pedido falla (nunca queda a medias). Pruebas: `tests/engine/test_store_backends.py` (las mismas reglas sobre SQLite y PostgreSQL), `test_migrate_sqlite_to_postgres.py` y toda la suite de la API con `ApiTestsOnPostgres`; usan la base de `EMBROIDERY_TEST_DATABASE_URL` o la de `services/api/.runtime/postgres-dev.json` y se omiten si no hay ninguna.

## Proveedores de IA (H2)

`GET /api/v1/profiles` informa como disponible solo lo configurado aquí: OpenAI si hay `openai_api_key` y `openai_model`; el modelo local (`ollama`) si hay `ollama_model`, **sondeado en vivo** en cada `GET /profiles` (se recuerda 10 s): disponible solo si el servidor responde y el modelo está instalado; si no, `available: false` con el motivo. La validación de un pedido solo exige que esté configurado. Si el modelo local falla durante un trabajo, termina con `LOCAL_MODEL_UNAVAILABLE` (servidor caído, modelo no instalado o sin respuesta a tiempo), `ANALYSIS_INCOMPLETE` (respuesta cortada) o `ANALYSIS_SCHEMA_INVALID`. Si un proveedor falla, el trabajo termina con el código del catálogo; nunca se pasa a otro proveedor en silencio.

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
