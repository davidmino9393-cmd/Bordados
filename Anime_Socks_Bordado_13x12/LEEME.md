# Anime Socks — versión pequeña

Diseño proporcional para un área de aproximadamente 13 × 12 cm. Las medidas exactas y los recuentos de puntadas figuran en `Anime_Socks_13x12_Informe.md`.

- `Anime_Socks_13x12.jef`: principal sin círculo.
- `Anime_Socks_13x12_Con_Circulo.jef`: variante con contorno circular fino.
- Los SVG contienen el diseño editable y la configuración de Ink/Stitch a esta escala.
- Los PNG están dibujados desde los JEF releídos.
- `trabajo` conserva el plan de puntadas, diagnóstico y auditorías.

Orden de hilos físicos: **malva grisáceo → rosa pálido → rosa viejo más oscuro**. Los nombres de catálogo mostrados por JEF son aproximaciones; elegir los hilos por el tono del logo.

Para la primera prueba, usar RE20b de 140 × 200 mm, acorde con la cabecera JEF. Las medidas también caben en SQ14b, pero no se probó en la máquina la selección de ese bastidor. Probar antes en un retazo de la misma gabardina y comprobar el corte de saltos y la legibilidad de SOCKS.

## Reproducción local

El script `herramientas/crear_version_pequena.py` recibe `--original` (carpeta de los archivos grandes), `--salida` (carpeta donde Python pueda escribir), `--vendor` (ubicación de pyembroidery) y opcionalmente `--factor`. Utiliza los SVG ya corregidos, mantiene las separaciones físicas de puntada y vuelve a exportar con Ink/Stitch. No reduce el JEF binario anterior.

Dependencias: Pillow, lxml y pyembroidery 1.5.1. Las rutas de Ink/Stitch dentro del script corresponden a la instalación comprobada en esta computadora.
