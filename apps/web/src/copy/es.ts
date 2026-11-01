import { ArtifactKind } from '../contracts/artifacts';
import { JobStatus, StageState } from '../contracts/job';
import { SewoutStatus } from '../contracts/sewout';
import { Technique } from '../contracts/project';
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
  [JobStatus.Analyzing]: 'Análisis de la imagen',
  [JobStatus.Vectorizing]: 'Vectorización',
  [JobStatus.Digitizing]: 'Generación de puntadas',
  [JobStatus.Validating]: 'Verificación del archivo',
};

export const stageStateLabel: Record<StageState, string> = {
  [StageState.Pending]: 'Pendiente',
  [StageState.Running]: 'En curso',
  [StageState.Done]: 'Listo',
  [StageState.Skipped]: 'Omitida',
  [StageState.Failed]: 'Falló',
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
  [ArtifactKind.SvgEditable]: 'SVG editable',
  [ArtifactKind.SvgInkStitch]: 'SVG para Ink/Stitch',
  [ArtifactKind.Jef]: 'Archivo de bordado (JEF)',
  [ArtifactKind.JefPreview]: 'Vista previa del JEF',
  [ArtifactKind.Report]: 'Informe',
};

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
    jobs: (n: number) => (n === 1 ? '1 trabajo' : `${n} trabajos`),
  },
  upload: {
    title: '1. Imagen o SVG',
    choose: 'Elegir archivo',
    hint: (types: string, maxMb: string) => `Formatos admitidos: ${types}. Tamaño máximo: ${maxMb} MB.`,
    wrongType: 'Ese formato no está admitido. Probá con PNG, JPG o SVG.',
    tooBig: (maxMb: string) => `El archivo supera el máximo de ${maxMb} MB.`,
    uploading: 'Subiendo…',
    pixels: (w: number, h: number) => `${w} × ${h} píxeles (de la imagen, no del bordado)`,
    pickAsset: 'Imagen del proyecto',
    none: 'Subí una imagen para continuar.',
  },
  settings: {
    title: '2. Ajustes del bordado',
    width: 'Ancho máximo (mm)',
    height: 'Alto máximo (mm)',
    keepProportions: 'Conservar proporciones dentro del área indicada',
    machine: 'Máquina',
    hoop: 'Bastidor',
    fabric: 'Tela',
    colors: 'Cantidad de colores',
    provider: 'Análisis con',
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
    history: 'Trabajos anteriores',
    historyEmpty: 'Todavía no se generó ningún trabajo.',
    variantOf: 'Derivado de otro trabajo',
    open: 'Abrir',
  },
  progress: {
    title: 'Progreso',
    estimate: (s: number) => `Tiempo restante estimado: unos ${s} s (es una estimación).`,
    stageDuration: (s: string) => `${s} s medidos`,
    cancel: 'Cancelar generación',
    cancelling: 'Cancelando…',
    summary: (done: number, total: number) => `${done} de ${total} etapas completas`,
  },
  result: {
    readyTitle: 'Listo para prueba (digital)',
    readyText:
      'Los archivos se generaron y pasaron las comprobaciones digitales. Esto no significa que la muestra en tela esté aprobada.',
    sewoutTitle: 'Muestra física',
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
    downloadsTitle: 'Descargas',
    mismatch: 'Se descartaron archivos que no pertenecen a este trabajo.',
    issuesTitle: 'Avisos y comprobaciones',
    noIssues: 'No hay avisos para este trabajo.',
  },
  metrics: {
    size: 'Medida',
    stitches: 'Puntadas',
    blocks: 'Bloques de hilo',
    colorChanges: 'Cambios de color',
    jumps: 'Saltos',
    trims: 'Cortes',
    method: 'Método de conteo',
  },
  review: {
    title: 'Hay un elemento que necesita revisión',
    objects: 'Elementos',
    evidence: 'Qué se detectó',
    suggestion: 'Qué se sugiere',
    action: 'Qué querés hacer',
    keep: 'Sin cambios',
    setTechnique: 'Cambiar la técnica',
    exclude: 'Excluir del bordado',
    apply: 'Aplicar y regenerar',
    nothingChosen: 'Elegí al menos una corrección para regenerar.',
    marked: 'Zonas marcadas en la imagen original',
  },
  variants: {
    title: 'Variante de tamaño',
    text: 'Se regenera desde la geometría con el nuevo tamaño; no se reduce el archivo existente.',
    create: 'Generar variante',
  },
  errors: {
    generic: 'Ocurrió un problema. Probá de nuevo en unos instantes.',
    notFound: 'No encontramos lo que buscabas.',
  },
};
