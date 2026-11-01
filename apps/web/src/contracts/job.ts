// BORRADOR v0.1 — estados y forma de Job (sección 6). La forma de Job es cambio propuesto.
import type { SewoutStatus } from './sewout';
import type { JobSettings } from './settings';
import type { ReviewRequest, ValidationIssue } from './validation';

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

/** Etapas de la secuencia, en orden. `queued` es espera, no etapa. */
export const PIPELINE_STAGES = [
  JobStatus.Analyzing,
  JobStatus.Vectorizing,
  JobStatus.Digitizing,
  JobStatus.Validating,
] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export const StageState = {
  Pending: 'pending',
  Running: 'running',
  Done: 'done',
  /** SVG ya preparado: análisis y vectorización se registran como omitidos. */
  Skipped: 'skipped',
  Failed: 'failed',
} as const;
export type StageState = (typeof StageState)[keyof typeof StageState];

export interface StageProgress {
  stage: PipelineStage;
  state: StageState;
  /** Tiempo medido por el backend. Ausente mientras no terminó. */
  duration_ms?: number;
}

export interface JobFailure {
  code: string;
  message: string;
  stage: PipelineStage | 'queued';
}

export interface Job {
  id: string;
  project_id: string;
  source_asset_id: string;
  status: JobStatus;
  settings: JobSettings;
  stages: StageProgress[];
  created_at: string;
  updated_at: string;
  /** Trabajo del que deriva una variante o corrección (sección 6: revisión relacionada). */
  parent_job_id: string | null;
  failure?: JobFailure;
  review?: ReviewRequest;
  /** Diagnóstico disponible (sección 5). */
  diagnostics: ValidationIssue[];
  /** Aprobación física, separada del estado digital. Cambio propuesto: exponerla en el trabajo. */
  sewout_status: SewoutStatus;
  /** Estimación, no medición. null si el backend no la ofrece. */
  estimated_remaining_s: number | null;
}

/** Estados en los que el trabajo ya no cambia sin una acción nueva. */
export const TERMINAL_STATUSES: readonly JobStatus[] = [
  JobStatus.ReadyForSewout,
  JobStatus.NeedsReview,
  JobStatus.Failed,
  JobStatus.Cancelled,
];

export const CANCELLABLE_STATUSES: readonly JobStatus[] = [
  JobStatus.Queued,
  JobStatus.Analyzing,
  JobStatus.Vectorizing,
  JobStatus.Digitizing,
  JobStatus.Validating,
];
