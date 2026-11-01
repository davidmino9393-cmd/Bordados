# Anime Socks — digitalización para prueba en gabardina

Fecha: 12 de octubre de 2026. Referencia: `trabajo/Referencia.png`, 1122 × 1402 px.

**Estado: SVG editables, plan generado con Ink/Stitch y dos JEF exportados y releídos. Preparado para una prueba física en un retazo equivalente al bolso. La respuesta de la tela y de la máquina todavía no se ha medido.**

## Entregables y dimensiones

- `Anime_Socks_Vector.svg`: contornos originales del texto reconstruidos en Bézier; pétalos, hojas, nervios, ramas, capullos y corazones separados. Incluye una capa de círculo opcional oculta.
- `Anime_Socks_InkStitch.svg`: versión principal sin círculo, con parámetros editables y orden de bordado optimizado.
- `Anime_Socks_Optimizado.jef`: 150.0 × 142.8 mm.
- `Anime_Socks_Con_Circulo.jef`: 150.0 × 142.8 mm; contorno circular simple, sin relleno circular.
- `Anime_Socks_Preview.png`: representación de las coordenadas releídas del JEF principal con los tonos de hilo propuestos. No es una fotografía de bordado.
- `Anime_Socks_Informe.md`: este informe.

También se incluyen un reproductor local de órdenes JEF (`Anime_Socks_Simulacion.html`), la referencia, el SVG de la variante circular, el plan de puntadas, la primera secuencia sin optimizar, auditorías y scripts de reconstrucción/exportación.

La medida de 150 mm corresponde al **recorrido de puntadas final**, cuantizado en décimas de milímetro por JEF. La página SVG incluye el pequeño margen necesario para la compensación; no se debe confundir su ancho de página con el ancho del bordado.

## Paleta y orden de hilos

| Bloque | Hilo físico propuesto | Color de trabajo |
|---|---|---|
| 1 | Malva grisáceo | `#967E88` |
| 2 | Rosa pálido | `#EDB3B5` |
| 3 | Rosa viejo más oscuro | `#BF7F85` |

El JEF guarda una paleta Janome limitada. El exportador aproximó los tonos a Salmon 256, Beige Gray 223 y Umber 237. **Elegir los hilos físicos por los tonos de la referencia y la tabla anterior; esos nombres de catálogo no son una recomendación de comprar hilo beige o marrón.** La pantalla de la máquina puede mostrar matices diferentes del SVG. El archivo tiene tres bloques y dos cambios de hilo.

## Técnicas y parámetros efectivos

| Zona | Técnica | Parámetros |
|---|---|---|
| Anime | Columnas satin de ancho variable; triple running en terminales demasiado finos | Satin 0,43 mm; compensación 0,20 mm; center walk solo donde el ancho lo justifica; sin contour ni zigzag underlay |
| SOCKS | Satin estrecho, letras espaciadas como en la imagen | Sin underlay adicional; separación 0,43 mm; revisar definición de los trazos angostos en la prueba |
| Flores | Contornos running y relleno abierto por pétalo | Relleno 0,85 mm, sin underlay; longitud máxima de relleno 2,5 mm; contorno 2,1 mm |
| Hojas | Relleno abierto, contorno y nervio running | Relleno 0,95 mm, sin underlay; running 2,1–2,3 mm |
| Ramas | Running triple | Longitud 2,3 mm |
| Capullos | Relleno abierto, contorno y detalle central | Separación 0,75 mm; running 2,1–2,3 mm |
| Cálices y corazones | Relleno pequeño | Separación 0,45–0,50 mm, sin underlay pesado |
| Círculo | Running simple | Longitud 2,5 mm; sin relleno de fondo |

La apertura de los rellenos florales es intencional: deja ver la gabardina y evita intentar reproducir la transparencia fotográfica con una cobertura densa. Se conservaron diez estambres principales por flor; los pequeños puntos decorativos y las venas fotográficas más tenues se simplificaron para mantener centros livianos. Las flores se reconstruyeron manualmente y son una adaptación para bordado, no una reproducción de sus degradados.

