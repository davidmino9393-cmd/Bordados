import type { ArtifactManifest } from '../contracts/artifacts';
import type { Job } from '../contracts/job';
import type {
  Project,
  ProjectDetail,
  ProjectSummary,
  RevisionRequest,
  SourceAsset,
} from '../contracts/project';
import type { JobSettings, ProfileCatalog } from '../contracts/settings';

export const ApiErrorCode = {
  NotFound: 'not_found',
  InvalidInput: 'invalid_input',
  Unavailable: 'unavailable',
  ContractsNotFrozen: 'contracts_not_frozen',
} as const;
export type ApiErrorCode = (typeof ApiErrorCode)[keyof typeof ApiErrorCode];

export class ApiError extends Error {
  constructor(
    public readonly code: ApiErrorCode,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Superficie que la web consume. Las rutas corresponden a la sección 5 del contrato. */
export interface ApiClient {
  /** true cuando las respuestas son simuladas. La UI lo muestra siempre. */
  readonly isSimulated: boolean;
  getProfiles(): Promise<ProfileCatalog>;
  listProjects(): Promise<ProjectSummary[]>;
  createProject(name: string): Promise<Project>;
  getProject(projectId: string): Promise<ProjectDetail>;
  uploadAsset(projectId: string, file: File): Promise<SourceAsset>;
  createJob(
    projectId: string,
    assetId: string,
    settings: JobSettings,
    idempotencyKey: string,
  ): Promise<Job>;
  getJob(jobId: string): Promise<Job>;
  getArtifacts(jobId: string): Promise<ArtifactManifest>;
  cancelJob(jobId: string): Promise<Job>;
  createRevision(projectId: string, request: RevisionRequest): Promise<Job>;
}
