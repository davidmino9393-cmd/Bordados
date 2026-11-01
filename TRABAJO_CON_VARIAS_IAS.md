# Trabajo con dos o más IAs

Objetivo: construir el mismo proyecto mediante entregas compatibles, sin que cada IA invente una aplicación distinta.

## Reparto con dos IAs

| Rol | Trabajo principal | Áreas propuestas |
|---|---|---|
| IA 1 — motor, API e integración | H0, contratos, worker, validación; después análisis y geometría | `services/api`, `workers/embroidery`, `packages/contracts`, `tests/engine` |
| IA 2 — aplicación web y pruebas de uso | Carga, configuración, proyectos, progreso, revisión y descargas | `apps/web`, `tests/e2e` |

La IA 1 coordina los contratos y la integración. Al principio la IA 2 trabaja con ejemplos de respuesta acordados mientras la IA 1 comprueba el motor de servidor. Después conectan un recorrido real de extremo a extremo.

## Si se dispone de una tercera o cuarta IA

- **IA 3 — visión y geometría:** asume proveedores OpenAI/Ollama, segmentación, trazado y evaluación. Trabaja en `services/vision`, `packages/geometry` y sus pruebas. La IA 1 conserva motor, API y coordinación.
- **IA 4 — revisión independiente:** revisa contratos, archivos JEF, regresiones y casos nuevos. Produce defectos reproducibles y revisa las correcciones; no modifica simultáneamente los módulos que otra IA esté cambiando.

Las IAs pueden ser sesiones distintas de una misma herramienta o herramientas diferentes que accedan al repositorio. La coordinación por contratos, cambios revisables y pruebas importa más que la cantidad de modelos.

## Organización práctica

Estructura propuesta para el futuro código:

```text
apps/web/
services/api/
services/vision/
workers/embroidery/
packages/contracts/
packages/geometry/
tests/fixtures/
tests/engine/
tests/e2e/
docs/
infra/
```

1. Crear una base compartida y acordar contratos v0.1 antes de implementar módulos independientes.
2. Asignar carpetas y ramas; por ejemplo `codex/motor`, `codex/web` y `codex/vision`.
3. Conservar los bordados existentes como referencias de solo lectura para pruebas.
4. Cada IA entrega código, comprobaciones ejecutadas, resultados y pendientes; los datos simulados se identifican.
5. La coordinadora integra un cambio por vez y comprueba el recorrido completo.
6. Si cambia un contrato, comunicar la versión y adaptar ambos extremos antes de continuar.
7. Pedir revisión cruzada: la IA de interfaz verifica la API que consume y la del motor comprueba que la web muestra métricas y estados reales.

Estos pasos son el plan de coordinación. No se crearon ramas, agentes ni servicios como parte de esta entrega documental.

## Mensaje listo para IA 1: motor y coordinación

```text
Vas a desarrollar el motor y backend de una aplicación web de bordados con IA.

Leé PLAN_MAESTRO.md, CONTRATOS_Y_CALIDAD.md y TAREAS_INICIALES.md antes de editar.
Hay otra IA encargada de apps/web. Coordiná a través de contratos versionados.

Contexto:
- El usuario quiere subir una imagen, usar OpenAI o una IA local y obtener
  SVG editables, JEF, preview e informe.
- La primera máquina es Janome MC 550E. El acceso será por navegador desde
  varios equipos.
- Los archivos Anime Socks existentes son referencias, no un digitalizador
  general ni bordados físicamente aprobados.

Tu primer hito es H0:
1. Revisá los scripts de Anime_Socks_Bordado/herramientas.
2. Separá geometrías específicas del logo de exportación y validación reutilizables.
3. Proponé y fijá contratos v0.1, estados y OpenAPI para coordinar con la IA web.
4. Verificá que Inkscape/InkStitch puedan ejecutarse en el entorno de worker
   elegido sin intervención interactiva. Comprobá los comandos antes de usarlos.
5. Exportá desde un SVG preparado, releé el JEF y devolvé dimensiones,
   conteos y preview basados en el archivo real.
6. Registrá versiones, stdout binario, stderr, límites de tiempo y fallos.
7. Prepará después H1: proyecto, trabajo asíncrono, artefactos y descarga.

Las rutas de ejecutables se configuran. Los avisos se clasifican por objeto;
no se descartan en bloque. No confundas geometría de página con tamaño de puntadas.
Los parámetros de tela, colores y bastidor deben ser perfiles configurables.
Cada trabajo conserva sus propios archivos y versiones.

Entregá cambios revisables, comprobaciones ejecutadas y criterios de H0 cumplidos
o pendientes. Si la viabilidad de servidor falla, documentá el bloqueo y una
alternativa comprobable. Coordiná cambios de contrato antes de imponerlos a la web.
```

