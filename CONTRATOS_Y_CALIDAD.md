# Contratos y calidad — propuesta v0.1

Fecha: 1 de noviembre de 2026. Especificación para acordar antes de programar en paralelo. Los nombres de rutas y campos son propuestas, no una API ya implementada.

## 1. Documentos compartidos

| Documento | Lo produce | Contenido y reglas |
|---|---|---|
| `SourceAsset` | Carga de archivos | ID, hash, dimensiones en píxeles, formato, ubicación interna y transformaciones de recorte; conservar original |
| `JobSettings` | Usuario + perfiles | Tamaño en mm, modo de ajuste, máquina, bastidor, tela, hilo, paleta máxima y proveedor de IA |
| `AnalysisSpec` | Proveedor de visión | Regiones candidatas, función visual, texto observado, colores sugeridos, incertidumbres y referencias a la imagen |
| `EmbroideryDocument` | Geometría y reglas | Objetos con geometría editable, unidades, técnicas, parámetros físicos, dependencias y decisiones registradas |
| `StitchPlan` | Motor | Coordenadas, órdenes, bloques de hilo, límites, relación con objetos cuando el motor la permita |
| `ValidationReport` | Validadores | Errores, advertencias, mediciones, decisiones de revisión y referencias a objetos/zonas |
| `ArtifactManifest` | Worker | Archivos generados, hashes, formatos, versión del trabajo y métricas de relectura |
| `SewoutRecord` | Usuario después de la muestra | Tela, estabilizador, hilo, observaciones, fotografías opcionales y aprobación o cambios necesarios |

El esquema de cada documento se versiona. Las regiones estimadas por la IA se distinguen de máscaras y curvas comprobadas. El texto reconocido es una anotación de revisión; no se usa automáticamente como sustitución tipográfica del logo.

## 2. Coordenadas y tamaño

- La imagen original utiliza coordenadas de píxel y conserva su tamaño y recortes.
- La geometría de trabajo declara sus unidades; la conversión a milímetros tiene una transformación explícita y versionada.
- Los parámetros de separación, underlay, compensación y longitud de puntada se expresan en unidades físicas.
- La medida visible de una página SVG, los límites de sus objetos y los límites de puntadas son campos distintos.
- El modo de ajuste inicial es `contain`: conservar proporciones dentro del área indicada. Puede añadirse anchura o altura fija como opciones explícitas.
- La medida de salida se calcula sobre el JEF releído y se compara con la tolerancia del perfil del formato. Una variante se regenera desde la geometría, no reduciendo las coordenadas del JEF existente.

Ejemplo conceptual de solicitud, sin IDs inventados de archivos reales:

```json
{
  "schema_version": "0.1",
  "target": {
    "width_mm": 130,
    "height_mm": 120,
    "fit": "contain"
  },
  "machine_profile": "janome_mc550e",
  "fabric_profile": "gabardina_inicial",
  "color_limit": 3,
  "ai_provider": "openai"
}
```

Estos identificadores de perfiles se crearán como configuración del proyecto. No son opciones de línea de comandos de Ink/Stitch.

## 3. Objetos del documento de bordado

Cada objeto necesita un ID estable, geometría, rol, color de trabajo, técnica propuesta/efectiva y parámetros. Debe poder vincularse a una región del original.

Técnicas iniciales: `running`, `bean`, `satin`, `fill`. La capa que traduce esos nombres a atributos de Ink/Stitch es responsabilidad exclusiva del adaptador del motor.

Para satin conservar raíles y la forma de controlar su correspondencia: pares de nodos o guías válidas. Comprobar topología, direcciones y anchuras reales. Los trazos no aptos para satin pasan a una alternativa justificada o solicitan corrección; un umbral global no decide todos los materiales.

El orden de puntadas es un conjunto de precedencias, además de una lista final. Ejemplos: relleno antes del contorno que lo remata, base antes de cubierta y trayecto oculto antes del elemento que lo tapa. La reducción de cambios de hilo respeta esas condiciones aunque produzca más bloques del mismo color.

Los cambios conservan trazabilidad: objeto afectado, motivo, valor anterior, valor nuevo y origen —usuario, regla o propuesta de IA—.

## 4. Interfaz de proveedores

Operación conceptual: `analyze(image, settings, schema_version) -> AnalysisSpec`.

Cada adaptador comprueba capacidades del modelo seleccionado. OpenAI y Ollama no se tratan como APIs idénticas por compartir texto o JSON. Cada respuesta se traduce al contrato del proyecto y vuelve a validarse.

La aplicación maneja como resultados previstos: respuesta válida, rechazo, salida incompleta, esquema incorrecto, región incoherente, límite de servicio, fallo de conexión y modelo local no disponible. Una autovaloración de confianza del modelo no autoriza por sí sola un JEF.

Guardar la respuesta original y la normalizada. La caché se identifica por imagen, recorte, ajustes, proveedor/modelo y versión del prompt/esquema. Las métricas de consumo las informa el proveedor o se marcan como no disponibles.

## 5. API web propuesta

