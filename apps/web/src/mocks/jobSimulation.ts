// SIMULADO — calcula el estado de un trabajo a partir del tiempo transcurrido.
// Las formas de respuesta salen de los fixtures copiados de packages/contracts/fixtures.
import cancellationFixture from '../../mocks/cancellation.json';
import completedFixture from '../../mocks/job-completed-real.json';
import failureFixture from '../../mocks/failure.json';
import needsReviewFixture from '../../mocks/needs-review.json';
import validResultFixture from '../../mocks/valid-result.json';
import type { Artifact, ArtifactManifest } from '../contracts/artifacts';
import {
  JobStatus,
  PIPELINE_STAGES,
  StageOutcome,
  type InputKind,
  type JobResponse,
  type PipelineStage,
  type StageRecord,
} from '../contracts/job';
import type { SewoutProjection } from '../contracts/sewout';
import type { JobSettings } from '../contracts/settings';
import { analysisIssues } from './analysis';
import { ScenarioOutcome, activeStages, type Scenario } from './scenarios/scenarios';

export const QUEUE_MS = 500;
/** El servidor tarda un poco en detener los procesos tras aceptar una cancelación. */
export const CANCEL_STOP_MS = 400;
const MS_PER_SECOND = 1000;

export interface SimulatedJob {
  id: string;
  projectId: string;
  revisionId: string;
  assetId: string;
  inputKind: InputKind;
  settings: JobSettings;
  scenario: Scenario;
  parentJobId: string | null;
  createdAt: number;
  /** Proporción del original; null si no se conoce (SVG sin píxeles). */
  aspectRatio: number | null;
  /** Tamaño en píxeles del original; null si no se conoce (SVG). */
  assetPx: { width: number; height: number } | null;
  cancelRequestedAt: number | null;
}

const clone = <T>(value: T): T => structuredClone(value);
const SKIP_REASON: Record<string, string> = {
  analyzing: 'Prepared SVG: analysis omitted',
  vectorizing: 'Prepared SVG: vectorization omitted',
};

function buildStages(job: SimulatedJob, runningIndex: number, terminal: 'none' | 'done' | 'failed', stageMs: number): StageRecord[] {
  const active = activeStages(job.scenario);
  const failPosition = job.scenario.failAt ? active.indexOf(job.scenario.failAt) : -1;
  return PIPELINE_STAGES.map((stage: PipelineStage): StageRecord => {
    const position = active.indexOf(stage);
    const make = (outcome: StageRecord['outcome'], ms: number | null = null): StageRecord => ({
      stage,
      outcome,
      reason: outcome === StageOutcome.Skipped ? (job.scenario.skipReason ?? SKIP_REASON[stage]) : null,
      measured_duration_ms: ms,
    });
    if (position === -1) return make(StageOutcome.Skipped);
    if (terminal === 'failed') {
      if (position < failPosition) return make(StageOutcome.Completed, stageMs);
      return make(position === failPosition ? StageOutcome.Failed : StageOutcome.Pending, position === failPosition ? stageMs : null);
    }
    if (terminal === 'done' || position < runningIndex) return make(StageOutcome.Completed, stageMs);
    return make(position === runningIndex ? StageOutcome.Running : StageOutcome.Pending);
  });
}

function withIdentity(template: JobResponse, job: SimulatedJob, stages: StageRecord[]): JobResponse {
  const response = clone(template);
  response.job_id = job.id;
  response.project_id = job.projectId;
  response.revision_id = job.revisionId;
  response.asset_id = job.assetId;
  response.input_kind = job.inputKind;
  response.settings_snapshot = clone(job.settings);
  response.parent_job_id = job.parentJobId;
  response.stages = stages;
  response.sewout_status = 'untested';
  response.sewout_record = null;
  return response;
}

function stitchedBounds(job: SimulatedJob) {
  const { width_mm: maxW, height_mm: maxH } = job.settings.target;
  const ratio = job.aspectRatio ?? maxW / maxH;
  const width = Math.min(maxW, maxH * ratio);
  return { min_x_mm: 0, min_y_mm: 0, max_x_mm: Number(width.toFixed(1)), max_y_mm: Number((width / ratio).toFixed(1)) };
}

/** Instantánea del manifiesto: las URLs vienen null; getArtifacts las emite frescas. */
function readyManifest(job: SimulatedJob, template: ArtifactManifest, keepBounds = false): ArtifactManifest {
  const manifest = clone(template);
  manifest.job_id = job.id;
  manifest.revision_id = job.revisionId;
  if (manifest.reread_metrics && !keepBounds) manifest.reread_metrics.stitch_bounds_mm = stitchedBounds(job);
  manifest.artifacts = manifest.artifacts.map((a): Artifact => ({
    ...a,
    job_id: job.id,
    artifact_id: `${job.id}_${a.kind}`,
    filename: `${job.id}-${a.filename}`,
    download: null,
    download_url: null,
    expires_at: null,
  }));
  if (manifest.reread_metrics) manifest.reread_metrics.raw_commands_artifact_id = `${job.id}_raw_commands_json`;
  return manifest;
}

