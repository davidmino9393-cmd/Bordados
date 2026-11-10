import { ArtifactKind } from '../contracts/artifacts';
import { JobStatus, StageOutcome } from '../contracts/job';
import { Technique } from '../contracts/project';
import { SewoutStatus } from '../contracts/sewout';
import { Severity } from '../contracts/validation';

export const jobStatusLabel: Record<JobStatus, string> = {
  [JobStatus.Queued]: 'En cola',
  [JobStatus.Analyzing]: 'Analizando la imagen',
  [JobStatus.Vectorizing]: 'Vectorizando',
  [JobStatus.Digitizing]: 'Generando las puntadas',
  [JobStatus.Validating]: 'Verificando el archivo',
  [JobStatus.ReadyForSewout]: 'Listo para prueba (digital)',
  [JobStatus.NeedsReview]: 'Necesita tu revisión',
  [JobStatus.Failed]: 'Falló',
  [JobStatus.Cancelled]: 'Cancelado',
};

export const stageLabel: Record<string, string> = {
  queued: 'En cola',
  [JobStatus.Analyzing]: 'Análisis de la imagen',
  [JobStatus.Vectorizing]: 'Vectorización',
  [JobStatus.Digitizing]: 'Generación de puntadas',
  [JobStatus.Validating]: 'Verificación del archivo',
};

export const stageOutcomeLabel: Record<StageOutcome, string> = {
  [StageOutcome.Pending]: 'Pendiente',
  [StageOutcome.Running]: 'En curso',
  [StageOutcome.Completed]: 'Listo',
  [StageOutcome.Skipped]: 'Omitida',
  [StageOutcome.Failed]: 'Falló',
  [StageOutcome.Cancelled]: 'Detenida',
};

export const sewoutLabel: Record<SewoutStatus, string> = {
  [SewoutStatus.Untested]: 'Sin probar en tela',
  [SewoutStatus.Approved]: 'Muestra física aprobada',
  [SewoutStatus.NeedsAdjustment]: 'La muestra requiere ajustes',
};

export const severityLabel: Record<Severity, string> = {
  [Severity.Blocking]: 'Error',
  [Severity.ReviewRequired]: 'Revisión necesaria',
  [Severity.Info]: 'Aviso',
};

export const techniqueLabel: Record<Technique, string> = {
  [Technique.Running]: 'Línea simple (running)',
  [Technique.Bean]: 'Línea reforzada (bean)',
  [Technique.Satin]: 'Satén (satin)',
  [Technique.Fill]: 'Relleno (fill)',
};

export const artifactKindLabel: Record<ArtifactKind, string> = {
  [ArtifactKind.Jef]: 'Archivo de bordado (JEF)',
  [ArtifactKind.EditableSvg]: 'SVG editable',
  [ArtifactKind.InkStitchSvg]: 'SVG para Ink/Stitch',
  [ArtifactKind.PreviewPng]: 'Vista previa del JEF',
  [ArtifactKind.ValidationJson]: 'Informe de validación',
  [ArtifactKind.StitchPlanJson]: 'Plan de puntadas',
  [ArtifactKind.RawCommandsJson]: 'Órdenes crudas del JEF',
  [ArtifactKind.ProviderRawJson]: 'Respuesta original de la IA',
};