La caligrafía se extrajo de la referencia; no se reemplazó por una fuente parecida. Las columnas están separadas por letras/tramos y usan **dos curvas con igual número de nodos correspondientes**. Se eliminaron guías transversales inválidas que producían deformaciones del lazo de la A. El método de nodos es una técnica documentada de Ink/Stitch.

## Optimización y comparación medida

La secuencia inicial utiliza las mismas geometrías finales en el orden de construcción, intercalando repetidamente los tres tonos. Sus 36 entradas de paleta son bloques repetidos, no 36 colores físicos distintos. La optimizada agrupa los tres tonos, aproxima objetos consecutivos, respeta relleno antes de contorno en hojas y centros después de pétalos, y elimina cortes entre objetos cuya separación prevista es de hasta 2 mm.

| Métrica | Inicial | Optimizado | Con círculo |
|---|---:|---:|---:|
| Puntadas de aguja | 7248 | 6789 | 6966 |
| Saltos tras decodificar cortes | 196 | 112 | 112 |
| Cortes explícitos codificados | 109 | 53 | 54 |
| Cambios de color | 35 | 2 | 2 |
| Bloques de hilo | 36 | 3 | 3 |
| Recorrido de saltos, mm | 1696.0 | 1107.7 | 1111.0 |

Respecto de esa secuencia inicial: 6.3 % menos puntadas, 42.9 % menos comandos de salto y 51.4 % menos cortes. Se acortaron conexiones de n–i, i–m y m–e que duplicaban cobertura sobre el siguiente trazo. Se interrumpió el satin del travesaño bajo la columna ancha de la A para reducir superposición.

Un salto largo puede ocupar varios comandos JEF: el número de comandos no equivale al número de desplazamientos físicos. Los cortes se codifican como tres saltos de desplazamiento cero. La auditoría los interpreta explícitamente, con la inferencia por distancia desactivada. Su ejecución física depende del ajuste de corte de la Janome; comprobarlo al comenzar la prueba.

## Simulación y validación

Se generó el recorrido completo con `stitch_plan_preview` de Ink/Stitch. Se revisó visualmente el plan y luego una imagen independiente dibujada desde el JEF releído, lo que permitió detectar y corregir una deformación de satin que no debía aceptarse. El reproductor local usa todas las órdenes del JEF final y permite ver saltos y avance; no representa tensión, velocidad mecánica o tiraje de la tela.

Comprobaciones realizadas en cada JEF:

- Tabla de colores, desplazamiento inicial y número de registros coherentes con la longitud del archivo.
- Lectura de todos los comandos binarios hasta un único marcador final; sin comandos desconocidos ni datos después del fin.
- Coordenadas finitas, archivo centrado y dimensiones medidas en el recorrido real.
- Cabecera de bastidor JEF con código 4, correspondiente a 200 × 200 mm.
- Relectura con pyembroidery y recuento de puntadas, saltos, cortes y cambios de hilo.
- Puntada máxima principal: 4.87 mm. Las puntadas más cortas incluyen amarres y discretización de curvas; no se eliminaron indiscriminadamente para bajar el contador.

La herramienta Troubleshoot ya no informa cruces de bordes ni guías que no intersectan las columnas. Conserva 14 avisos «Satin has no rungs»: son advertencias de recomendación, porque se eligió el método válido de nodos correspondientes, no columnas incompletas. No se afirma que el diagnóstico haya dado cero advertencias.

La auditoría de densidad cuenta penetraciones por celdas de 1 mm y conserva las diez celdas más pobladas en JSON. Ese recuento incluye amarres y varios bordes cercanos; sirve para localizar zonas a revisar y no es una medición de deformación de tela. Revisar especialmente uniones de letras, terminales y centros florales en la prueba física.

