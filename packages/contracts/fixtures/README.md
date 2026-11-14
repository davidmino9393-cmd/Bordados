# Fixtures compartidos v0.1

Propósito: ejemplos JSON para mocks y validación mínima. **Todos son simulados**, incluidos artefactos, hashes, tiempos y muestra física. v0.1 B2 candidato a congelar, pendiente de revisión humana.

Contenido: [Casos](#casos), [copia](#copia), [relacionados](#relacionados).

## Casos

| Archivo | Modelo de payload | Representa |
|---|---|---|
| generation-from-svg.json | JobCreate | Request para SVG ya preparado, sin análisis IA |
| valid-result.json | JobResponse | Respuesta lista digitalmente con manifest, métricas y checks simulados |
| needs-review.json | JobResponse | Revisión satin localizada en object_mock_satin |
| failure.json | JobResponse | Fallo controlado de exportación con código/diagnóstico |
| cancellation.json | JobResponse | Cancelación ya completada; no solo solicitud |
| physical-sewout.json | SewoutRecord | Request de muestra física aprobada, también ficticia |

## Copia

- Envelope: `schema_version: "0.1"`, `contract_revision: "B2"`, `simulated: true`, `case`, `model`, `direction`, `endpoint`, `payload`.
- La web usa estos JSON desde `apps/web/mocks/`. No necesita importar Python ni el paquete backend.
- Usar `payload` como cuerpo request/response del mock. El envelope identifica datos de prueba y **no** se envía a la API real.
- Mantener en web una señal visible de modo simulado; no borrar procedencia al mostrar mocks. El resultado incluye además provenance.simulated=true.
- IDs `*_mock_*`, URLs `example.invalid`, hashes de relleno y tamaños no identifican archivos existentes. Los conteos del caso válido ilustran el inventario histórico, no una exportación realizada por este contrato.
- Al actualizar versión, copiar el caso completo y comprobar modelo, estado y unidades. La integración real espera revisión humana de v0.1 y H1.

## Relacionados

[Modelos](../README.md), [mapa B2](../B2-web-mapping.md), [protocolo](../B2-protocol.md), [tests](../../../tests/engine/test_contracts.py).
