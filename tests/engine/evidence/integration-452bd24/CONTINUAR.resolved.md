# Continuar motor integrado (preparación, sin merge a main)

Propósito: retomar el árbol candidato sin confundir evidencia histórica con trabajo pendiente. Fecha: 2026-11-03.

Contenido: [Base](#base), [Estado](#estado), [Próximo trabajo](#próximo-trabajo), [Referencias](#referencias).

## Base

Árbol temporal preparado desde main `68d7ecdfef23f34e5becd9e5ccb0be9de65244bf` y motor `452bd249d765c53d6d4e7155259cff2e47913f73`. No es un commit de merge ni autorización para fusionar. Codex trabaja en codex/motor; el integrador humano decide main. No crear worktrees ni hacer push.

Resolución de este documento: gana la estructura y relevo actualizado de Codex (1ebfb40), conservando la corrección de finos 2507edf. Se incorporan los hechos posteriores de main: imagen→JEF de referencia, cancelación y variantes SVG corregidas. Se descartan las afirmaciones históricas de que kmeans sigue experimental o de que el motor continúa idéntico a 4a7fd6b.

## Estado

- E1 v4: paleta refinada, color mediano, cobertura y medición de finos con exterior cero/kernel par. No borra ni engrosa para aprobar; 0,4 mm sigue provisional.
- Imagen→JEF funciona con parámetros de referencia y avisos; termina needs_review. GO independiente 014e368 y corrección SVG 29f73a8+25370ff. Nunca equivale a calibración física ni ready_for_sewout.
- Helper image_input.py: PNG/JPEG, 10 MiB/4 Mpx, EXIF visual normalizado y PNG de análisis sin pérdida. Test antes huérfano ya está versionado y pasa.
- Consumo API del helper todavía pendiente de Claude: límites del catálogo, dimensiones visuales de SourceAsset y PNG orientado para proveedor. No afirmar que esté conectado por existir el helper.
- Evidencias de auditoría independent-review/ son artefactos locales deliberados; los JEF y capturas no se incluyen en el commit del helper.

## Próximo trabajo

Claude mantiene API/web/F. Codex mantiene E/adaptador/pruebas. Correcciones de revisiones van después de variantes. La integración real de este árbol y cualquier calibración requieren su validación propia. La muestra H3 preparada se mide con David; coser por sí solo no habilita readiness digital.

## Referencias

- [Entrada orientada](IMAGE_INPUT.md) · [Reglas](ESTADO_Y_REGLAS.md) · [Coordinación](COORDINACION.md)
- [Protocolo H3](../../../tests/calibration/h3/PROTOCOLO_H3.md)
