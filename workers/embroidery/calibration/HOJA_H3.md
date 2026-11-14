# Medición física H3 — hoja de trabajo

Propósito: David mide la muestra existente y registra evidencia; los resultados físicos están pendientes.

Contenido: [Identificación](#identificación), [Procedimiento](#procedimiento), [Registro](#registro), [Referencias](#referencias).

## Identificación

Completar antes de coser:

| Dato | Registro |
|---|---|
| Fecha / operador / archivo JEF / SHA256 | __________ |
| Máquina / bastidor | Janome MC550E / SQ20b; confirmar __________ |
| Tela (tipo, lote, capas, orientación) | Gabardina de uso previsto: __________ |
| Estabilizador (tipo, peso, capas) | Grueso de uso previsto: __________ |
| Hilo (marca, material, grosor) / bobina | __________ |
| Aguja (tipo, calibre, uso) / tensión | __________ |
| Velocidad | **400 puntadas/min**; confirmar __________ |
| Instrumentos / resolución / control de cero | __________ |

Usar `tests/calibration/h3/muestra_h3.jef` y registrar su hash. Su preview es digital, no una foto cosida. No sustituirlo por un JEF de Anime Socks cuya identidad física no se confirmó.

## Procedimiento

1. Registrar condiciones e instrumentos de [criterios](CRITERIOS_H3.md). Preparar la misma combinación de tela/estabilizador/hilo prevista. No cambiar densidad o compensación durante esta muestra.
2. Coser a 400 ppm; anotar roturas, paradas, tensión o intervenciones por elemento. Una fila intervenida queda identificada y no se usa como comparación limpia.
3. Medir sin planchar ni estirar, primero en bastidor. A–C: ancho en inicio/centro/final, evitando remates. D: tres lecturas de cada lado X/Y. E: repetir tres veces el largo de extremo a extremo. No son tres muestras independientes.
4. Retirar del bastidor, dejar 30 min en plano y repetir la dimensión principal. Este tiempo fijo es una convención del estudio, no una norma industrial.
5. Fotografiar pieza completa y filas, con escala milimetrada en el mismo plano. Conservar foto sin editar, CSV, condiciones y JEF identificado.

## Registro

Completar mediciones.csv: 39 filas para 31 piezas y marco; cada relleno D tiene X/Y separados, con medidas digitales propias.

- Error nominal = media real − objetivo físico; error digital = media real − dimensión JEF.
- En D: medir diez intervalos entre filas, perpendiculares a su dirección, y dividir por diez. En B comparar cobertura/fruncido entre separaciones programadas; no equiparar zigzag visible con separación nominal.
- Aplicar tolerancias de estudio y criterios visuales de [CRITERIOS_H3.md](CRITERIOS_H3.md). Resultado: candidato, rechazar o no evaluable.
- Guardar resultados en un archivo nuevo; la plantilla y el JEF originales se conservan.

## Referencias

- [Protocolo existente](../../../tests/calibration/h3/PROTOCOLO_H3.md)
- [Criterios e instrumentos](CRITERIOS_H3.md) · Plantilla
