import type { AnalysisDecision, AnalysisSpec } from '../contracts/analysis';
import type { AuthorizedArtifactManifest } from '../contracts/artifacts';
import type { JobCreate, JobResponse } from '../contracts/job';
import type {
  DerivedRevisionRequest,
  InitialRevisionRequest,
  ProjectDetail,
  ProjectList,
  ProjectResponse,
  RevisionResponse,
  SourceAsset,
} from '../contracts/project';
import type { SewoutRecordRequest, SewoutResponse } from '../contracts/sewout';
import type { ProfileCatalog } from '../contracts/settings';

/** Códigos propios del cliente, además de los ErrorCode del contrato. */
export const ClientErrorCode = {
  Network: 'NETWORK',
  Timeout: 'TIMEOUT',
  NotImplemented: 'NOT_IMPLEMENTED',
  Unexpected: 'UNEXPECTED',
} as const;

export class ApiError extends Error {
  constructor(
    /** ErrorCode del contrato o ClientErrorCode. */
    public readonly code: string,
    message: string,
    public readonly status?: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const TRANSIENT_CODES: readonly string[] = [
  ClientErrorCode.Network,
  ClientErrorCode.Timeout,
  'SERVICE_UNAVAILABLE',
  'INTERNAL_ERROR',
  'RATE_LIMITED',
];

/** Errores que pueden resolverse solos: tiene sentido reintentar la consulta. */
export function isTransientError(error: unknown): boolean {
  return error instanceof ApiError && TRANSIENT_CODES.includes(error.code);
}

/**
 * Superficie que la web consume (openapi.json). Todos los POST aceptan una clave
 * de idempotencia; si se omite, el cliente genera una. Reutilizar la clave al
 * reintentar el mismo envío evita duplicar proyectos, revisiones y trabajos.
 */
export interface ApiClient {
  /** true cuando las respuestas son simuladas. La UI lo muestra siempre. */
  readonly isSimulated: boolean;
  getProfiles(): Promise<ProfileCatalog>;
  listProjects(): Promise<ProjectList>;
  createProject(name: string, idempotencyKey?: string): Promise<ProjectResponse>;
  getProject(projectId: string): Promise<ProjectDetail>;
  uploadAsset(projectId: string, file: File, idempotencyKey?: string): Promise<SourceAsset>;
  /** Paso 3 del flujo inicial: `base_revision_id: null`. */
  createInitialRevision(
    projectId: string,
    request: InitialRevisionRequest,
    idempotencyKey?: string,
  ): Promise<RevisionResponse>;
  /** Paso 4: exige el `revision_id` creado antes; no hay revisión implícita. */
  createJob(projectId: string, request: JobCreate, idempotencyKey?: string): Promise<JobResponse>;
  getJob(jobId: string): Promise<JobResponse>;
  /** Siempre emite URLs nuevas (vencen en 300 s). */
  getArtifacts(jobId: string): Promise<AuthorizedArtifactManifest>;
  /** 202: solo registra la solicitud; el estado `cancelled` lo publica el servidor. */
  cancelJob(jobId: string, idempotencyKey?: string): Promise<JobResponse>;
  /**
   * CAMBIO PROPUESTO (H2, no existe en OpenAPI v0.1): análisis visual de un trabajo de imagen.
   * Hasta que el backend lo ofrezca, solo lo responde el cliente simulado.
   */
  getAnalysis(jobId: string): Promise<AnalysisSpec>;
  /**
   * CAMBIO PROPUESTO (H2): aprobar el análisis (con regiones marcadas) o cambiar de proveedor.
   * Devuelve el trabajo nuevo; el que estaba en needs_review no se modifica.
   */
  decideAnalysis(jobId: string, decision: AnalysisDecision, idempotencyKey?: string): Promise<JobResponse>;
  /** Registra la muestra física de una revisión; nunca cambia el estado digital del trabajo. */
  recordSewout(projectId: string, request: SewoutRecordRequest, idempotencyKey?: string): Promise<SewoutResponse>;
  /** Variante de tamaño o corrección: responde con el trabajo nuevo. */
  createDerivedRevision(
    projectId: string,
    request: DerivedRevisionRequest,
    idempotencyKey?: string,
  ): Promise<JobResponse>;
}