## Bastidor y prueba sobre gabardina

Usar **SQ20b, 200 × 200 mm**: el diseño de 150,0 × 142,8 mm entra con margen. SQ14b de 140 × 140 mm no alcanza. Janome declara SQ20b y soporte JEF para la MC 550E.

Punto de partida de la prueba, como decisión técnica que debe ajustarse a la gabardina real:

1. Retazo de la misma gabardina, con el mismo número de capas que la zona del bolso.
2. Estabilizador recortable medio; bastidar estabilizador y tela juntos sin estirar. Comprobar que la pieza quede firme y plana.
3. Hilo de bordado de buena calidad en los tres tonos indicados y aguja de bordado adecuada a la tela. Para la primera muestra, probar 75/11 y ajustar si la gabardina necesita 80/12.
4. Comenzar a unas 500 puntadas/minuto. Probar el corte de saltos al inicio, observar el center walk y las primeras columnas antes de completar la muestra.
5. Evaluar legibilidad de SOCKS, continuidad de conexiones, rigidez y relieve de centros, arrugas, tiraje y cobertura del rosa. Si la tela domina demasiado los pétalos, cerrar su separación gradualmente; no aumentar toda la densidad del diseño.

No se verificó el archivo cargándolo en la máquina física, ni se realizó bordado sobre tela. Siguen pendientes la tensión óptima, el estabilizador exacto, el comportamiento real de los cortes, la cobertura con el hilo elegido y la deformación al retirar el bastidor. Los JEF son archivos para **prueba**, no una garantía de producción sin muestra.

## Entorno y reproducción

Inkscape 1.4.2; Ink/Stitch v3.2.2 (windows-x86_64); esquema SVG de Ink/Stitch 3; Python 3.12.14; NumPy 2.3.5, Pillow 12.3.0, lxml 6.1.1 y pyembroidery 1.5.1. Se comprobaron los ejecutables, la ayuda de Inkscape, las acciones registradas y los descriptores `.inx`; se consultó el código de la versión correspondiente para no inventar parámetros.

Las bibliotecas de geometría descargadas inicialmente resultaron bloqueadas por Windows. El flujo final no las utiliza: reconstruye y mide con NumPy y Python, y normaliza rellenos con el motor instalado de Ink/Stitch. Python también tuvo restricciones de escritura en OneDrive. El trabajo se generó en una carpeta permitida y se copió al proyecto con Node, sin cambiar ajustes de seguridad.

`herramientas/reproducir.mjs` reproduce el flujo con los ejecutables encontrados en esta computadora: reconstrucción, reparación de rellenos, exportación, auditoría e informe. Genera temporalmente los archivos y los copia a la carpeta del proyecto. Para una instalación diferente hay que ajustar las rutas de Inkscape/InkStitch y definir `ANIME_PYTHON`. Los scripts separados admiten `--salida`; las dependencias están en `requirements.txt`. Las auditorías y SHA-256 del resultado entregado permanecen en `trabajo`.

## Fuentes técnicas

- [Ink/Stitch: columnas satin y método de nodos](https://inkstitch.org/docs/stitches/satin-column/).
- [Ink/Stitch: running y triple running](https://inkstitch.org/docs/stitches/running-stitch/).
- [Ink/Stitch: línea de comandos y plan de puntadas](https://inkstitch.org/docs/command-line/).
- [Ink/Stitch: herramientas de relleno](https://inkstitch.org/docs/fill-tools/).
- [Janome: MC 550E, bastidores, formatos y velocidad](https://www.janome.ca/product/memory-craft-550e/).

SHA-256 principal: `60a185b27c542cb5a12a4ed97779a5bfb00c5811696f4c1da81f2584e71da80d`.
SHA-256 variante circular: `c67718bd3a26575f59a77b55a70a28a77303f195990f99ae74f78b63de73922e`.