| Operación | Función |
|---|---|
| `POST /api/v1/projects` | Crear un proyecto accesible por su usuario |
| `POST /api/v1/projects/{id}/assets` | Subir una imagen o un SVG admitido |
| `POST /api/v1/projects/{id}/jobs` | Crear una generación con una versión inmutable de los ajustes |
| `GET /api/v1/jobs/{id}` | Consultar estado, etapa y diagnóstico disponible |
| `GET /api/v1/jobs/{id}/artifacts` | Obtener los artefactos permitidos y sus métricas |
| `POST /api/v1/jobs/{id}/cancel` | Solicitar cancelación y detener procesos asociados |
| `POST /api/v1/projects/{id}/revisions` | Guardar una corrección o una variante y relacionarla con su origen |
| `POST /api/v1/projects/{id}/sewouts` | Registrar una muestra física |

Definir autenticación, errores y descargas autorizadas en OpenAPI antes de conectar la interfaz real. La primera interfaz puede consultar el estado periódicamente; añadir actualizaciones en vivo solo si hacen falta.

Una solicitud repetida debe poder usar una clave de idempotencia. No debe duplicar generación ni llamadas de IA al reintentar una conexión.

## 6. Estados del trabajo

`queued → analyzing → vectorizing → digitizing → validating → ready_for_sewout`.

El estado puede pasar a `needs_review`, `failed` o `cancelled`. Una entrada SVG ya preparada puede omitir análisis y vectorización, registrando esas etapas como omitidas.

`needs_review` incluye una causa y objetos o regiones concretos. La corrección crea una revisión relacionada; los artefactos anteriores no se sobrescriben como si fueran el mismo resultado.

`ready_for_sewout` exige archivos reales y controles digitales satisfactorios. La interfaz no puede activarlo mediante una bandera enviada por el cliente. La aprobación física se guarda aparte: `untested`, `approved` o `needs_adjustment`.

Los porcentajes de progreso derivan de etapas observadas. Las estimaciones de tiempo se distinguen de los tiempos medidos.

## 7. Validaciones y severidades

Cada incidencia contiene `code`, `severity`, `stage`, `object_ids`, descripción, evidencia y corrección sugerida. Las severidades son error bloqueante, revisión necesaria y aviso informativo. No reutilizar una misma lista global de avisos aceptados para todos los diseños.

| Control | Qué comprueba | Consecuencia |
|---|---|---|
| Entrada | Formato, tamaño admitido, dimensiones y contenido legible | Rechazar entrada ilegible o pedir mejor referencia |
| Interpretación | Regiones, texto y elementos que podrían perderse | Marcar incertidumbres y permitir corrección localizada |
| Geometría | Huecos, cruces, duplicados y áreas degeneradas | Reparar con registro; detener si la reparación modifica de forma dudosa la identidad |
| Satin | Correspondencia de raíles, dirección, guías si existen y ancho físico | Corregir o proponer otra técnica |
| Recorrido | Precedencias, trayectos visibles, amarres y cortes | Reordenar dentro de restricciones; no sacrificar estabilidad para bajar métricas |
| Dimensiones | Límites de puntadas en mm y margen de compensación | Recalcular cuando se excede el destino |
| Bastidor | Tamaño físico y código/cabecera del formato | Distinguir encaje geométrico de compatibilidad declarada y prueba en máquina |
| Archivo | Tabla, longitud, órdenes conocidas y fin válido | Bloquear salida defectuosa |
| Comparación visual | Original, vector y representación desde JEF | Localizar pérdidas, cierres y deformaciones |
| Tela | Resultado de la muestra física | Aprobar un perfil o generar una corrección, sin atribuir ese resultado a la simulación |

En Anime Socks se aceptaron avisos de ausencia de guías en columnas con nodos correspondientes. En la aplicación esa decisión requiere comprobar el tipo de construcción de la columna; no basta con ignorar el texto del aviso.

Los conteos de densidad local son indicadores de zonas para inspeccionar. Incluyen amarres y bordes; su umbral debe calibrarse por perfil y no presentarse como prueba de ausencia de fruncido.

## 8. Métricas verificables y reproducibilidad

Medir después de exportar y releer: ancho/alto, puntadas de aguja, bloques de hilo, cambios de color, saltos, cortes interpretados, longitudes y duración del procesamiento. Guardar también el método de conteo y los comandos crudos necesarios para auditarlo.

En JEF, los tripletes de saltos cero utilizados para codificar cortes se distinguen de saltos de desplazamiento. La ejecución del corte en la máquina se verifica por separado. La paleta visual de trabajo y la aproximación del catálogo del formato también se conservan como datos distintos.

Guardar hashes de entradas, geometría, configuración, modelo/prompt, versiones del motor y artefactos. La fecha de cabecera del JEF puede cambiar su hash sin cambiar las puntadas; una prueba de regresión compara además las órdenes y coordenadas normalizadas, con tolerancia definida.

## 9. Contrato entre las IAs desarrolladoras

La IA coordinadora mantiene el esquema, OpenAPI y las decisiones de arquitectura. Las otras IAs consumen una versión identificada y proponen cambios de contrato con un ejemplo y su impacto. Tras acordarlos, se actualizan juntos backend, frontend y pruebas.

Las pruebas de la interfaz pueden usar respuestas simuladas identificadas como tales. La aceptación del recorrido completo requiere un JEF producido por el worker y releído por el validador.
