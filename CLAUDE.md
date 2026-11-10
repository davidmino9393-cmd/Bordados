# CLAUDE.md

Proyecto **bordados**: app web que convierte un logo en un bordado (JEF) con el motor Ink/Stitch.

## Repos y reparto

- `C:\dev\bordados` — `main`. Los merges los autoriza y ejecuta David.
- `C:\dev\wt-web` — ramas `claude/*`; áreas `services/api` y `apps/web`. Claude es el desarrollador principal (N3/N4).
- `C:\dev\wt-motor` — ramas `codex/*`; áreas `workers/embroidery` y `packages/contracts`. Codex es el secundario (N1/N2).
- `C:\dev\wt-opencode` — auditoría independiente de OpenCode.

No editar el árbol de otro agente. No commitear, mergear ni cambiar de rama sin autorización.

## Comandos

- Git: usar siempre `C:\Program Files\Git\cmd\git.exe`; el `git` suelto lo intercepta RTK.
- Motor: desde `tests/engine`, `python -m unittest -s . -p 'test_*.py'` con `PYTHONPATH` que incluya `services/api/.deps`.
- Web: `npm run build` y `npx vitest run` en `apps/web`.

## Presupuesto de contexto

- Tope de salida por comando: 2 KB. Usar `Select-Object -First/-Last`, `--stat`, `-q`, `tail`.
- Prohibido recursar `node_modules`, `.tmp`, `.git` o listar árboles completos.
- Estado del equipo: MCP `estado_proyecto` (≈1 KB) en vez de varios comandos de git.
- Leer con `grep -n` o `limit`; no volcar archivos enteros.
- Investigación amplia: en subagente; vuelve solo el resumen.
- Cerrar la sesión al terminar un tema.

## Entrega

- Commits en inglés, conventional commits, sin `Co-Authored-By`.
- Reportar hash y número medido, no impresiones.
- Sin calibración ni `ready_for_sewout`: el estado honesto es `needs_review`.
