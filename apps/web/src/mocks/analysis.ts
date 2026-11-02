// SIMULADO — análisis visual de una imagen (H2). Los datos salen de apps/web/mocks/analysis-result.json.
import analysisFixture from '../../mocks/analysis-result.json';
import type { AnalysisRegion, AnalysisSpec } from '../contracts/analysis';
import { Severity, type Issue } from '../contracts/validation';
import type { SimulatedJob } from './jobSimulation';

type AmbiguityName = 'analisis' | 'ambiguo';
const REFERENCE = analysisFixture.reference_size_px;
const ISSUE_CODE = 'ANALYSIS_REGION_INCOHERENT';

const ambiguousIds = (name: AmbiguityName | undefined): string[] =>
  name ? (analysisFixture.ambiguity_sets as Record<AmbiguityName, string[]>)[name] : [];

/** Regiones del fixture escaladas del tamaño de referencia (800 × 600) al del original subido. */
function scaledRegions(job: SimulatedJob): AnalysisRegion[] {
  // El análisis solo lleva dudas en las regiones que el guion marca como inciertas (coherente con los avisos).
  const uncertain = new Set(ambiguousIds(job.scenario.ambiguity));
  const sx = job.assetPx ? job.assetPx.width / REFERENCE.width : 1;
  const sy = job.assetPx ? job.assetPx.height / REFERENCE.height : 1;
  return (analysisFixture.payload.regions as AnalysisRegion[]).map((region) => ({
    ...region,
    suggested_colors: [...region.suggested_colors],
    uncertainties: uncertain.has(region.region_id) ? [...region.uncertainties] : [],
    bounds_px: {
      x_px: region.bounds_px.x_px * sx,
      y_px: region.bounds_px.y_px * sy,
      width_px: Math.max(region.bounds_px.width_px * sx, 1),
      height_px: Math.max(region.bounds_px.height_px * sy, 1),
    },
  }));
}

export function buildAnalysisSpec(job: SimulatedJob): AnalysisSpec {
  const provider = job.settings.ai_provider === 'ollama' ? 'ollama' : 'openai';
  return {
    ...(analysisFixture.payload as unknown as AnalysisSpec),
    analysis_id: `analysis_${job.id}`,
    asset_id: job.assetId,
    provider,
    model: provider === 'ollama' ? 'modelo-local-simulado' : 'modelo-nube-simulado',
    regions: scaledRegions(job),
  };
}

/** Un aviso ANALYSIS_REGION_INCOHERENT por región incierta (el contrato exige región localizada). */
export function analysisIssues(job: SimulatedJob): Issue[] {
  const uncertain = new Set(ambiguousIds(job.scenario.ambiguity));
  return (analysisFixture.payload.regions as AnalysisRegion[])
    .filter((region) => uncertain.has(region.region_id))
    .map((region) => ({
      code: ISSUE_CODE,
      severity: Severity.ReviewRequired,
      stage: 'analysis',
      object_ids: [],
      region_ids: [region.region_id],
      description: region.uncertainties[0] ?? 'Region inconsistent with image',
      evidence: { simulated: true, region_id: region.region_id, uncertainties: region.uncertainties },
      suggested_correction: 'Revisá esta zona del original antes de continuar con el vector.',
    }));
}
