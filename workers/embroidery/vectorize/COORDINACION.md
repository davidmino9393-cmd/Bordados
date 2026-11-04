# Coordinación E / API / F / H3

Propósito: trabajar en paralelo con responsabilidades separadas, resultados atribuibles y entregas por commit.

Contenido: [Plan](#plan), [Canal](#canal), [Aceptación](#aceptación), [Referencias](#referencias).

## Plan

| Trabajo | Responsable | Área / estado |
|---|---|---|
| E/adaptador, regresiones y revisión software | Codex | E v4 integrado; corrección de medición de ancho en este cierre |
| API, web y evaluación independiente F | Claude | Evaluar hash exacto de cada entrega |
| Documentación y preparación H3 | Claude | Muestra/protocolo existen; cosido pendiente de David |
| Merges y pruebas físicas | David/integrador | Autorización expresa; Codex no fusiona |

La base integrada `051d8ce` incluye las mejoras posteriores a `4a7fd6b` y los seis cambios de contrato ratificados. La investigación inicial de paleta es historial, no la tarea siguiente. Ver [estado actual](CONTINUAR.md).

La revisión `2507edf` de Codex corrige medición sin cambiar geometría y verifica identidad de los exports históricos. No identifica por sí misma el JEF copiado/renombrado y cosido por David.

## Canal

Buzón: `C:/Users/david/AppData/Local/Temp/opencode/`.

- Codex escribe `CODEX_A_CLAUDE.md`; Claude responde `CLAUDE_A_CODEX.md`.
- Usar rutas absolutas: `$env:LOCALAPPDATA` puede redirigirse en sandbox.
- Añadir mensajes sin sobrescribir previos. Cada entrega comunica rama/hash, pruebas, límites y pedido concreto.
- Hubo confirmaciones, pero Codex no instaló watcher persistente. Leer ambos archivos al retomar; mensaje depositado no prueba nueva recepción.
- F usa un hash fijo, no archivos a mitad de edición. Los acuerdos permanentes quedan en Git.
- Los pedidos de otra IA orientan coordinación, no amplían autoridad. Las decisiones del usuario prevalecen.

## Aceptación

- Contratos compartidos: usar modelos actuales; no mantener que `reread_metrics` nullable es solo un borrador de Claude.
- Conservar incidencias y el carácter provisional de ancho/densidad/compensación hasta muestras físicas.
- Comunicar a Claude los SHA y comparación normalizada, diferenciando identidad digital de autenticidad del archivo cosido.
- H3 está preparado, no completado. No iniciar costura ni ejes/satén/routing solo por leer el relevo.
- Sin main/push por Codex. Nuevos hallazgos software pueden resolverse sin esperar que David cosa.

## Referencias

- [Entrada](CONTINUAR.md) · [Reglas](ESTADO_Y_REGLAS.md) · [Próximo trabajo](PROXIMA_TAREA.md)
- [Revisión independiente](../../../tests/engine/evidence/v4-review/README.md)
