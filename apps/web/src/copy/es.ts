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
  GEOMETRY_REPAIR_AMBIGUOUS: 'Reparar la geometría podría cambiar la forma del elemento',
  GEOMETRY_HOLES_CHANGED: 'La reparación modificó huecos del diseño',
  SATIN_RAILS_UNVERIFIED: 'No se pudo verificar la correspondencia de los bordes del satén',
  SATIN_WIDTH_UNSUPPORTED: 'El ancho del satén está fuera de lo calibrado',
  SATIN_RUNG_WARNING: 'Faltan guías en una columna de satén',
  SATIN_PAIRED_NODES_VERIFIED: 'Satén verificado por nodos correspondientes',
  ROUTING_PRECEDENCE_VIOLATION: 'Se violó un orden obligatorio de bordado',
  ROUTING_VISIBLE_TRAVEL: 'Hay desplazamientos visibles entre elementos',
  DENSITY_REVIEW_REQUIRED: 'Una zona densa necesita revisión',
  DIMENSIONS_EXCEEDED: 'La medida real supera el tamaño pedido',
  HOOP_INCOMPATIBLE: 'El diseño no es compatible con el bastidor elegido',
  JEF_INVALID: 'El archivo JEF generado no es válido',
  JEF_UNKNOWN_COMMAND: 'El JEF contiene una orden desconocida',
  ENGINE_DIAGNOSTIC_UNCLASSIFIED: 'El motor informó un aviso sin clasificar',
  WORKER_EXPORT_FAILED: 'Falló la exportación del bordado',
  WORKER_TIMEOUT: 'La generación superó el tiempo máximo',
  JOB_CANCELLED: 'Generación cancelada',
  VISUAL_MISMATCH: 'El resultado difiere del original',
  PHYSICAL_ADJUSTMENT_REQUIRED: 'La muestra física requiere ajustes',
};

export function issueTitle(code: string, fallback: string): string {
  return issueTitles[code] ?? fallback;
}

export const es = {
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
    more: 'Hay más proyectos que no se muestran todavía.',
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
    pickAsset: 'Imagen del proyecto',
    none: 'Subí una imagen para continuar.',
    unavailable: 'La vista previa del original no está disponible.',
  },
  settings: {
    title: '2. Ajustes del bordado',
    width: 'Ancho máximo (mm)',
    height: 'Alto máximo (mm)',
    keepProportions: 'Conservar proporciones dentro del área indicada',
    machine: 'Máquina',
    hoop: 'Bastidor',
    fabric: 'Tela',
    thread: 'Hilo',
    colors: 'Cantidad de colores',
    provider: 'Análisis con',
    noFallback: 'No se usará otro proveedor en su lugar.',
    noAiForSvg: 'Un SVG ya preparado no se analiza con IA.',
    positive: 'Ingresá un número mayor que cero.',
    colorsRange: (max: number) => `Elegí entre 1 y ${max} colores.`,
    outsideHoop: (w: number, h: number) =>
      `El área indicada es mayor que el bastidor (${w} × ${h} mm). Podés continuar: el servidor confirmará el encaje.`,
    estimate: (w: string, h: string) =>
      `Tamaño estimado: ${w} × ${h} mm. El tamaño real se mide al releer el archivo generado.`,
    submit: 'Generar bordado',
    submitting: 'Enviando…',
    needAsset: 'Primero subí una imagen.',
  },
  jobs: {
    title: 'Generación del bordado',
    history: 'Trabajos anteriores',
    historyEmpty: 'Todavía no se generó ningún trabajo.',
    historyMore: 'Hay trabajos anteriores que no se muestran todavía.',
    variantOf: 'Derivado de otro trabajo',
    open: 'Abrir',
  },
  progress: {
    title: 'Progreso',
    estimate: (s: number) => `Tiempo restante estimado: unos ${s} s (es una estimación).`,
    stageDuration: (s: string) => `${s} s medidos`,
    cancel: 'Cancelar generación',
    cancelling: 'Cancelando…',
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
    failedAt: (stage: string) => `Falló en la etapa: ${stage}.`,
    retrySame: 'Reintentar con los mismos ajustes',
    compareTitle: 'Comparación',
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
    mismatch: 'Se descartaron archivos que no pertenecen a este trabajo.',
    issuesTitle: 'Avisos y comprobaciones',
    noIssues: 'No hay avisos para este trabajo.',
  },
  metrics: {
    size: 'Medida',
    stitches: 'Puntadas',
    blocks: 'Bloques de hilo',
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
    suggestion: 'Qué se sugiere',
    action: 'Qué querés hacer',
    keep: 'Sin cambios',
    setTechnique: 'Cambiar la técnica',
    exclude: 'Excluir del bordado',
    apply: 'Aplicar y regenerar',
    nothingChosen: 'Elegí al menos una corrección para regenerar.',
    originalRef: 'Original para consultar',
  },
  variants: {
    title: 'Variante de tamaño',
    text: 'Se regenera desde la geometría con el nuevo tamaño; no se reduce el archivo existente.',
    create: 'Generar variante',
  },
  errors: {
    generic: 'Ocurrió un problema. Probá de nuevo en unos instantes.',
    notFound: 'No encontramos lo que buscabas.',
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
