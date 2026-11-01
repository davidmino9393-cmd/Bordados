// SIMULADO — calcula el estado de un trabajo a partir del tiempo transcurrido.
import {
  JobStatus,
  PIPELINE_STAGES,
  StageState,
  type Job,
  type PipelineStage,
  type StageProgress,
} from '../contracts/job';
import { SewoutStatus } from '../contracts/sewout';
import type { JobSettings } from '../contracts/settings';
import type { ReviewRequest } from '../contracts/validation';
import { Severity } from '../contracts/validation';
import { ScenarioOutcome, activeStages, type Scenario } from './scenarios/scenarios';

export const QUEUE_MS = 500;
const MS_PER_SECOND = 1000;

export interface SimulatedJobRecord {
  id: string;
  projectId: string;
  assetId: string;
  settings: JobSettings;
  scenario: Scenario;
  parentJobId: string | null;
  createdAt: number;
  assetWidthPx: number;
  assetHeightPx: number;
  cancelledAt: number | null;
}

function buildReview(record: SimulatedJobRecord): ReviewRequest {
  const { assetWidthPx: w, assetHeightPx: h } = record;
  return {
    cause: 'Una columna de satin es demasiado angosta para la tela elegida.',
    regions: [{ object_id: 'obj_007', x: w * 0.3, y: h * 0.4, width: w * 0.2, height: h * 0.15 }],
    issues: [
      {
        code: 'satin_width_below_minimum',
        severity: Severity.ReviewRequired,
        stage: JobStatus.Validating,
        object_ids: ['obj_007'],
        description: 'El trazo mide menos de lo que admite un satin en este tamaño.',
        evidence: 'Ancho físico medido: 0,8 mm (simulado).',
        suggested_fix: 'Cambiar la técnica a puntada de línea o excluir el elemento.',
      },
    ],
  };
}

function stageList(
  record: SimulatedJobRecord,
  runningIndex: number,
  terminal: 'none' | 'done' | 'failed',
  stageMs: number,
): StageProgress[] {
  const active = activeStages(record.scenario);
  return PIPELINE_STAGES.map((stage): StageProgress => {
    const position = active.indexOf(stage);
    if (position === -1) return { stage, state: StageState.Skipped };
    if (terminal === 'failed' && stage === record.scenario.failAt) {
      return { stage, state: StageState.Failed };
    }
    const failPosition = record.scenario.failAt ? active.indexOf(record.scenario.failAt) : -1;
    if (terminal === 'failed' && position > failPosition) return { stage, state: StageState.Pending };
    if (terminal === 'done' || position < runningIndex) {
      return { stage, state: StageState.Done, duration_ms: stageMs };
    }
    return { stage, state: position === runningIndex ? StageState.Running : StageState.Pending };
  });
}

export function simulateJob(record: SimulatedJobRecord, now: number, stageMs: number): Job {
  const base = {
    id: record.id,
    project_id: record.projectId,
    source_asset_id: record.assetId,
    settings: record.settings,
    created_at: new Date(record.createdAt).toISOString(),
    parent_job_id: record.parentJobId,
    diagnostics: [],
    sewout_status: SewoutStatus.Untested,
  };
  const active = activeStages(record.scenario);
  const failPosition = record.scenario.failAt ? active.indexOf(record.scenario.failAt) : -1;
  const lastIndex = record.scenario.outcome === ScenarioOutcome.Failed ? failPosition : active.length - 1;
  const clock = record.cancelledAt ?? now;
  const elapsed = clock - record.createdAt;
  const runningIndex = Math.floor((elapsed - QUEUE_MS) / stageMs);
  const updated_at = new Date(clock).toISOString();
  const remainingMs = Math.max(0, QUEUE_MS + (lastIndex + 1) * stageMs - elapsed);
  const estimated_remaining_s = Math.ceil(remainingMs / MS_PER_SECOND);

  if (record.cancelledAt !== null) {
    const snapshot = elapsed < QUEUE_MS ? -1 : Math.min(runningIndex, lastIndex);
    return {
      ...base,
      status: JobStatus.Cancelled,
      stages: stageList(record, snapshot, 'none', stageMs).map((s) =>
        s.state === StageState.Running ? { stage: s.stage, state: StageState.Pending } : s,
      ),
      updated_at,
      estimated_remaining_s: null,
    };
  }
  if (elapsed < QUEUE_MS) {
    return { ...base, status: JobStatus.Queued, stages: stageList(record, -1, 'none', stageMs), updated_at, estimated_remaining_s };
  }
  if (runningIndex <= lastIndex) {
    return {
      ...base,
      status: active[runningIndex],
      stages: stageList(record, runningIndex, 'none', stageMs),
      updated_at,
      estimated_remaining_s,
    };
  }
  if (record.scenario.outcome === ScenarioOutcome.Failed) {
    return {
      ...base,
      status: JobStatus.Failed,
      stages: stageList(record, runningIndex, 'failed', stageMs),
      failure: {
        code: 'engine_export_failed',
        message: 'No se pudo generar el archivo de bordado en esta etapa (error simulado).',
        stage: record.scenario.failAt as PipelineStage,
      },
      updated_at,
      estimated_remaining_s: null,
    };
  }
  const outcome =
    record.scenario.outcome === ScenarioOutcome.NeedsReview
      ? { status: JobStatus.NeedsReview, review: buildReview(record) }
      : { status: JobStatus.ReadyForSewout };
  return { ...base, ...outcome, stages: stageList(record, runningIndex, 'done', stageMs), updated_at, estimated_remaining_s: null };
}
