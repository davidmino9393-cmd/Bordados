# Próximo trabajo tras revisar E v4

Propósito: continuar con evidencia nueva sin repetir mejoras ya integradas ni iniciar la costura que David postergó.

Contenido: [Base](#base), [Agents & Skills](#agents--skills), [Continuación](#continuación), [Aceptación](#aceptación), [Referencias](#referencias).

## Base

Base integrada `051d8ce`, E `e1-pixel-mask-v4`. Cuantización `kmeans=3`, mediana de grupo, cobertura de borde y medición de ancho ya existen. La revisión `2507edf` corrige bordes, kernels pares, igualdad física por coma flotante y filtros desmesurados de `thin_features.py`; no modifica geometría ni el supuesto provisional de 0,4 mm.

Mantener firma `vectorize()` y campos `VectorizeResult`. Imagen → JEF no está habilitado por esta revisión.

## Agents & Skills

| Orden futuro | Responsable | Skills / área |
|---|---|---|
| 1 | `tester` | `core`, `test`; reproducir hallazgo y prueba mínima |
| 2 | `backend-developer` | `core`; E/adaptador y evidencia |
| 3 | `code-reviewer` | `core`, `code-review`; revisión independiente |
| 4 | Claude | F/API/web, por hash fijo |

Aplicar la cadena al implementar; leer el plan no inicia H3. Orquesta el principal; delegados no crean agentes. Correcciones E ya autorizadas no necesitan otra aprobación.

## Continuación

1. Verificar último commit, buzón y [cierre independiente](../../../tests/engine/evidence/v4-review/README.md). No reabrir la promoción de paleta ya hecha.
2. Si llega un fallo software concreto, reproducirlo y corregirlo dentro de E. Medir geometría/máscara, color, unidades, recursos y cancelación según el cambio; conservar incidencias. No inventar calibración ni umbrales de aprobación.
3. Si David aporta el archivo JEF realmente utilizado, comparar SHA/comandos con [identidades verificadas](../../../tests/engine/evidence/v4-review/jef-identity.json). Registrar condiciones reales; no deducir la muestra cosida de un nombre o preview.
4. Cuando David retome H3, coordinar muestra, tela, estabilizador, hilo, aguja, máquina/bastidor y mediciones mediante el protocolo preparado. Antes de eso, 0,4 mm, densidad y compensación siguen provisionales.
5. Futuras técnicas, ejes, satén, routing y regeneración por tamaño requieren su trabajo y validación propios. No incluirlos como terminados por existir un JEF de muestra.

## Aceptación

- Revisión software puede avanzar con evidencia nueva; el cosido pendiente no bloquea todo el proyecto.
- Sin borrado/engrosado silencioso de zonas finas. No ocultar pérdidas de fondo/color ni advertencias para aprobar.
- Igualdad digital no demuestra resultado físico. No afirmar qué archivo cosió David sin verificarlo.
- Nueva entrega: pruebas pertinentes, revisión independiente, commit/hash y F de Claude. Cambios de contrato o calibración deben quedar explícitos.

## Referencias

- [Inicio](CONTINUAR.md) · [Comandos](REPRODUCIR.md)
- [Protocolo H3](../../../tests/calibration/h3/PROTOCOLO_H3.md)
