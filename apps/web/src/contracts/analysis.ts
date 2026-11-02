// H2 — análisis visual de una imagen.
//
// AnalysisRegion / AnalysisSpec: forma CONGELADA en contratos-v0.1 (design.py, componentes de
// openapi.json). Ningún endpoint de v0.1 los devuelve todavía.
// AnalysisDecision y las operaciones getAnalysis / decideAnalysis: forma CONFIRMADA por OpenCode, pero
// todavía no incorporada a OpenAPI/contracts (cambio aditivo pendiente). Detalle en
// apps/web/docs/H0-05-recorrido-web.md.
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

/**
 * Decisión del usuario sobre un análisis en needs_review (POST /jobs/{id}/analysis-decision). Ambas crean un
 * job nuevo con parent_job_id = el original, que no cambia.
 * - approve: misma revisión y mismo asset; `analyzing` queda omitido. flagged_region_ids debe ser un
 *   subconjunto de las regiones del análisis y solo se guarda como metadato (no bloquea ni altera la geometría).
 * - change_provider: el servidor crea una revisión nueva (`analysis_retry`); el revision_id del job nuevo
 *   es distinto, la web debe leerlo de la respuesta.
 */
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
