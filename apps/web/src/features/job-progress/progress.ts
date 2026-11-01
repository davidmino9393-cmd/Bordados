import { StageOutcome, type StageRecord } from '../../contracts/job';

export interface ProgressSummary {
  done: number;
  total: number;
}

/** Progreso derivado solo de etapas observadas; las omitidas no cuentan. */
export function summarizeProgress(stages: StageRecord[]): ProgressSummary {
  const counted = stages.filter((s) => s.outcome !== StageOutcome.Skipped);
  return {
    done: counted.filter((s) => s.outcome === StageOutcome.Completed).length,
    total: counted.length,
  };
}
