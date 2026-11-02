# Estado y reglas del relevo

Propósito: conservar límites de autoridad y separar lo implementado de lo reportado por otra IA.

Contenido: [Propiedad](#propiedad), [Invariantes](#invariantes), [Estado externo](#estado-externo), [Entrega](#entrega), [Referencias](#referencias).

## Propiedad

| Área | Responsable |
|---|---|
| `workers/embroidery/vectorize/**`, adaptador y pruebas E en `tests/engine` | Codex |
| API, web, e2e, `tests/h2_eval`, manifiesto | Claude |
| Traslados y merges | David |

- Solo `codex/motor`. Git: `status`, `diff`, `log`, `add`, `commit`. Sin merge, push, checkout ni worktree add.
- Correcciones internas E y commits atómicos ya autorizados; no volver a pedirlos.
- `da5e1a1` trasladado con permiso como `094956a`. `4018d97` pendiente aquí: Claude refiere permiso en otro chat. No darlo por instrucción directa; el PNG existe y no bloquea E.
- Leer `C:\dev\wt-web` está permitido; no escribir allí. Contratos congelados locales: solo lectura.
- Scripts originales de las dos carpetas Anime Socks: conservar, no ejecutar/importar ni reescribir. `digitalizar.py` no es generalizable.
- Rutas configurables; sin rutas de esta máquina en producción. No dependencias nuevas ni política API sin decisión correspondiente. La siguiente prueba de paleta no necesita dependencias nuevas.

## Invariantes

- `ready_for_sewout` digital ≠ `approved` físico; `approved` no es estado del job. E no asigna estados.
- E produce `verified_mask`: contorno exacto de máscara segmentada, no garantía semántica. Bboxes IA solo anotan; texto no sustituye fuentes.
- Todo resultado conserva `DENSITY_REVIEW_REQUIRED`, decisión por objeto y `evidence.h3_validation_required`. H3 no está implementado; no JEF desde imagen.
- `VectorizeFailure.issue` conserva catálogo/severidad. Revisión sola no justifica `failed`; este requiere bloqueante. Cancelación: `JOB_CANCELLED`.
- PNG/JPEG hasta 32 MiB y 4 Mpx; SVG preparado sigue el worker previo. Crop fraccional y EXIF no normalizado dan incidencias controladas.
- No ocultar pérdidas de color/fondo ni borrar detalles para superar límites. Sin constantes por logo.

## Estado externo

Git al preparar relevo: `main` en `af21ed3`; `claude/web` en `7459bb5`. Verificar de nuevo al continuar.

Según Claude: integró E hasta `4a7fd6b` en `claude/web` (merge `19e418e`, autorizado por David). F pasó controles estructurales; calidad de color pendiente. No ejecutamos F localmente.

Claude hizo `ArtifactManifest.reread_metrics` opcional para revisión sin JEF, solo en su rama. Requiere revisión/versionado humano; v0.1 local no acepta ese supuesto.

## Entrega

Terminar siempre con: Hito/tarea; Versión de contratos utilizada; Archivos y rama; Qué funciona con entradas reales; Qué utiliza datos simulados; Comprobaciones y resultado; Limitaciones o bloqueos; Cambios que necesitás de la otra IA.

## Referencias

- [Inicio](CONTINUAR.md) · [Buzón y reparto](COORDINACION.md)
