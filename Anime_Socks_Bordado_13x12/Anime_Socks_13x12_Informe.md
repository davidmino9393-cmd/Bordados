# Anime Socks — versión pequeña para prueba de bordado

## Tamaño y proporciones

Área solicitada: aproximadamente 130 × 120 mm. Se conservó la proporción del logo para que entre en esa área, en lugar de estirar por separado sus ejes.

- Principal sin círculo: **126.2 × 120.0 mm**.
- Con círculo: **126.2 × 120.0 mm**.
- Reducción geométrica desde el diseño anterior: factor 0.83893790.

## Digitalización a la nueva escala

Se redujeron los SVG editables ya corregidos y se regeneraron todas las puntadas con Ink/Stitch 3.2.2. No se encogió el JEF anterior. Se mantuvo la composición, la forma de las letras, las flores y los tres tonos.

Las separaciones físicas se mantienen: satin 0,43 mm, rellenos abiertos de pétalos 0,85 mm, hojas 0,95 mm, capullos 0,75 mm y corazones 0,45 mm. Los contornos y ramas utilizan running de hasta 2 mm para definir mejor las curvas pequeñas; el círculo conserva running simple de 2,5 mm.

En SOCKS se redujo la compensación satin a 0,15 mm y se mantuvo sin underlay adicional. Se retiró center walk de los tramos finos del lazo de A y de e; las columnas más anchas conservan su configuración anterior. Las dos curvas de cada satin tienen nodos correspondientes.

## Métricas medidas desde los JEF

| Medida | Sin círculo | Con círculo |
|---|---:|---:|
| Puntadas | 5600 | 5750 |
| Saltos, tras interpretar cortes | 100 | 101 |
| Cortes codificados | 53 | 54 |
| Cambios de color | 2 | 2 |
| Bloques de hilo | 3 | 3 |
| Puntada máxima, mm | 4.14 | 4.14 |

Se verificaron longitud de archivo, tabla de hilos, registros, todos los comandos binarios hasta el marcador final, coordenadas y cabecera de bastidor. Se releyeron los JEF con pyembroidery 1.5.1 y se dibujaron las vistas previas desde esas coordenadas reales. Se generó el plan completo con Ink/Stitch.

Diagnóstico a esta escala: {'Satin has no rungs': 14}. Los avisos de ausencia de rungs son recomendaciones para columnas que aquí emplean el método documentado de nodos correspondientes. No se encontraron otros avisos geométricos en ese diagnóstico.

## Bastidor Janome

Para la primera prueba usar **RE20b, 140 × 200 mm**, coherente con la cabecera JEF del exportador (código 2). Las dimensiones también caben geométricamente en SQ14b de 140 × 140 mm. El JEF no incluye un código exclusivo para SQ14b; no se verificó en la máquina un cambio a ese bastidor. No se alteró artificialmente la cabecera. Comprobar la posición con la función de trazado antes de bordar.

Fuente de tamaños de bastidor: [Janome MC 550E](https://www.janome.ca/product/memory-craft-550e/). Método satin: [Ink/Stitch](https://inkstitch.org/docs/stitches/satin-column/).

## Hilos y prueba

Orden de hilos físicos: **malva grisáceo → rosa pálido → rosa viejo más oscuro**. El JEF muestra aproximaciones de la paleta Janome; elegir los hilos por los tonos del logo y no por nombres como Beige Gray o Umber.

Probar primero en un retazo equivalente a la gabardina del bolso, con estabilizador recortable y los hilos elegidos. Revisar especialmente la legibilidad de SOCKS, las conexiones de Anime, la cobertura de los pétalos y el funcionamiento de los cortes. Los cortes JEF se codifican mediante tres saltos de desplazamiento cero; su ejecución física depende del ajuste de la máquina.

La integridad digital está comprobada. No se realizó un bordado físico ni se cargaron estos archivos en la máquina. Esta reducción requiere su propia muestra aunque la versión grande haya dado buen resultado.

## Reproducción y archivos

Se incluye `herramientas/crear_version_pequena.py`. Requiere Python con Pillow, lxml y pyembroidery; recibe `--original` (carpeta de la versión grande), `--salida`, `--vendor` y opcionalmente `--factor`. Las rutas de Inkscape/InkStitch corresponden a la instalación comprobada en esta computadora.

Las auditorías, diagnóstico y plan están en `trabajo`. Los SVG y las vistas previas son editables/consultables por separado. Se conservaron todos los archivos de la versión grande.

SHA-256 principal: `d0f45dc5bf6dd63c26289dde233cf5907e46b24a223b7132f6681f17c4775e40`.
SHA-256 con círculo: `149ccca849d89483ba2fa91102f676f6f99c17ece51789ab681545ff4cca8536`.
