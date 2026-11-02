# Entrega E1 para Claude

Propósito: conectar E sin cambiar contratos ni confundir geometría con puntadas validadas.

Contenido: [Responsabilidades](#responsabilidades), [Conexión](#conexión), [Pendientes](#pendientes), [Referencias](#referencias).

## Responsabilidades

| Área | Responsable |
|---|---|
| `workers/embroidery/vectorize/**`, adaptador y pruebas E | Codex |
| `services/api`, `runner.py`, web, manifiesto, evaluación F | Claude |
| Traslado entre ramas, merges a main | David |

No se modificaron API, contratos, worker anterior ni regresiones existentes.

## Conexión

1. Importar `vectorize` desde el directorio del worker y pasar bytes originales, MIME, asset, análisis normalizado y ajustes tipados. `analysis=None` sirve para uso independiente sin proveedor; no significa que el análisis H2 esté aprobado.
2. Ejecutar en el trabajo background; pasar el evento de cancelación. E no crea archivos ni cambia estados.
3. Persistir documento, SVG editable y evidencia con hashes propios del job. `.issues` son modelos `Issue`; `.duration_ms` es la medición real.
4. `source_region_id` queda `None`: no existe correspondencia verificada entre cajas estimadas y objetos. Las anotaciones de texto/regiones están en `.evidence["annotations"]`.
5. Manejar `VectorizeFailure.issue` respetando su severidad. Una incidencia de geometría de nivel revisión no alcanza para declarar `failed`, que exige una bloqueante; decidir el estado conforme al contrato y conservar el motivo original. Cancelación devuelve `JOB_CANCELLED`.
6. Mantener visibles cambios RGB y supuestos del fondo. `verified_mask` verifica el contorno de la máscara segmentada, no la interpretación del diseño.
7. H3 debe validar parámetros antes de llamar `to_inkstitch_svg(result, h3_document=...)`. Solo relleno; mismo documento/geometría. El documento explícito es una declaración del llamador, no una certificación automática. E1 no genera JEF ni habilita `ready_for_sewout`.

## Pendientes

- Fondo blanco opaco inferido por borde; puede eliminar blancos intencionales. Transparencia parcial binarizada. Ambos se advierten.
- F sobre `4a7fd6b` confirmó pérdidas de color. La investigación `2fbb6ca` no cambia E; fidelidad semántica y legibilidad siguen pendientes.
- Recorte fraccional, orientación EXIF no normalizada y complejidad excesiva: incidencias controladas.
- SVG preparados siguen su recorrido existente. Ejes centrales, satén y casos difíciles quedan fuera de esta tanda.
- Cancelación cooperativa: Pillow nativo se consulta antes/después, no se interrumpe internamente.

## Referencias

- [Estado y arranque del próximo chat](CONTINUAR.md)
- [Interfaz](README.md)
- [Evidencia y reproducción](../../../tests/engine/evidence/h2-e1/README.md)