function terminalResponse(job: SimulatedJob, stageMs: number, cancelledAtIndex: number | null): JobResponse {
  const { outcome } = job.scenario;
  if (cancelledAtIndex !== null) {
    const frozen = buildStages(job, cancelledAtIndex, 'none', stageMs).map((s) =>
      s.outcome === StageOutcome.Running ? { ...s, outcome: StageOutcome.Cancelled } : s,
    );
    const response = withIdentity(cancellationFixture.payload as JobResponse, job, frozen);
    response.cancellation_requested = true;
    return response;
  }
  if (outcome === ScenarioOutcome.Failed) {
    return withIdentity(failureFixture.payload as JobResponse, job, buildStages(job, 0, 'failed', stageMs));
  }
  if (outcome === ScenarioOutcome.NeedsReviewWithFiles) {
    const response = withIdentity(completedFixture.payload as unknown as JobResponse, job, buildStages(job, 0, 'done', stageMs));
    // Medidas y conteos del fixture tal cual; solo cambian los ids para pertenecer a este job.
    response.artifact_manifest = readyManifest(job, response.artifact_manifest as ArtifactManifest, true);
    if (response.validation_report) {
      response.validation_report.job_id = job.id;
      response.validation_report.revision_id = job.revisionId;
    }
    return response;
  }
  if (outcome === ScenarioOutcome.AnalysisReview) {
    // Solo terminó el análisis; el resto queda pendiente hasta que el usuario decida.
    const stages = PIPELINE_STAGES.map((stage): StageRecord => ({
      stage,
      outcome: stage === JobStatus.Analyzing ? StageOutcome.Completed : StageOutcome.Pending,
      reason: null,
      measured_duration_ms: stage === JobStatus.Analyzing ? stageMs : null,
    }));
    const response = withIdentity(needsReviewFixture.payload as JobResponse, job, stages);
    const issues = analysisIssues(job);
    response.issues = issues;
    response.diagnostics = issues;
    response.review = {
      cause: issues[0].description,
      issues,
      object_ids: [],
      region_ids: issues.flatMap((issue) => issue.region_ids).sort(),
    };
    response.validation_report = null;
    response.artifact_manifest = null;
    return response;
  }
  if (outcome === ScenarioOutcome.NeedsReview) {
    return withIdentity(needsReviewFixture.payload as JobResponse, job, buildStages(job, 0, 'done', stageMs));
  }
  const response = withIdentity(validResultFixture.payload as JobResponse, job, buildStages(job, 0, 'done', stageMs));
  const manifest = readyManifest(job, response.artifact_manifest as ArtifactManifest);
  response.artifact_manifest = manifest;
  if (response.validation_report) {
    response.validation_report.job_id = job.id;
    response.validation_report.revision_id = job.revisionId;
    response.validation_report.metrics = manifest.reread_metrics;
  }
  return response;
}

function activeResponse(job: SimulatedJob, status: JobResponse['status'], stages: StageRecord[], remainingS: number | null): JobResponse {
  const response = withIdentity(validResultFixture.payload as JobResponse, job, stages);
  response.status = status;
  response.estimated_remaining_s = remainingS;
  response.validation_report = null;
  response.artifact_manifest = null;
  response.diagnostics = [];
  response.issues = [];
  return response;
}

/** `sewout` es la proyección de la última muestra física registrada para la revisión del job. */
export function simulateJob(job: SimulatedJob, now: number, stageMs: number, sewout: SewoutProjection | null = null): JobResponse {
  const active = activeStages(job.scenario);
  const failPosition = job.scenario.failAt ? active.indexOf(job.scenario.failAt) : -1;
  const analysisOnly = job.scenario.outcome === ScenarioOutcome.AnalysisReview;
  const lastIndex = analysisOnly ? 0 : job.scenario.outcome === ScenarioOutcome.Failed ? failPosition : active.length - 1;
  const requested = job.cancelRequestedAt;
  const stopped = requested !== null && now >= requested + CANCEL_STOP_MS;
  const withSewout = (response: JobResponse): JobResponse => {
    response.sewout_record = sewout;
    response.sewout_status = sewout?.status ?? 'untested';
    return response;
  };
  const clock = requested ?? now;
  const elapsed = clock - job.createdAt;
  const runningIndex = Math.floor((elapsed - QUEUE_MS) / stageMs);
  if (stopped) return withSewout(terminalResponse(job, stageMs, Math.min(runningIndex, lastIndex)));

  const remainingMs = Math.max(0, QUEUE_MS + (lastIndex + 1) * stageMs - elapsed);
  const remainingS = Math.ceil(remainingMs / MS_PER_SECOND);

  let response: JobResponse;
  if (elapsed < QUEUE_MS) {
    response = activeResponse(job, JobStatus.Queued, buildStages(job, -1, 'none', stageMs), remainingS);
  } else if (runningIndex <= lastIndex) {
    response = activeResponse(job, active[runningIndex], buildStages(job, runningIndex, 'none', stageMs), remainingS);
  } else {
    response = terminalResponse(job, stageMs, null);
  }
  response.cancellation_requested = requested !== null;
  return withSewout(response);
}
