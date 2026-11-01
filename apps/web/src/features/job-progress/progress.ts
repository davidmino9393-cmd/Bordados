import { StageState, type StageProgress } from '../../contracts/job';

export interface ProgressSummary {
  done: number;
  total: number;
}

/** Progreso derivado solo de etapas observadas; las omitidas no cuentan. */
export function summarizeProgress(stages: StageProgress[]): ProgressSummary {
  const counted = stages.filter((s) => s.state !== StageState.Skipped);
  return {
    done: counted.filter((s) => s.state === StageState.Done).length,
    total: counted.length,
  };
}
