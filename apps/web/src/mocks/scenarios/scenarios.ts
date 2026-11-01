// SIMULADO — guiones de comportamiento del MockApiClient.
import { JobStatus, PIPELINE_STAGES, type PipelineStage } from '../../contracts/job';

export const ScenarioOutcome = {
  Ready: 'ready',
  NeedsReview: 'needs_review',
  /** Controles digitales sin aprobar, pero con archivos ya generados (fixture job-completed-real). */
  NeedsReviewWithFiles: 'needs_review_with_files',
  Failed: 'failed',
} as const;
export type ScenarioOutcome = (typeof ScenarioOutcome)[keyof typeof ScenarioOutcome];

export interface Scenario {
  name: string;
  outcome: ScenarioOutcome;
  /** Etapas que el backend registra como omitidas (SVG preparado). */
  skipped: PipelineStage[];
  /** Etapa en la que falla, si outcome = failed. */
  failAt?: PipelineStage;
}

export const SCENARIO_KEYWORD = {
  Failure: 'fallo',
  Review: 'revision',
  Completed: 'completo',
} as const;

const PREPARED_SKIPS: PipelineStage[] = [JobStatus.Analyzing, JobStatus.Vectorizing];

/** Elige el guion por nombre de archivo: la subida de prueba decide qué se simula. */
export function pickScenario(filename: string, isSvg: boolean): Scenario {
  const name = filename.toLowerCase();
  const skipped = isSvg ? PREPARED_SKIPS : [];
  if (name.includes(SCENARIO_KEYWORD.Failure)) {
    return { name: 'fallo', outcome: ScenarioOutcome.Failed, skipped, failAt: JobStatus.Digitizing };
  }
  if (name.includes(SCENARIO_KEYWORD.Review)) {
    return { name: 'revision', outcome: ScenarioOutcome.NeedsReview, skipped };
  }
  if (isSvg && name.includes(SCENARIO_KEYWORD.Completed)) {
    return { name: 'completo', outcome: ScenarioOutcome.NeedsReviewWithFiles, skipped };
  }
  return { name: 'exito', outcome: ScenarioOutcome.Ready, skipped };
}

export function activeStages(scenario: Scenario): PipelineStage[] {
  return PIPELINE_STAGES.filter((stage) => !scenario.skipped.includes(stage));
}
