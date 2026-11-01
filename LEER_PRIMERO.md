# Plan para la aplicación web de bordados

Fecha: 1 de noviembre de 2026.

Objetivo: subir una imagen, analizarla con una IA de OpenAI o un modelo local, construir un diseño editable y generar un JEF verificable para una prueba de bordado. La aplicación se usará desde varios equipos.

Este paquete contiene el plan y las instrucciones de coordinación. Todavía no se creó la aplicación ni se probaron proveedores de IA dentro de ella.

## Archivos

1. `PLAN_MAESTRO.md`: producto, pasos usados en Anime Socks, arquitectura y fases de desarrollo.
2. `CONTRATOS_Y_CALIDAD.md`: datos compartidos, estados, API propuesta y condiciones para aceptar un archivo.
3. `TRABAJO_CON_VARIAS_IAS.md`: reparto para dos, tres o cuatro IAs y mensajes listos para copiar.
4. `TAREAS_INICIALES.md`: primeros trabajos, responsables, dependencias y criterios de aceptación.

## Cómo comenzar

Entregar el plan y los contratos a las dos IAs. A la primera, darle el mensaje de motor e integración; a la segunda, el de interfaz web. Empezar por el hito H0 y el primer recorrido real de generación web. Incorporar el análisis de imágenes en el hito H2.

Si las IAs trabajan con archivos y Git, usar el mismo repositorio con ramas separadas. Si se usan chats que no acceden al proyecto, adjuntar estos documentos y pasarles los cambios del contrato cuando se actualicen. Una ruta local escrita en un mensaje no les concede acceso a los archivos.

Los SVG, JEF e imágenes de Anime Socks servirán como referencias de prueba. Se conservarán las dos carpetas de bordados existentes.
