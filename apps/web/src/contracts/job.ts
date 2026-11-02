// Contrato v0.1 — jobs.py y states.py.
import type { ArtifactManifest, ValidationReport } from './artifacts';
import type { SewoutProjection, SewoutStatus } from './sewout';
import type { JobSettings } from './settings';
import type { FailureSummary, Issue, ReviewSummary } from './validation';

export const JobStatus = {
  Queued: 'queued',
  Analyzing: 'analyzing',
  Vectorizing: 'vectorizing',
  Digitizing: 'digitizing',
  Validating: 'validating',
  ReadyForSewout: 'ready_for_sewout',
  NeedsReview: 'needs_review',
  Failed: 'failed',
  Cancelled: 'cancelled',
} as const;
export type JobStatus = (typeof JobStatus)[keyof typeof JobStatus];

/** Etapas con registro propio; `queued` es espera, no etapa. */
export const PIPELINE_STAGES = [
  JobStatus.Analyzing,
  JobStatus.Vectorizing,
  JobStatus.Digitizing,
  JobStatus.Validating,
] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export const StageOutcome = {
  Pending: 'pending',
  Running: 'running',
  Completed: 'completed',
  /** SVG ya preparado: análisis y vectorización se registran como omitidos, con motivo. */
  Skipped: 'skipped',
  Failed: 'failed',
  Cancelled: 'cancelled',
} as const;
export type StageOutcome = (typeof StageOutcome)[keyof typeof StageOutcome];

export interface StageRecord {
  stage: PipelineStage;
  outcome: StageOutcome;
  reason: string | null;
  /** Medido por el backend; ausente si no se midió. */
  measured_duration_ms: number | null;
}

export type InputKind = 'prepared_svg' | 'raster_image';

export interface JobCreate {
  schema_version: string;
  asset_id: string;
  revision_id: string;
  input_kind: InputKind;
  settings: JobSettings;
}

export interface JobResponse {
  schema_version: string;
  job_id: string;
  project_id: string;
  revision_id: string;
  asset_id: string;
  input_kind: InputKind;
  settings_snapshot: JobSettings;
  status: JobStatus;
  stages: StageRecord[];
  parent_job_id: string | null;
  /** Estimación, nunca duración medida. */
  estimated_remaining_s: number | null;
  sewout_status: SewoutStatus;
  sewout_record: SewoutProjection | null;
  failure: FailureSummary | null;
  review: ReviewSummary | null;
  diagnostics: Issue[] | null;
  /** true solo confirma la solicitud; el estado `cancelled` lo publica el servidor. */
  cancellation_requested: boolean;
  issues: Issue[];
  validation_report: ValidationReport | null;
  /** Instantánea: las URLs de descarga pueden ser null; usar GET artifacts para obtenerlas. */
  artifact_manifest: ArtifactManifest | null;
}

/** Estados que no cambian sin una acción nueva (states.md). */
export const TERMINAL_STATUSES: readonly JobStatus[] = [
  JobStatus.ReadyForSewout,
  JobStatus.NeedsReview,
  JobStatus.Failed,
  JobStatus.Cancelled,
];

export const ACTIVE_STATUSES: readonly JobStatus[] = [
  JobStatus.Queued,
  JobStatus.Analyzing,
  JobStatus.Vectorizing,
  JobStatus.Digitizing,
  JobStatus.Validating,
];
