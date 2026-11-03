# Referencias de la Janome MC 550E para completar H3

Propósito: reunir los límites de la Janome MC 550E, el formato JEF y las referencias de digitalización publicadas, para acotar lo que la muestra H3 debe medir. Separa dato confirmado de opinión. **Nada de esto está calibrado**: son referencias, no medidas en tu tela.

Fecha: 2026-11-02. Estado: documento de trabajo. La búsqueda no pudo usar Reddit ni abrir el manual oficial (ver [§2](#2-qué-no-se-pudo-consultar)).

Contenido: [1 Cómo leerlo](#1-cómo-leer-este-documento) · [2 Qué no se pudo consultar](#2-qué-no-se-pudo-consultar) · [3 Límites de la máquina](#3-límites-de-la-máquina) · [4 Formato JEF](#4-formato-jef) · [5 Digitalización publicada](#5-referencias-de-digitalización-publicadas) · [6 Anime Socks](#6-anime-socks-referencia-empírica) · [7 Qué cubre H3](#7-qué-cubre-h3) · [8 Cambios propuestos](#8-cambios-propuestos-no-aplicados) · [9 Otras máquinas](#9-otras-máquinas) · [10 Pendientes](#10-pendientes-para-cerrar-h3) · [11 Fuentes](#11-fuentes)

Documentos relacionados: [PROTOCOLO_H3.md](PROTOCOLO_H3.md) · [planilla_h3.csv](planilla_h3.csv) · [Anime_Socks_Informe.md](../../../Anime_Socks_Bordado/Anime_Socks_Informe.md) · [profiles.py](../../../packages/contracts/embroidery_contracts/profiles.py) · [profiles.json](../../../services/api/profiles.json)

## 1. Cómo leer este documento
| Confianza | Significa |
|---|---|
| A | Especificación del fabricante, o dato leído en el código o en los archivos del proyecto |
| B | Fuente técnica reconocida, o varias fuentes independientes coinciden |
| C | Una sola fuente (blog, tienda, usuario) o analogía con otro modelo Janome |
| D | No encontrado |

| Obtenido | Significa |
|---|---|
| Leído | Abrí la página y extraje el dato |
| Resumen | Solo vi el resumen que devolvió el buscador; no abrí el original |
| Código | Leído en el repo o en el entorno del proyecto |

## 2. Qué no se pudo consultar
| Fuente | Resultado |
|---|---|
| Reddit | El buscador rechaza el dominio y `old.reddit.com` no se pudo abrir. **Ningún dato de este documento viene de Reddit** |
| Manual oficial MC 550E y 500E (`janome.com`, PDF) y guía de Artistic Digitizer (`janome.ca`) | Error 403. Los datos del manual vienen de fragmentos que devolvió el buscador; de la guía de Artistic Digitizer no hay nada |
| manualslib, manualmachine, forum.embroideres.com | Error 403 |
| groups.io (foro de usuarios de Janome) | Error 402. Solo se vio un resumen del hilo |
| JustAnswer | Respuestas genéricas de soporte; sin límites numéricos de digitalización |

Los «foros» alcanzados son blogs de tiendas, preguntas y respuestas de soporte y un resumen de un hilo de groups.io. Ninguno da límites numéricos de digitalización de la 550E.

Cómo cerrarlo: (1) dejar el manual en PDF dentro del repo, o pegar las páginas de especificaciones, jump trimming y solución de problemas; (2) buscar en Reddit y pegar los hilos (términos: `janome 550e`, `MC550E satin`, `janome jump trim`; por ejemplo en r/embroidery y r/MachineEmbroidery).

## 3. Límites de la máquina
| Parámetro | Valor | Conf. | Obtenido |
|---|---|---|---|
| Área máxima de bordado | 200 × 360 mm (7,9″ × 14,2″) | A | Resumen (Janome) |
| Bastidores incluidos | RE36b 200 × 360 · SQ20b 200 × 200 · RE20b 140 × 200 · SQ14b 140 × 140 mm | B | Leído (blog de tienda) + Resumen (Janome, SQ20b) |
| Velocidad | 400 a 860 puntadas por minuto (ppm) | A | Resumen (Janome) |
| Espesor máximo tela + estabilizador | 3 mm | B | Resumen (manual oficial) |
| Hilo | Tamaño 50 a 90; no usar 30 ni más grueso | B | Resumen (manual oficial) |
| Aguja | 75/11 estándar; 90/14 para telas gruesas | C | Leído (dos blogs de tienda) |
| Corte de saltos | La 550E lo tiene y es programable. **Umbral propio sin confirmar** | D | Resumen |
| Corte de saltos, analogía | En el modo «fácil» de la 500E y la 15000 corta saltos de 3 mm o más y en cada cambio de color; el modo avanzado permite fijar la longitud | C | Resumen (manuales 500E y 15000) |
| Letra incorporada más chica | ≈ 10 mm en mayúscula (tamaño S). Es de la fuente interna de la máquina, **no** un límite para diseños externos | B | Resumen (manual oficial) |
| Máximo de puntadas, colores o tamaño de archivo | No encontrado | D | |
| Escalado en pantalla | No encontrado; tiendas aconsejan no pasar de 5–10 % porque la densidad cambia | C | Resumen |
| Velocidad según el trabajo | 400–600 ppm para satin denso, hilo metálico y detalle; 860 solo en rellenos grandes sobre tela firme. Es opinión de tienda | C | Leído |

## 4. Formato JEF
| Parámetro | Valor | Conf. | Obtenido |
|---|---|---|---|
| Unidad de coordenadas | 0,1 mm | A | Código (pyembroidery `JefWriter.py`) |
| Desplazamiento máximo por orden | ±127 unidades = **12,7 mm**. Un movimiento mayor ocupa varias órdenes | A | Código |
| Corte de hilo | Tres saltos de desplazamiento cero (`trim_at = 3`) | A | Código |
| Códigos de bastidor en la cabecera | 0 = 110 × 110 · 1 = 50 × 50 · 2 = 140 × 200 · 3 = 126 × 110 · 4 = 200 × 200 mm | A | Código + Leído (EduTech) |
| Elección del código (ancho × alto, mm) | < 50 × 50 → 1 · < 126 × 110 → 3 · < 140 × 200 → 2 · < 200 × 200 → 4 · **en otro caso → 0 (110 × 110)** | A | Código (`get_jef_hoop_size`) |

Consecuencias:
- No hay código propio para SQ14b ni para RE36b. Un diseño de 130 × 150 mm sale con código 2 (RE20b), aunque quepa en SQ14b; el informe de Anime Socks 13×12 ya lo anota.
- Un diseño que llegue a 200 mm en algún lado sale con código 0 (110 × 110), aunque se borde con RE36b. **No se sabe cómo reacciona la máquina**: probarlo.
- Anime Socks (150,0 × 142,8 mm) y la muestra H3 (140 × 150 mm) salen con código 4 (SQ20b).
- Catálogo actual (`profiles.json`): `janome_mc550e` con solo `sq20b`, `max_colors = 3` (decisión del proyecto, no límite de la máquina) y `calibration_status = proposed`. No guarda área máxima, velocidad ni umbral de corte.

## 5. Referencias de digitalización publicadas
Valen para cualquier máquina; ninguna es un límite de la 550E.

| Parámetro | Rango publicado | Conf. | Obtenido |
|---|---|---|---|
| Ancho mínimo de satin | 1,0 mm como mínimo absoluto; 1,5 mm o más recomendado. Ink/Stitch recomienda más de 1 mm y pide contornos de más de 1,5 mm | B | Leído (Ink/Stitch) + Resumen (guías) |
| Ancho máximo de satin | 8 a 10 mm en la práctica (una fuente da 12 mm como absoluto); más ancho, relleno | B | Resumen |
| Rango habitual | 1,5 a 8 mm (otra fuente: 2 a 7 mm) | B | Resumen |
| Separación del satin | Base 0,40 mm; habitual 0,38–0,45; 0,45 en formas de menos de 5 mm. Embrilliance: normal 0,4, rango 0,3–2,0 | B | Resumen |
| Puntada mínima | Piso común 0,5 mm. Ink/Stitch pide al menos 0,3 mm para máquinas W6; un manual Brother descarta las de 0,3 mm o menos | C | Leído (Ink/Stitch) + Resumen |
| Altura mínima de letra en satin | ≈ 5 mm (4,8 mm en una fuente; 6,2 mm en minúscula); trazos de 0,6 mm o más; hilo 60 wt permite letras ≈ 25 % más chicas | C | Resumen |
| Compensación de tracción | **Sin valor universal**: depende de tela, hilo y estabilizador. Ink/Stitch la admite en mm fijos o en % | B | Resumen |
| Línea fina | Bajo ≈ 5 mm de texto conviene puntada corrida; no hay mínimo publicado de ancho de línea | C | Resumen |
| Detalle muy fino | Un usuario comercial resolvió roturas con aguja 8 e hilo 60 wt en vez de aguja 14 e hilo 40 wt | C | Resumen (groups.io) |
| Relleno | Sin rangos firmes de separación; solo la densidad base de 0,4 mm | C | Resumen |

## 6. Anime Socks: referencia empírica
Condiciones de la costura, declaradas por David el 2026-11-02. No hay fotos ni medidas registradas: es un dato cualitativo.

| Dato | Declarado | Falta anotar |
|---|---|---|
| Resultado | «Salió muy bien» | Fotos y medidas |
| Archivo | El JEF que le dio Codex, de nombre parecido a «animesocks.jef» | Cuál era (ver abajo): no hay ningún archivo con ese nombre en el repo |
| Tela | Gabardina | |
| Estabilizador | Grueso | Tipo (recortable o rasgable) y gramaje |
| Hilo | Hilo de bordar | Marca y grosor |
| Aguja | La que Janome trae de fábrica | Número |
| Velocidad | **400 ppm**, el mínimo del rango de la máquina (400–860) | |
| Bastidor | Sin anotar | Depende del archivo |

El plan del informe original era distinto (estabilizador recortable medio, aguja 75/11, unas 500 ppm); lo que vale es lo declarado. **El resultado vale para esas condiciones**: una tela, un estabilizador y 400 ppm. No se extrapola a otra velocidad.

Candidatos (todos con 3 bloques de hilo). Se distinguen por el tamaño del diseño que muestra la máquina al cargarlo:

| Archivo | Tamaño en pantalla | Bytes | Puntadas | SHA-256 (12 primeros) |
|---|---|---|---|---|
| `Anime_Socks_Optimizado.jef` | 150,0 × 142,8 mm | 14 816 | 6789 | `60a185b27c54` |
| `Anime_Socks_Con_Circulo.jef` | 150,0 × 142,8 mm | 15 182 | 6966 | `c67718bd3a26` |
| `Anime_Socks_13x12.jef` | 126,2 × 120,0 mm | 12 386 | 5600 | `d0f45dc5bf6d` |
| `Anime_Socks_13x12_Con_Circulo.jef` | 126,2 × 120,0 mm | 12 702 | 5750 | `149ccca849d8` |

`Anime_Socks_Inicial.jef` (36 bloques de hilo) queda descartado por improbable. Los 150,0 mm de ancho no caben en RE20b ni SQ14b: esa versión se borda con SQ20b. Para la 13×12 el informe recomienda RE20b.

Parámetros del SVG de Ink/Stitch de la versión principal (`Anime_Socks_InkStitch.svg`) y de su informe:

| Elemento | Parámetro | Valor |
|---|---|---|
| Satin (14 columnas) | Separación | 0,43 mm |
| | Compensación de tracción | 0,2 mm |
| | Puntada mínima / máxima / corta | 0,3 / 5 / 0,35 mm |
| | Base | Sin base de contorno ni de zigzag; center walk en 6 de 14 |
| Relleno | Separación | 0,45 · 0,5 · 0,75 · 0,85 · 0,95 mm (abierto a propósito, deja ver la gabardina) |
| | Ángulos / puntada máxima / base | Variados (los más usados, 40° y 75°) / 2,5 mm / sin base |
| Puntada corrida (67 trazos) | Largo | 1,8 · 2,0 · 2,1 · 2,3 mm |
| | Tolerancia | 0,12 mm |
| | Triple (bean) | 13 trazos |
| Terminales demasiado finos | Técnica | Triple corrida en lugar de satin |
| Diseño | Tamaño / puntadas / hilos | 150,0 × 142,8 mm / 6789 / 3 colores, 2 cambios |
| | Bastidor / código JEF | SQ20b / 4 |
| Cortes | Entre objetos separados hasta 2 mm | Eliminados (la máquina corta saltos desde ≈ 3 mm en modo fácil: coherente, sin confirmar en la 550E) |

La versión 13×12 (`Anime_Socks_13x12_InkStitch.svg`) usa casi lo mismo. Difiere en: compensación de 0,15 mm en 6 objetos (el resto 0,2 mm), center walk en 4 de 14 satins y puntada corrida de 2,0 mm en casi todos los trazos (y 1,8 mm en 2). Si se cosió esa versión, la tabla anterior vale con esas diferencias.

La prueba `test_reexport_regression.py` confirma que re-exportar el SVG principal da los mismos comandos que `Anime_Socks_Optimizado.jef`. Eso es una prueba digital, no de costura.

## 7. Qué cubre H3
Los anchos de la planilla incluyen la compensación (0,6 mm nominal = 1,0 mm cosido). Las predicciones de la columna central son hipótesis a confirmar, no resultados.

| Fila | Qué mide | Qué anticipan las referencias | Falta medir |
|---|---|---|---|
| A (satin 1,0–6,4 mm) | Ancho mínimo bordable | A1 (1,0) en el límite absoluto; A2–A3 (1,2–1,4) bajo lo recomendado; A4–A8 dentro del rango | El menor ancho con aspecto `bien` |
| B (separación 0,30–0,60) | Cobertura | 0,40–0,45 habitual; 0,30–0,35 con riesgo de fruncido; 0,5–0,6 puede dejar ver la tela | La separación con mejor aspecto |
| C (compensación 0–0,4) | Ancho real | Anime Socks usó 0,2 mm | La compensación que acerque a 3,0 mm |
| D (relleno 0,3–0,8) | Cobertura y fruncido | Denso ≈ 0,4; Anime Socks abrió a 0,5–0,95 | La separación según el efecto buscado |
| E (pespunte) | Largo y grosor | Anime Socks: 2,0–2,3 mm y triple | Qué repetición se distingue |
| Marco 140 × 150 | Retiro | Sin referencia publicada | El retiro por eje |

No cubre y convendría sumar (opcional):
1. **Corte de saltos:** saltos de 2, 3, 4 y 6 mm con el corte en modo fácil, para fijar el umbral real.
2. **Texto:** letras de 4, 5, 6 y 8 mm en satin y en corrida.
3. **Carga del JEF:** qué bastidor propone la máquina para 140 × 150 mm y si permite bordar con SQ20b.

## 8. Cambios propuestos (no aplicados)
Ninguno de la tabla está hecho. Decide David. Los respaldos de Anime Socks valen para gabardina, estabilizador grueso y 400 ppm (§6).

**Ya aplicado (2026-11-02, para que una imagen llegue a un JEF):** la generación de puntadas desde una imagen usa los valores de Anime Socks (relleno a 0,45 mm, puntada de 2,5 mm, compensación de 0,2 mm, sin base; `inkstitch.py`) y un filtro de lo bordable (`stitchable.py`) que quita manchas de menos de 1 mm² (≈ 1 mm de lado, §5) y capas con todos los canales ≥ 240. Cada trabajo lo avisa y queda en revisión. El ancho mínimo de `thin_features.py` (0,4 mm) no cambió.

| Parámetro | Hoy en el código | Propuesta | Respaldo |
|---|---|---|---|
| Ancho mínimo bordable (`thin_features.py:16`) | 0,4 mm, sin calibrar | Satin desde ≈ 1,0 mm; por debajo, corrida (triple en terminales finos). Conservar 0,4 mm como piso de lo que se mide | §5 y §6 |
| Separación de relleno (`pipeline.py:22`) | 0,4 mm | Mantener 0,4 mm como denso; permitir 0,5–0,95 mm para rellenos abiertos | Anime Socks |
| Largo de puntada (`pipeline.py:21`) | 2,5 mm | Sin cambio: coincide con Anime Socks (2,0–2,5 mm) | §6 |
| Catálogo `janome_mc550e` | Solo `sq20b`, sin límites | Agregar RE36b, RE20b y SQ14b como bastidores, y registrar área máxima, velocidad y umbral de corte con su fuente. **Cambiar el contrato exige tu ratificación** | §3 y §4 |
| `max_colors = 3` | Decisión del proyecto | Revisar: no es un límite de la máquina | §3 |

## 9. Otras máquinas
El catálogo ya separa `MachineProfile`, `HoopProfile`, `FabricProfile` y `ThreadProfile`. Lo propio de cada máquina:

| Campo | Dónde se obtiene | Se comparte entre máquinas |
|---|---|---|
| Bastidores y área máxima | Ficha del fabricante | No |
| Velocidad | Ficha del fabricante | No |
| Formato de archivo y códigos de cabecera | Especificación del formato y código de pyembroidery | No |
| Lógica de corte de saltos | Manual de la máquina | No |
| Espesor, hilo y aguja admitidos | Manual de la máquina | Parcial |
| Ancho mínimo, separación y compensación | Muestra física (H3) | Depende de tela, hilo y estabilizador más que de la marca |

Procedimiento: ficha → manual → especificación del formato → foros para contrastar → muestra física. Cada valor lleva fuente, fecha y confianza.

## 10. Pendientes para cerrar H3
- [x] David: condiciones de la costura de Anime Socks (gabardina, estabilizador grueso, hilo de bordar, aguja de fábrica, 400 ppm). Hecho el 2026-11-02.
- [ ] David: qué tamaño mostró la máquina al cargar el archivo (150,0 × 142,8 mm o 126,2 × 120,0 mm); identifica el archivo y el bastidor.
- [ ] David: tipo de estabilizador, número de aguja, marca y grosor del hilo, y fotos del bordado. Las fotos se pueden registrar en la web en «Registrar muestra física» (hasta 4).
- [ ] Codex: confirmar el nombre y el hash exactos del JEF que le dio a David.
- [ ] Decidir si `gabardina_inicial` pasa a `physically_calibrated`: exige un registro de calibración con evidencia física (la muestra H3, o fotos y medidas de Anime Socks).
- [ ] David: manual oficial en PDF y/o hilos de Reddit (ver §2).
- [ ] En la máquina: umbral de corte de saltos en el menú y bastidor propuesto al cargar `muestra_h3.jef`.
- [ ] David: coser la muestra H3 (mínimo, filas A y B) y llenar `planilla_h3.csv`.
- [ ] David: decidir los cambios de §8.

## 11. Fuentes
Máquina:
- [Janome MC 550E (Australia)](https://www.janome.com.au/product/mc550e/) · [Janome MC 550E LE](https://www.janome.com/product/memory-craft-550e-limited-edition/) · [manual oficial 550E LE](https://www.janome.com/wp-content/uploads/2019/11/inst-mc550e_le.pdf) (no abierto)
- [Rocky Mountain Sewing](https://rockymountainsewing.com/product/janome-memory-craft-550e) · [guía de la 550E (tienda)](https://embroideryhoopstore.com/blogs/articles/janome-memory-craft-550e-on-screen-editing-big-hoops-and-fewer-hooping-headaches-a-practical-shop-tested-walkthrough) · [primer bordado en la 550E (tienda)](https://embroideryhooping.com/blogs/articles/janome-memory-craft-550e-from-first-hoop-to-first-stitch-plus-the-real-world-fixes-that-save-you-time) · [ajustes 400E/500E/550E (tienda)](https://embroideryhoopstore.com/blogs/articles/stop-guessing-your-janome-400e-500e-550e-settings-the-calm-pro-level-menu-tweaks-that-prevent-wasted-thread-and-ugly-stitchouts)
- [Manual 500E, corte de saltos](https://www.manualslib.com/manual/1054581/Janome-Memory-Craft-500e.html?page=55) (no abierto) · [Manual 15000](https://homeappliance.manualsonline.com/manuals/mfg/janome/15000.html?p=158) (no abierto)
- [Hilo de usuarios en groups.io](https://groups.io/g/onlinesewing-janome/topic/79347085) (no abierto)

Formato:
- [Formato JEF (EduTech)](https://edutechwiki.unige.ch/en/Embroidery_format_JEF) · `JefWriter.py` de pyembroidery en el entorno del proyecto

Digitalización:
- [Ink/Stitch: columna de satin](https://inkstitch.org/docs/stitches/satin-column/) · [Ink/Stitch: preferencias](https://inkstitch.org/docs/preferences/)
- [Guía de satin (DrawStitch)](https://www.drawstitch.com/blog/knowledge-base/how-to-digitize-satin-stitches/) · [Satin de 1 a 8 mm](https://embroideryhooping.com/blogs/articles/satin-stitch-digitizing-that-actually-sews-clean-point-counterpoint-1-8-mm-rules-and-settings-that-stop-pinching)
- [Embrilliance: propiedades de puntada](https://embrilliance.com/Help/Platform%20Win%201158/stitchproperties.htm) · [Digitizing 101 (Embroidery Legacy)](https://embroiderylegacy.com/wp-content/uploads/2025/09/Digitizing-101-Cheat-Sheet-2025.pdf)
- [Letras chicas (Graphics Pro)](https://graphics-pro.com/education/what-can-embroiderers-do-to-execute-small-lettering-successfully/) · [Letras chicas (Ignition)](https://blog.ignitiondrawing.com/small-lettering-guide-part-1/) · [Letras nítidas (ASI)](https://members.asicentral.com/news/how-to/may-2018/keep-your-small-letters-crisp/)
