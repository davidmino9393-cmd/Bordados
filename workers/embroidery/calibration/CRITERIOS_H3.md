# Criterios operativos del estudio H3

Propósito: tolerancias **propuestas para esta muestra**, sin afirmar calibración ni cumplimiento de una norma industrial.

Contenido: [Instrumentos](#instrumentos), [Criterios](#criterios), [Decisión](#decisión), [Referencias](#referencias).

## Instrumentos

- Calibre digital, resolución 0,01 mm; registrar exactitud declarada. Comprobar cero y una longitud conocida. Para filas A–D, exactitud declarada de 0,1 mm o mejor; cerrar suavemente sin comprimir hilo ni estirar tela.
- Regla rígida milimetrada para marco/líneas: incertidumbre estimada ≤0,5 mm. Para marco de 150 mm puede usarse calibre de alcance suficiente. Registrar instrumento por fila.
- Lupa 5× o macro con escala coplanar para cobertura, bordes e intervalos. Diez intervalos reducen el error relativo de lectura; no estimar décimas desde una regla insuficiente.
- Si falta instrumento o incertidumbre adecuada: **no evaluable**, no aprobar por apariencia.

## Criterios

| Fila / objetivo | Tolerancia del estudio |
|---|---|
| A: ancho nominal de cada satin | ±max(0,2 mm; 5% del nominal) |
| B/C: ancho físico deseado 3 mm | ±0,2 mm |
| D: relleno, lado deseado 12 mm | ±0,5 mm por eje |
| E: largo deseado 25 mm | ±0,5 mm; registrar grosor, continuidad y legibilidad |
| Marco: 140×150 mm | ±1 mm por eje |
| D: separación de filas vs. programada | ±max(0,05 mm; 10%), midiendo 10 intervalos perpendiculares |

Registrar incertidumbre estimada U (instrumento, bordes y repetición), no solo resolución. Con error e y tolerancia T: aceptar lectura si |e|+U≤T; rechazar si |e|−U>T; resto no evaluable. Las tres lecturas y la medición fuera del bastidor deben evaluarse; registrar dispersión.

Rechazar como candidato una pieza con rotura, bucle suelto, hueco de cobertura no previsto, fruncido persistente, borde irregular o pérdida de continuidad. El pespunte E no exige cobertura de relleno. Registrar cantidad y ubicación; la foto no sustituye la medida.

## Decisión

El objetivo físico y la dimensión digital son distintos: el JEF puede incluir compensación. Comparar contra ambos; no ajustar el nominal para hacer pasar la muestra. En C, comparar el error respecto de 3 mm entre compensaciones, sin extrapolar a otra tela.

El menor A aceptable es candidato de satin para estas condiciones; no calibra automáticamente el umbral genérico de 0,4 mm de E1 (la fila A empieza en 0,6 mm). Una sola pieza no demuestra repetibilidad entre muestras.

Conservar perfiles como propuestos hasta revisar evidencia y condiciones. `ready_for_sewout` exige además las comprobaciones digitales de archivo, dimensiones, bastidor, geometría, satin y recorrido; coser o aprobar físicamente no las reemplaza.

## Referencias

- [Hoja y procedimiento](HOJA_H3.md)
- [Planilla digital original](../../../tests/calibration/h3/planilla_h3.csv)
