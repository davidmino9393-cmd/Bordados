# Cómo convertir una imagen en un JEF

Propósito: subir una imagen en la página web y descargar el JEF para la Janome MC 550E. El resultado **no está calibrado**: usa los parámetros de la costura de Anime Socks (gabardina, estabilizador grueso, 400 ppm). Probalo en un retazo antes de la pieza final.

Contenido: [Iniciar](#iniciar) · [Usar la página](#usar-la-página) · [Qué esperar](#qué-esperar) · [Si algo falla](#si-algo-falla)

Documentos relacionados: [services/api/docs/CONFIG.md](services/api/docs/CONFIG.md) · [REFERENCIAS_JANOME_MC550E.md](tests/calibration/h3/REFERENCIAS_JANOME_MC550E.md) · [PROTOCOLO_H3.md](tests/calibration/h3/PROTOCOLO_H3.md)

## Iniciar
| Paso | Qué hacer |
|---|---|
| 1 | Doble clic en `scripts\iniciar-web.cmd` (una sola vez por sesión). Se abre el navegador en `http://localhost:5173` |
| 2 | No hay que escribir usuario ni clave: la web los toma de `services\api\.runtime\api-config.json` y los agrega sola |
| 3 | Para detener todo, cerrá la ventana negra |

La primera vez hace falta `cd apps\web` y `npm install`, y que existan Inkscape, Ink/Stitch y el archivo de configuración privada de la API.

## Usar la página
| Paso | Qué hacer |
|---|---|
| 1 | «Crear proyecto» con cualquier nombre. Un proyecto puede reunir varios archivos: se genera un bordado de cada uno, con sus propios ajustes, y los anteriores quedan en «Trabajos anteriores» |
| 2 | Subir la imagen (PNG o JPG, fondo blanco o transparente) |
| 3 | Ancho y alto máximos en mm (el bordado entra en ese cuadro, sin deformarse) y cantidad de hilos |
| 4 | Dejar «Sin análisis de IA» (no hace falta OpenAI ni Ollama) |
| 5 | «Generar bordado» y esperar: de unos segundos a unos minutos, según el diseño |
| 6 | «Descargar archivo JEF»: se llama como la imagen. Copiarlo al pendrive de la máquina |
| 7 | Para otro tamaño, más abajo está «Variante de tamaño»: genera un trabajo nuevo desde la imagen original y deja el anterior intacto (no achica el JEF). Con un SVG preparado, la hoja entra en el cuadro sin deformarse; si el SVG no tiene `viewBox` ni ancho y alto absolutos, la página lo rechaza y dice por qué |

## Qué esperar
| Tema | Detalle |
|---|---|
| Estado final | «Necesita tu revisión»: siempre. El JEF es descargable, pero ningún diseño queda aprobado por la página; eso lo decide la costura de prueba |
| Colores | El límite es de hilos. Una capa casi blanca se toma como fondo y no gasta un hilo |
| Qué se quita | Manchas de menos de 1 mm² y capas casi blancas. La página lo avisa con los números |
| Técnica | Todo se borda como relleno: las líneas muy finas salen como relleno angosto, no como satin ni como puntada corrida |
| SVG preparado | Se borda al tamaño con el que se preparó: el ancho y el alto que indicás son solo el límite (si el dibujo es más grande, el trabajo se rechaza). Para otro tamaño, usá «Variante de tamaño» en el resultado |
| Bastidor | El perfil actual es SQ20b (200 × 200 mm); el JEF lleva ese código de bastidor |
| Tiempo | Un logo simple, unos 10 s; Anime Socks, unos 2 min |

## Si algo falla
| Síntoma | Causa probable |
|---|---|
| La página muestra un error de acceso (401) | Cerrar la ventana negra y volver a abrir `iniciar-web.cmd`: la web debe iniciarse con ese script, que le pasa las credenciales de la configuración |
| El script dice que falta la configuración | Falta `services\api\.runtime\api-config.json` (ver CONFIG.md) |
| «No se pudo generar el bordado» | La incidencia dice la causa; los registros están en `services\api\.runtime\logs` |
| La máquina no acepta el diseño o pide otro bastidor | Anotarlo: es justo lo que falta probar (ver §10 de REFERENCIAS_JANOME_MC550E.md) |
