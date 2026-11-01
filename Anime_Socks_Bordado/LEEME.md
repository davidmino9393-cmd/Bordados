# Anime Socks — archivos para prueba

Usar `Anime_Socks_Optimizado.jef` para la versión principal sin círculo, o `Anime_Socks_Con_Circulo.jef` para el contorno circular fino. Ambos miden **150,0 × 142,8 mm** y requieren el bastidor **SQ20b de 200 × 200 mm**.

Orden de hilos físicos: **malva grisáceo → rosa pálido → rosa viejo más oscuro**. Los nombres de colores que muestra JEF son aproximaciones de su paleta limitada. Elegir los hilos según el logo y la vista previa, como se explica en el informe.

El PNG está dibujado desde las puntadas del JEF. Abrir `Anime_Socks_Simulacion.html` en un navegador para reproducir todas las órdenes y mostrar u ocultar saltos. Los archivos todavía requieren una prueba sobre retazo de la misma gabardina antes de bordar el bolso.

Leer `Anime_Socks_Informe.md` para parámetros, métricas, limitaciones y prueba inicial. Las auditorías JSON y la primera secuencia quedan en `trabajo`; no cargar el JEF inicial en la máquina, porque conserva cambios de color y cortes innecesarios.

## Reproducir en esta computadora

Desde la carpeta `Anime_Socks_Bordado`, ejecutar en PowerShell:

```powershell
& 'C:\Users\david\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' '.\herramientas\reproducir.mjs'
```

El ejecutor usa el Python de Codex y el Inkscape/InkStitch ya instalados. Instala únicamente pyembroidery en una carpeta temporal y trabaja allí antes de copiar los resultados al proyecto. No modifica la instalación de Inkscape ni los ajustes de seguridad de Windows. Requiere acceso a PyPI para esa dependencia. Una nueva exportación tendrá otra fecha de cabecera y otro SHA-256; las métricas se vuelven a calcular.

Para otras instalaciones, ajustar las rutas de Inkscape/InkStitch en los scripts y establecer `ANIME_PYTHON` en el ejecutor. Los scripts individuales aceptan `--salida`; los que releen bordados también aceptan `--vendor`.
