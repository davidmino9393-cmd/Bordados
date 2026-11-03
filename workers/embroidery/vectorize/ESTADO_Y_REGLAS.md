# Estado y reglas del relevo

Propósito: conservar autoridad y distinguir revisión software, integridad digital y aprobación física.

Contenido: [Propiedad](#propiedad), [Invariantes](#invariantes), [Contratos e integración](#contratos-e-integración), [Entrega](#entrega), [Referencias](#referencias).

## Propiedad

| Área | Responsable |
|---|---|
| E, adaptador y pruebas del motor | Codex |
| API, web, e2e, F, manifiesto y documentación H3 | Claude |
| Merges, traslados y muestras físicas | David/integrador humano |

- Solo `codex/motor`. Git habitual: `status`, `diff`, `log`, `add`, `commit`. Codex no ejecuta merge, push, checkout ni worktree add.
- Correcciones internas E y commits atómicos autorizados; no pedirlos de nuevo. La sincronización a `051d8ce` la hizo Claude con permiso de David; no es permiso general para futuras fusiones.
- `4018d97` y los fixtures ya están integrados. No repetir cherry-pick.
- Leer `C:\dev\wt-web`/main está permitido; no escribir en otro worktree. Conservar los scripts originales Anime Socks sin ejecutar/importar ni reescribir: `digitalizar.py` no es generalizable.
- Rutas configurables. Nuevas dependencias, políticas o contratos requieren la decisión correspondiente; esta revisión no los cambia.

## Invariantes

- `ready_for_sewout` digital ≠ `approved` físico. E no asigna estados; `approved` no pertenece al job.
- E produce geometría desde píxeles; bboxes IA orientan, no sustituyen máscaras. Texto es anotación, no fuente reemplazada.
- Parámetros provisionales: `DENSITY_REVIEW_REQUIRED`, decisión por objeto y bandera H3. El supuesto de 0,4 mm se mide/avisa, no se transforma en calibración por documentación manual.
- Revisión sola no justifica `failed`: exige bloqueante. Cancelación: `JOB_CANCELLED`. No ocultar avisos de color, fondo o satén.
- JEF desde SVG preparado funciona; imagen → JEF y selección de técnicas/routing siguen pendientes de H3. No declarar la app completa.
- Hash y comandos iguales no identifican el archivo realmente cosido. Requiere el original usado y sus condiciones; no extender aprobación física a variantes.

## Contratos e integración

La base `051d8ce` incluye los seis cambios ratificados y modelos actuales de `packages/contracts`; `reread_metrics` nullable ya no es una propuesta aislada de Claude. `ready_for_sewout` conserva exigencia de JEF y relectura. No aplicar supuestos viejos del relevo de `4a7fd6b`.

## Entrega

Cerrar con: Hito/tarea; Versión de contratos; Archivos y rama; Entradas reales; Datos simulados; Comprobaciones/resultados; Limitaciones/bloqueos; Cambios necesitados de la otra IA.

## Referencias

- [Inicio](CONTINUAR.md) · [Coordinación](COORDINACION.md)