/** Títulos en español por código del catálogo de incidencias (issue-catalog.json). */
const issueTitles: Record<string, string> = {
  INPUT_UNSUPPORTED_FORMAT: 'Formato de imagen no admitido',
  INPUT_UNREADABLE: 'No se pudo leer la imagen',
  INPUT_TOO_LARGE: 'La imagen supera los límites configurados',
  ANALYSIS_REFUSED: 'El proveedor de IA rechazó el análisis',
  ANALYSIS_INCOMPLETE: 'El análisis de IA quedó incompleto',
  ANALYSIS_SCHEMA_INVALID: 'La respuesta de la IA no tiene el formato esperado',
  ANALYSIS_REGION_INCOHERENT: 'Una región detectada no coincide con la imagen',
  PROVIDER_RATE_LIMITED: 'El proveedor de IA alcanzó su límite de uso',
  PROVIDER_UNAVAILABLE: 'El proveedor de IA elegido no está disponible',
  LOCAL_MODEL_UNAVAILABLE: 'El modelo local no está disponible',
  GEOMETRY_INVALID: 'Hay una geometría inválida o degenerada',
  GEOMETRY_REPAIR_AMBIGUOUS: 'Revisá que el fondo se haya quitado bien',
  GEOMETRY_HOLES_CHANGED: 'La reparación modificó huecos del diseño',
  SATIN_RAILS_UNVERIFIED: 'No se pudo verificar la correspondencia de los bordes del satén',
  SATIN_WIDTH_UNSUPPORTED: 'El ancho del satén está fuera de lo calibrado',
  SATIN_RUNG_WARNING: 'Faltan guías en una columna de satén',
  SATIN_PAIRED_NODES_VERIFIED: 'Satén verificado por nodos correspondientes',
  ROUTING_PRECEDENCE_VIOLATION: 'Se violó un orden obligatorio de bordado',
  ROUTING_VISIBLE_TRAVEL: 'Hay desplazamientos visibles entre elementos',
  DENSITY_REVIEW_REQUIRED: 'Probá el bordado antes de usarlo en la pieza final',
  DIMENSIONS_EXCEEDED: 'La medida real supera el tamaño pedido',
  HOOP_INCOMPATIBLE: 'El diseño no es compatible con el bastidor elegido',
  JEF_INVALID: 'El archivo JEF generado no es válido',
  JEF_UNKNOWN_COMMAND: 'El JEF contiene una orden desconocida',
  ENGINE_DIAGNOSTIC_UNCLASSIFIED: 'Observación técnica del programa de bordado',
  WORKER_EXPORT_FAILED: 'Falló la exportación del bordado',
  WORKER_TIMEOUT: 'La generación superó el tiempo máximo',
  JOB_CANCELLED: 'Generación cancelada',
  VISUAL_MISMATCH: 'El bordado no es idéntico a tu imagen',
  PHYSICAL_ADJUSTMENT_REQUIRED: 'La muestra física requiere ajustes',
};

export function issueTitle(code: string, fallback: string): string {
  return issueTitles[code] ?? fallback;
}

/** Qué significa el aviso para quien borda y qué conviene hacer, sin términos del motor. Sin entrada: solo el título. */
const issueAdvice: Record<string, string> = {
  DENSITY_REVIEW_REQUIRED: 'Las puntadas usan valores generales, no ajustados a tu tela. Probá el bordado en un retazo antes de la pieza final.',
  GEOMETRY_REPAIR_AMBIGUOUS: 'El fondo se separó del dibujo de forma automática. Compará las vistas: si falta una parte o sobra fondo, usá una imagen con fondo liso o transparente.',
  VISUAL_MISMATCH: 'Para poder bordarlo se simplificaron colores o se quitaron detalles muy chicos. Compará el bordado con tu imagen.',
  ENGINE_DIAGNOSTIC_UNCLASSIFIED: 'El programa de bordado dejó una observación sobre la forma de alguna pieza. No suele impedir bordar: mirá la vista del bordado.',
  HOOP_INCOMPATIBLE: 'El bordado no entra en el bastidor elegido con el margen de seguridad. Elegí un tamaño menor.',
  DIMENSIONS_EXCEEDED: 'El bordado salió más grande que el tamaño pedido.',
  SATIN_RUNG_WARNING: 'Una columna de satén no tiene guías de dirección. Revisá esa pieza en la vista del bordado.',
};

export function issueAdviceFor(code: string): string | undefined {
  return issueAdvice[code];
}

