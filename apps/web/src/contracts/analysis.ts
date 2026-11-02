// H2 — análisis visual de una imagen.
//
// AnalysisRegion / AnalysisSpec: forma CONGELADA en contratos-v0.1 (design.py, componentes de
// openapi.json). Ningún endpoint de v0.1 los devuelve todavía.
// AnalysisDecision y las operaciones getAnalysis / decideAnalysis: CAMBIO PROPUESTO, no existen en
// OpenAPI v0.1; se documentan en apps/web/docs/H0-05-recorrido-web.md y esperan confirmación.
import type { BoundsPX } from './project';
import type { AiProvider } from './settings';

export interface AnalysisRegion {
  region_id: string;
  /** Caja estimada por la IA en píxeles del original: orienta, no es una máscara verificada. */
  bounds_px: BoundsPX;
  representation: 'estimated_bbox';
  visual_role: string;
  observed_text: string | null;
  suggested_colors: string[];
  uncertainties: string[];
}

export interface AnalysisSpec {
  schema_version: string;
  analysis_id: string;
  asset_id: string;
  provider: Exclude<AiProvider, 'none'>;
  model: string;
  prompt_version: string;
  original_response_artifact_id: string;
  regions: AnalysisRegion[];
  duration_ms: number;
  input_tokens: number | null;
  output_tokens: number | null;
}

/** CAMBIO PROPUESTO: decisión del usuario sobre un análisis en needs_review. Ambas crean un job nuevo. */
export type AnalysisDecision =
  | {
      action: 'approve';
      /** Regiones que el usuario quiere revisar a mano más adelante (no frenan la generación). */
      flagged_region_ids: string[];
    }
  | {
      action: 'change_provider';
      ai_provider: Exclude<AiProvider, 'none'>;
    };
