// SIMULADO — guiones de comportamiento del MockApiClient.
import { JobStatus, PIPELINE_STAGES, type PipelineStage } from '../../contracts/job';

export const ScenarioOutcome = {
  Ready: 'ready',
  NeedsReview: 'needs_review',
  /** Controles digitales sin aprobar, pero con archivos ya generados (fixture job-completed-real). */
  NeedsReviewWithFiles: 'needs_review_with_files',
  /** Imagen: el análisis termina en needs_review con regiones inciertas (H2, solo mock). */
  AnalysisReview: 'analysis_review',
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
  /** Qué regiones del análisis simulado son inciertas (analysis-result.json → ambiguity_sets). */
  ambiguity?: 'analisis' | 'ambiguo';
  /** Motivo de las etapas omitidas, si no es el de SVG preparado. */
  skipReason?: string;
}

export const SCENARIO_KEYWORD = {
  Failure: 'fallo',
  Review: 'revision',
  Completed: 'completo',
  Analysis: 'analisis',
  Ambiguous: 'ambiguo',
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
  if (!isSvg && name.includes(SCENARIO_KEYWORD.Ambiguous)) {
    return { name: 'ambiguo', outcome: ScenarioOutcome.AnalysisReview, skipped, ambiguity: 'ambiguo' };
  }
  if (!isSvg && name.includes(SCENARIO_KEYWORD.Analysis)) {
    return { name: 'analisis', outcome: ScenarioOutcome.AnalysisReview, skipped, ambiguity: 'analisis' };
  }
  if (isSvg && name.includes(SCENARIO_KEYWORD.Completed)) {
    return { name: 'completo', outcome: ScenarioOutcome.NeedsReviewWithFiles, skipped };
  }
  return { name: 'exito', outcome: ScenarioOutcome.Ready, skipped };
}

export function activeStages(scenario: Scenario): PipelineStage[] {
  return PIPELINE_STAGES.filter((stage) => !scenario.skipped.includes(stage));
}