export const es = {
  loadingMore: 'Cargando…',
  appName: 'Bordados con IA',
  simulationBanner:
    'Datos simulados: lo que ves no proviene del servidor real ni es un bordado generado.',
  loading: 'Cargando…',
  retry: 'Reintentar',
  back: 'Volver',
  projects: {
    title: 'Proyectos',
    empty: 'Todavía no hay proyectos. Creá el primero para empezar.',
    newLabel: 'Nombre del proyecto',
    create: 'Crear proyecto',
    nameRequired: 'Escribí un nombre para el proyecto.',
    createdOn: (date: string) => `Creado el ${date}`,
    more: 'Ver más proyectos',
  },
  upload: {
    title: '1. Imagen o SVG',
    choose: 'Elegir archivo',
    hint: (types: string, maxMb: string) => `Formatos admitidos: ${types}. Tamaño máximo: ${maxMb} MB.`,
    wrongType: 'Ese formato no está admitido. Probá con PNG, JPG o SVG.',
    tooBig: (maxMb: string) => `El archivo supera el máximo de ${maxMb} MB.`,
    uploading: 'Subiendo…',
    pixels: (w: number, h: number) => `${w} × ${h} píxeles (de la imagen, no del bordado)`,
    pixelsUnknown: 'Sin medida en píxeles (SVG)',
    preparedBadge: 'SVG preparado',
    preparedText: 'Va directo a la generación del bordado.',
    imageBadge: 'Imagen para analizar',
    imageText: 'Primero la analiza una IA; vas a poder revisar ese análisis antes de generar el bordado.',
    pickAsset: 'Imagen del proyecto',
    moreAssets: 'Ver más imágenes',
    none: 'Subí una imagen para continuar.',
    unavailable: 'La vista previa del original no está disponible.',
  },
  legibility: {
    measuring: 'Midiendo el ancho de trazo al tamaño pedido…',
    unavailable: 'No se pudo medir la legibilidad de la imagen. Es solo un aviso: podés generar igual.',
    warnTitle: 'Aviso de legibilidad',
    infoTitle: 'Legibilidad al tamaño pedido',
    notBlocking: 'Es un aviso con números, no un bloqueo: podés generar igual.',
    belowLimit: (percent: number) => `El ${percent}% del trazo mide menos de 0,6 mm (se avisa a partir del 30%).`,
    method: 'Cómo se mide',
    methodText: 'Ancho de trazo a tamaño final, medido sobre la imagen con el borde suavizado ya fusionado con su color. Es una estimación: en trazos diagonales exagera la finura hasta 1,4 veces.',
    marginTitle: 'Opción de ajuste: recortar el margen blanco',
  },
  inscriptions: {
    searching: 'Buscando texto en la imagen… La primera vez tarda unos segundos.',
    failed: 'No se pudo buscar texto en la imagen. Es solo un aviso: podés generar igual.',
    unavailable: 'La búsqueda de texto no está instalada en este servidor.',
    title: 'Texto encontrado en la imagen',
    intro:
      'Confirmá o corregí cada frase tal como tiene que quedar bordada. Se guarda con la imagen para la variante con letras de bordado, que llega en una próxima etapa.',
    fieldLabel: (curved: boolean, mm: string | null) =>
      `${curved ? 'Texto en curva' : 'Texto'}${mm ? ` (letras de ~${mm} mm de alto)` : ''}`,
    small: (limit: string) => `Las letras de menos de ${limit} mm se pierden al trazarlas: conviene bordar esta frase con letras de bordado.`,
    confidence: (percent: number) => `Leído con ${percent}% de confianza.`,
    confirm: 'Confirmar frases',
    saving: 'Guardando…',
    saved: 'Frases confirmadas y guardadas con la imagen.',
    saveFailed: 'No se pudieron guardar las frases. Probá de nuevo.',
  },
  settings: {
    title: '2. Ajustes del bordado',
    limit: (w: string, h: string) =>
      `Área máxima del bastidor: ${w} × ${h} mm. El límite lo fija el bastidor y el diseño no se escala al cambiarlo.`,
    width: 'Ancho máximo (mm)',
    height: 'Alto máximo (mm)',
    machine: 'Máquina',
    hoop: 'Bastidor',
    fabric: 'Tela',
    colors: 'Cantidad de colores',
    provider: 'Análisis con',
    noFallback: 'No se usará otro proveedor en su lugar.',
    experimentalTitle: 'Función experimental',
    experimentalText:
      'Convertir una imagen en bordado es experimental y puede equivocarse. Los parámetros de puntada son de referencia, no están calibrados para tu tela: revisá los avisos y probalo en un retazo antes de bordar. Si elegís un análisis con IA, vas a poder revisar lo que detectó.',
    noAi: 'Sin análisis de IA',
    noAiHint: 'La imagen se vectoriza directamente, sin regiones sugeridas por la IA.',
    noProviders: 'El servidor no tiene proveedores de IA disponibles: la imagen se va a procesar sin análisis.',
    noAiForSvg: 'Un SVG ya preparado no se analiza con IA.',
    positive: 'Ingresá un número mayor que cero.',
    colorsRange: (max: number) => `Elegí entre 1 y ${max} colores.`,
    outsideHoop: (w: number, h: number) =>
      `El área indicada es mayor que el bastidor (${w} × ${h} mm). Se genera igual, pero no entra en este bastidor: el resultado queda para revisar.`,
    estimate: (w: string, h: string) =>
      `Tamaño estimado: ${w} × ${h} mm. El tamaño real se mide al releer el archivo generado.`,
    preparedSvgSize:
      'Un SVG preparado se borda al tamaño con el que se preparó: el bastidor es solo el límite (si el dibujo es más grande, el trabajo se rechaza con «el diseño no es compatible con el bastidor»). Para otro tamaño, pedí una «Variante de tamaño» desde el resultado.',
    submit: 'Generar bordado',
    submitting: 'Enviando…',
    needAsset: 'Primero subí una imagen.',
  },
  jobs: {
    title: 'Generación del bordado',
    history: 'Trabajos anteriores',
    historyEmpty: 'Todavía no se generó ningún trabajo.',
    historyMore: 'Ver más trabajos',
    variantOf: 'Derivado de otro trabajo',
    open: 'Abrir',
  },
  progress: {
    title: 'Progreso',
    estimate: (s: number) => `Tiempo restante estimado: unos ${s} s (es una estimación).`,
    stageDuration: (s: string) => `${s} s medidos`,
    cancel: 'Cancelar generación',
    cancelling: 'Cancelando…',
    retryingIn: (s: number) => `Reintentando en ${s} s…`,
    cancelRequested: 'Cancelación solicitada. Esperando a que el servidor detenga el proceso…',
    summary: (done: number, total: number) => `${done} de ${total} etapas completas`,
  },
  result: {
    readyTitle: 'Listo para prueba (digital)',
    readyText:
      'Los archivos se generaron y pasaron las comprobaciones digitales. Esto no significa que la muestra en tela esté aprobada.',
    sewoutTitle: 'Muestra física',
    sewoutTestedOn: (date: string) => `Probada el ${date}`,
    cancelledTitle: 'Generación cancelada',
    cancelledText: 'Se detuvo antes de terminar. No hay archivos para descargar de este trabajo.',
    failedTitle: 'No se pudo generar el bordado',
    incidentCode: (code: string) => `Código de incidencia: ${code}`,
    failedAt: (stage: string) => `Falló en la etapa: ${stage}.`,
    retrySame: 'Reintentar con los mismos ajustes',
    compareTitle: 'Comparación',
    compareHint: 'Tocá una vista para ampliarla. El fondo cuadriculado marca las zonas sin dibujo.',
    zoomIn: (label: string) => `Ampliar: ${label}`,
    zoomClose: 'Cerrar ampliación',
    original: 'Original',
    vector: 'Vector',
    jefPreview: 'Puntadas del archivo releído',
    metricsTitle: 'Medidas del archivo generado',
    metricsNote: 'Medidas tomadas releyendo el archivo JEF.',
    trimsNote: 'Los cortes son los interpretados del archivo; su ejecución en la máquina no está verificada.',
    downloadsTitle: 'Descargas',
    download: 'Descargar',
    technicalFiles: 'Archivos técnicos',
    linkNote: 'Los enlaces de descarga vencen a los 5 minutos; se renuevan solos.',
    renewing: 'Renovando el enlace de descarga…',
    filesUnavailable: 'No se pudieron obtener los archivos. Reintentá.',
    retryFiles: 'Reintentar',
    retryingFiles: 'Reintentando…',
    mismatch: 'Se descartaron archivos que no pertenecen a este trabajo.',
    issuesTitle: 'Avisos y comprobaciones',
    noIssues: 'No hay avisos para este trabajo.',
  },
  metrics: {
    size: 'Medida',
    stitches: 'Puntadas',
    colorChanges: 'Cambios de color',
    displacementJumps: 'Saltos de desplazamiento',
    trims: 'Cortes (interpretados)',
    maxStitch: 'Puntada más larga',
    method: 'Método de conteo',
  },
  review: {
    title: 'Hay un elemento que necesita revisión',
    objects: 'Elementos',
    regions: 'Zonas',
    evidence: 'Qué se detectó',
    details: 'Detalles técnicos',
    code: 'Código',
    suggestion: 'Qué se sugiere',
    action: 'Qué querés hacer',
    keep: 'Sin cambios',
    setTechnique: 'Cambiar la técnica',
    exclude: 'Excluir del bordado',
    apply: 'Aplicar y regenerar',
    nothingChosen: 'Elegí al menos una corrección para regenerar.',
    originalRef: 'Original para consultar',
    filesNotReadyTitle: 'Archivos para revisar: no están listos para prueba',
    filesNotReadyText:
      'Los controles digitales no pasaron. Podés inspeccionarlos o registrar una muestra, pero resolvé las incidencias antes de usarlos como versión final.',
    jefHeroTitle: 'Archivo de bordado: todavía no está validado para coser',
    jefHeroText:
      'El JEF se generó, pero sus parámetros de puntada son de referencia y no están calibrados para tu tela. No es una versión final: cosé una prueba en un retazo y revisá los controles y avisos de abajo.',
    jefHeroDownload: 'Descargar JEF (con avisos)',
    gateDigitalFailed: 'Controles digitales: NO pasaron.',
    gateDigitalNoReport: 'Controles digitales: no hay informe, así que no se puede afirmar que pasaron.',
    gateDigitalPassed: 'Controles digitales: pasaron.',
    gatePhysicalUntested: 'Aprobación física: sin probar (ninguna muestra cosida aprobada).',
    gatePhysicalNeedsAdjustment: 'Aprobación física: la muestra requiere ajustes.',
    gatePhysicalApproved: 'Aprobación física: muestra aprobada.',
    gateChecksTitle: 'Controles',
    checkKind: {
      file: 'Archivo',
      dimensions: 'Dimensiones',
      hoop: 'Bastidor',
      geometry: 'Geometría',
      satin: 'Satén',
      routing: 'Recorrido',
      visual: 'Comparación visual',
    } as Record<string, string>,
    checkOutcome: {
      passed: 'pasó',
      failed: 'FALLÓ',
      needs_review: 'requiere revisión',
      not_run: 'NO SE EJECUTÓ',
    } as Record<string, string>,
    legibilityTitle: 'Riesgo de legibilidad',
    legibilityTechniques: 'Técnica por objeto',
    legibilityNoTechnique: 'Esta versión del motor todavía no informa la técnica de cada objeto en la incidencia.',
    confirmDownload: (pending: string) =>
      `Entiendo que el archivo no está listo para coser: faltan o no pasaron estos controles (${pending}) y no hay muestra aprobada.`,
    confirmDownloadNoReport: 'Entiendo que el archivo no está listo para coser: no hay informe de controles y no hay muestra aprobada.',
    confirmDownloadUnapproved: 'Entiendo que el archivo no está listo para coser: no hay una muestra física aprobada.',
    downloadLocked: 'Marcá la confirmación para habilitar la descarga.',
    geometryOnlyTitle: 'Solo geometría: todavía no hay archivo de bordado',
    geometryOnlyText:
      'Se vectorizó la imagen y podés descargar el SVG editable. Las puntadas y el JEF no se generan hasta que se validen los parámetros físicos; por eso no hay muestra para registrar ni correcciones para aplicar.',
  },
  sewout: {
    title: 'Registrar muestra física',
    intro: 'Anotá el resultado de coser una muestra real. Esto no cambia el estado digital del archivo.',
    result: 'Resultado de la muestra',
    options: {
      approved: 'Aprobada',
      needs_adjustment: 'Requiere ajustes',
      untested: 'Sin probar (solo dejar constancia)',
    },
    testedAt: 'Fecha de la muestra',
    noDateIfUntested: 'Una muestra sin probar no lleva fecha.',
    fabric: 'Tela usada',
    stabilizer: 'Estabilizador',
    thread: 'Hilo',
    observations: 'Observaciones',
    photos: 'Fotos de la muestra (opcional)',
    photosHint: (max: number) => `PNG o JPG, hasta ${max} fotos. No se usan para bordar.`,
    photosTitle: 'Fotos de la muestra',
    photoAlt: 'Foto de la muestra',
    uploadingPhotos: 'Subiendo fotos…',
    removePhoto: 'Quitar',
    tooManyPhotos: (max: number) => `Podés agregar hasta ${max} fotos por muestra.`,
    photoType: 'Las fotos deben ser PNG o JPG.',
    submit: 'Registrar muestra',
    submitting: 'Registrando…',
    saved: 'Muestra registrada. El estado digital del archivo no cambió.',
    errors: {
      required: 'Completá este dato.',
      future: 'La fecha no puede ser futura.',
      tooLong: 'El texto es demasiado largo.',
    },
  },
  analysis: {
    title: 'Revisá el análisis de la imagen',
    attentionTitle: (n: number) =>
      n === 1 ? 'La IA no está segura de 1 zona' : `La IA no está segura de ${n} zonas`,
    estimated:
      'Las cajas y los textos los estimó la IA y no están verificados: sirven de guía, no son el trazado final.',
    analyzedWith: (provider: string, model: string, seconds: string) =>
      `Analizado con ${provider} (${model}) en ${seconds} s.`,
    originalAlt: 'Imagen original con las zonas detectadas',
    uncertain: 'Incierta',
    detectedText: 'Texto detectado',
    noText: 'ninguno',
    colors: 'Colores sugeridos',
    flag: (role: string) => `Marcar «${role}» para revisión manual`,
    flaggedCount: (n: number) =>
      n === 1 ? '1 zona marcada para revisión manual.' : `${n} zonas marcadas para revisión manual.`,
    approve: 'Aprobar el análisis y continuar',
    otherProvider: 'Probar con otro proveedor',
    noOtherProvider: 'No hay otro proveedor de IA disponible.',
    regenerate: 'Regenerar con otro proveedor',
  },
  variants: {
    title: 'Variante de tamaño',
    text: 'Se regenera desde la geometría con el nuevo tamaño; no se reduce el archivo existente.',
    create: 'Generar variante',
  },
  errors: {
    generic: 'Ocurrió un problema. Probá de nuevo en unos instantes.',
    notFound: 'No encontramos lo que buscabas.',
    timeout: 'El servidor tardó demasiado en responder. Probá de nuevo en unos instantes.',
    incident: (code: string, requestId?: string) =>
      `(Código de incidencia: ${code}${requestId ? ` · solicitud ${requestId}` : ''})`,
    network: 'No pudimos comunicarnos con el servidor. Revisá la conexión y probá de nuevo.',
    notImplemented: 'El servidor todavía no ofrece esta operación. El resto de la pantalla sigue disponible.',
    byCode: {
      MALFORMED_REQUEST: 'La solicitud no tiene el formato esperado.',
      UNAUTHENTICATED: 'Necesitás iniciar sesión para continuar.',
      FORBIDDEN: 'No tenés permiso para ver o modificar esto.',
      NOT_FOUND: 'No encontramos lo que buscabas.',
      IDEMPOTENCY_CONFLICT: 'Ese envío ya se había hecho con otros datos. Volvé a intentarlo desde cero.',
      REVISION_CONFLICT: 'Los ajustes cambiaron desde otra sesión. Recargá y probá de nuevo.',
      ARTIFACTS_UNAVAILABLE: 'Los archivos de este trabajo todavía no están disponibles.',
      PAYLOAD_TOO_LARGE: 'El archivo es demasiado grande.',
      UNSUPPORTED_MEDIA_TYPE: 'Ese formato de archivo no está admitido.',
      INVALID_REQUEST: 'El servidor no aceptó algunos datos. Revisá los ajustes.',
      RATE_LIMITED: 'Hay demasiadas solicitudes. Esperá un momento y probá de nuevo.',
      INTERNAL_ERROR: 'El servidor tuvo un problema. Probá de nuevo en unos instantes.',
      SERVICE_UNAVAILABLE: 'El servicio no está disponible en este momento.',
    } as Record<string, string>,
  },
};