## Mensaje listo para IA 2: web

```text
Vas a desarrollar la interfaz de la aplicación web de bordados con IA.

Leé PLAN_MAESTRO.md, CONTRATOS_Y_CALIDAD.md y TAREAS_INICIALES.md.
Otra IA construye services/api y workers/embroidery; usa sus contratos versionados.

Implementá en apps/web y sus pruebas:
1. Proyectos y carga de imagen o SVG admitido.
2. Ajustes de tamaño en mm, conservar proporciones, tela, máquina, bastidor,
   cantidad de colores y proveedor de IA.
3. Generación asíncrona con progreso por etapas, cancelación y errores claros.
4. Comparación de original, vector y preview del JEF releído.
5. Revisión localizada cuando exista un elemento dudoso.
6. Variantes de tamaño y descarga de artefactos del trabajo correcto.

Empezá contra ejemplos del contrato mientras se verifica el motor; identificá
esas respuestas como simuladas. Después conectá el recorrido real de H1.
Un botón o una animación no demuestran que se haya generado un bordado.
Mostrá los datos del backend y diferenciá listo para prueba de muestra aprobada.

Usá React y TypeScript como propuesta inicial. Mantené la interfaz en español,
adaptada a varios tamaños de pantalla. Evitá pedir al usuario detalles de código.
Las credenciales de proveedores se administran en el backend.

No construyas otro motor de puntadas ni modifiques unilateralmente los contratos.
Entregá cambios revisables y pruebas de los recorridos, incluidos fallo y revisión.
```

## Mensaje listo para IA 3: visión y geometría

```text
Vas a generalizar el paso imagen → interpretación → geometría de la aplicación.

Leé el plan y el contrato. La coordinadora mantiene API/motor y otra IA hace la web.
El script original contiene coordenadas, pétalos y letras específicos de Anime
Socks; no alcanza con cambiar la ruta de entrada.

Tu módulo debe:
1. Implementar analyze(image, settings) → AnalysisSpec, con adaptadores separados
   para OpenAI y Ollama local y validación de sus respuestas.
2. Mantener proveedor/modelo/prompt/esquema como configuración y registrar consumos.
3. Localizar regiones y distinguir una estimación visual de una máscara comprobada.
4. Extraer siluetas para áreas y ejes centrales para líneas cuando corresponda.
5. Mantener huecos, identidad de texto y objetos separados.
6. Producir geometría para EmbroideryDocument, con unidades y trazabilidad.
7. Señalar ambigüedades mediante needs_review y objetos concretos.

Evaluá con imágenes nuevas, distintas resoluciones y ambos tamaños de Anime Socks.
Las coordenadas particulares pertenecen a los datos de un proyecto, no a reglas
codificadas para reconocer sus nombres. La IA devuelve datos estructurados; las
operaciones del servidor están implementadas y acotadas por el programa.

Entregá ejemplos de entrada/salida, fallos conocidos y mediciones de calidad,
latencia y recursos. No afirmes éxito general a partir de un solo logo ni entrenes
un modelo desde cero antes de probar los proveedores y algoritmos disponibles.
```

## Mensaje listo para IA revisora

```text
Revisá la entrega de la aplicación contra el plan, contratos y criterios de aceptación.
Tu revisión debe separar resultados observados de expectativas.

Comprobá:
- Recorrido real imagen/vector → motor → JEF releído → preview → descarga.
- Tamaños y densidades físicas al regenerar variantes.
- Texto, huecos, columnas satin y orden con precedencias.
- Conteos de saltos/cortes y compatibilidad declarada del bastidor.
- Manejo de trabajos simultáneos, fallos y proyectos de distintos usuarios.
- Que READY dependa de artefactos y validaciones reales.
- Que las limitaciones de IA y los avisos geométricos no estén ocultos.

Usá los fixtures existentes y casos nuevos. Documentá cada defecto con entrada,
pasos, resultado esperado, resultado observado y artefactos. Una segunda IA que
opina que el diseño se ve bien no sustituye comprobaciones ni muestras en tela.
```

## Parte de entrega que debe devolver cada IA

```text
Hito / tarea:
Versión de contratos utilizada:
Archivos y rama:
Qué funciona con entradas reales:
Qué utiliza datos simulados:
Comprobaciones ejecutadas y resultado:
Limitaciones o bloqueos:
Cambios que necesita de la otra IA:
Próximo paso compatible con el plan:
```
