# Primeras tareas y aceptación

Fecha: 1 de noviembre de 2026. Las tareas describen trabajo futuro; no están marcadas como completadas.

## H0 — comprobar el motor y acordar interfaces

| ID | Responsable | Tarea | Criterio de aceptación | Dependencia |
|---|---|---|---|---|
| H0-01 | IA 1 | Inventariar scripts, ejecutables y datos específicos de Anime Socks | Mapa de funciones reutilizables y restricciones; no suponer que `digitalizar.py` acepta otros logos | Ninguna |
| H0-02 | IA 1 | Definir esquemas, estados, errores y API v0.1 | Ejemplos acordados para web, motor y visión; unidades explícitas | H0-01 |
| H0-03 | IA 1 | Probar worker en entorno de servidor | Generación sin intervención de escritorio; identificar dependencias del entorno gráfico | H0-01 |
| H0-04 | IA 1 | Extraer adaptador de exportación y auditoría | Trabaja con rutas configurables, directorio de job y perfil de máquina | H0-02, H0-03 |
| H0-05 | IA 2 | Diseñar el recorrido web y estados | Carga, ajustes, progreso, revisión y descarga coherentes con contratos | H0-02 |
| H0-06 | IA 1 + revisión | Fijar fixtures y regresiones | Dos variantes conocidas, sus límites y métricas, con comparación normalizada del JEF | H0-04 |

H0 se considera completo cuando el motor produce, relee y mide archivos en el entorno elegido, los errores se devuelven de forma controlada y la IA de web puede trabajar contra una interfaz estable.

## H1 — primer recorrido web con artefactos reales

| ID | Responsable | Tarea | Criterio de aceptación |
|---|---|---|---|
| H1-01 | IA 1 | Proyectos, archivos y usuarios | Acceso a los proyectos y descargas correspondientes |
| H1-02 | IA 1 | Cola, worker, estados y cancelación | El proceso web sigue respondiendo mientras se genera; falla o cancela limpiamente |
| H1-03 | IA 2 | Carga de SVG preparado y ajustes de destino | Tamaño en mm y proporciones visibles, con validación de entradas |
| H1-04 | IA 1 + IA 2 | Generación y descarga real | El archivo descargado coincide con el artefacto auditado del trabajo |
| H1-05 | IA 2 | Vista previa y reporte | Imagen desde JEF y métricas reales; avisos visibles |
| H1-06 | Ambas | Prueba desde dos equipos o sesiones | Trabajos y resultados no se pisan; no hay mezcla de archivos |

Demostración de aceptación: entrar desde otro equipo, cargar el SVG preparado, generar una variante y descargar el JEF medido. La interfaz no declara aprobado físicamente ese resultado.

## H2 — añadir imágenes nuevas y análisis visual

| ID | Responsable con tres IAs | Tarea | Criterio de aceptación |
|---|---|---|---|
| H2-01 | IA 3 | Adaptador OpenAI con visión y salida estructurada | AnalysisSpec validado y manejo de rechazo/incompletitud |
| H2-02 | IA 3 | Separación semántica y geométrica | Las regiones estimadas se distinguen de curvas/máscaras comprobadas |
| H2-03 | IA 3 | Siluetas, ejes de líneas y huecos | Evitar doble trazado de una línea y relleno accidental de huecos |
| H2-04 | IA 1 + IA 3 | Contrato de objetos para digitalización | Técnicas y parámetros dependientes de dimensiones físicas |
| H2-05 | IA 2 | Corrección localizada | Excluir región, ajustar color/técnica y regenerar sin perder el original |
| H2-06 | IA revisora o revisión cruzada | Evaluación con al menos cinco logos nuevos | No hay nombres, resoluciones o coordenadas de esos logos codificados en el motor |

Si solo hay dos IAs, la IA 1 asume las tareas de IA 3 después de H1, mientras la IA 2 prepara revisión y variantes. Se acepta que los casos difíciles pidan corrección justificada; no se acepta que la app siempre entregue un archivo aparentemente exitoso ocultando pérdidas.

## H3–H5 — digitalización, proveedor local y piloto

| ID | Tarea | Criterio de aceptación |
|---|---|---|
| H3-01 | Reglas de running, triple, satin y relleno | Objeto, técnica y razón verificables; columnas difíciles se corrigen o se señalan |
| H3-02 | Optimizar con precedencias | Reduce recorridos cuando es válido; conserva orden necesario para la calidad |
| H3-03 | Variantes de tamaño | Regenera y revalida desde geometría; mantiene separaciones físicas y adapta zonas finas |
| H3-04 | Revisión visual y de formato | Comparación de original, vector y JEF; cabecera y comandos íntegros |
| H4-01 | Adaptador Ollama local | Contrato común, modelo con visión verificado y métricas del hardware real |
| H4-02 | Recuperación y consumo | Reintentos acotados, cancelación, caché e idempotencia; sin cambios silenciosos de proveedor |
| H4-03 | Revisión opcional con otra IA | Aporta incidencias medibles y se conoce su coste adicional |
| H5-01 | Piloto con retazos | Documentar condiciones y resultado de muestras representativas, incluidas dos escalas |
| H5-02 | Publicación privada y operación | Acceso desde varios equipos, configuración externa y recuperación de proyectos/archivos |
| H5-03 | Cierre del MVP | Descarga completa, limitaciones documentadas y próximos tipos de imagen priorizados |

## Decisiones a cerrar durante H0 y las primeras evaluaciones

- Servidor en red privada o alojamiento autenticado por Internet.
- Capacidad y presupuesto del servidor; disponibilidad de GPU si se elige IA local.
- Primeros tipos de logos y materiales que se tomarán como admitidos.
- Modelos concretos de nube/local y coste máximo por trabajo, a partir de ejemplos.
- Versiones instalables de las herramientas y políticas de actualización.
- Quién integrará las ramas y registrará las muestras físicas.

El plan no necesita detenerse por estas decisiones: la viabilidad del motor, los contratos y la interfaz pueden iniciarse con el alcance y referencias ya disponibles.
