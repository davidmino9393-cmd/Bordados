# AGENTS.md — bordados

## Proyecto

Pipeline de bordado: imagen o SVG -> geometria vectorizada -> JEF.
`services/api` expone la API; `apps/web` permite preparar y revisar el trabajo.
`workers/embroidery` convierte y verifica el bordado con Ink/Stitch.
`packages/contracts` define los datos compartidos entre las areas.

## Estructura

- `services/api`: servicio HTTP FastAPI, persistencia y ejecucion de trabajos.
- `apps/web`: interfaz TypeScript + React y pruebas Vitest.
- `workers/embroidery`: motor, vectorizado, exportacion JEF y relectura.
- `packages/contracts`: modelos Pydantic, estados, OpenAPI y catalogos.
- `tests/engine`: pruebas del motor, contratos, API y persistencia.
- `tests/e2e`: pruebas del recorrido web con Playwright.
- `scripts`: arranque de la web.
- `docs`: guia de bordado con Ink/Stitch.

## Pruebas

Los comandos siguientes estan escritos en los README o documentos del area.
API y motor comparten pruebas bajo `tests/engine`.
Ejecutar desde la raiz, con las dependencias del area disponibles:

```powershell
python -m unittest discover -s tests/engine -p "test_*.py"
```

Regresiones del motor, desde la raiz:

```powershell
python -m unittest tests/engine/test_regressions.py -v
```

Web, desde la raiz; el script ejecuta Vitest:

```bash
cd apps/web && npm test
```

## Base de datos

- Desarrollo: PostgreSQL en Docker; puerto local `127.0.0.1:5433`, contenedor `5432`.
- La API usa PostgreSQL con `database_url`; sin ella usa SQLite.
- Las pruebas buscan `EMBROIDERY_TEST_DATABASE_URL` o `services/api/.runtime/postgres-dev.json`.
- Si PostgreSQL no responde, incluso con Docker apagado, esas pruebas se omiten.
- Revisar las omisiones: un resultado verde sin esas pruebas no verifica PostgreSQL.

## Medicion

- No aceptar un cambio sin numero medido o hash que lo respalde.
- Reportar el alcance de la comprobacion junto con el resultado.
- Exportar y releer un JEF no demuestra que este listo para bordar.
- Mantener `needs_review`; no marcar `ready_for_sewout` ni calibracion.

## Autoridad

- David autoriza y ejecuta los merges a main.
- Preguntar antes de cambiar configuracion de produccion.
- Trabajar en el arbol y la rama asignados; no editar el arbol de otro agente.

## Convenciones

- Motor: el README declara Python 3.12; seguir esa version documentada.
- Web: TypeScript + React; conservar los patrones existentes del area.
- Pruebas de API y motor: unittest; pruebas web: Vitest.
- Para identificadores y comentarios nuevos, usar espanol sin acentos.
- Cambiar solo lo necesario para la tarea y conservar contratos compartidos.

## Que no hacer

- No recursar `node_modules`, `.git` ni `.tmp`, ni listar arboles completos.
- No commitear artefactos generados de trabajos ni dependencias locales.
- No commitear `__pycache__`, bytecode ni configuracion privada de ejecucion.
- No confundir evidencia guardada con una nueva ejecucion comprobada.

Fuentes: `CLAUDE.md`; `services/api/README.md`; `services/api/docs/CONFIG.md`; `workers/embroidery/README.md`; `workers/embroidery/vectorize/README.md`; `packages/contracts/README.md`; `apps/web/package.json`; `apps/web/docs/H0-05-recorrido-web.md`; `tests/engine/test_regressions.py`; `tests/engine/test_store_backends.py`; `.gitignore`; `services/api/.gitignore`; `workers/embroidery/.gitignore`; reglas de autoridad de la version anterior de `AGENTS.md`.
