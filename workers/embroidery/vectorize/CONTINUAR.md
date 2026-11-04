# Continuar motor

Propósito: retomar el árbol candidato sin confundir evidencia histórica con trabajo pendiente. Fecha: 2026-11-03.

Contenido: [Base](#base), [Estado](#estado), [Próximo trabajo](#próximo-trabajo), [Referencias](#referencias).

## Base

La rama codex/motor ya contiene main `68d7ecdfef23f34e5becd9e5ccb0be9de65244bf` mediante el merge hacia motor autorizado por David en ronda B. Main permanece intacto. El integrador humano decide cualquier fusión a main. No crear worktrees ni hacer push.

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

Ronda B verificada: merge autorizado 3e618c0; control F rojo por dos literales; renombre neutral fcf7468 y F verde (8 checks 14/14), sin cambiar parámetros ni checker. Límite actual 20 MP tras medición y autorización de David; bytes 10 MiB y guarda 500000 aristas intactos. La referencia ampliada a 20 MP se rechaza por complejidad de forma controlada.
