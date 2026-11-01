// BORRADOR v0.1 — incidencias de validación (sección 7 del contrato).

export const Severity = {
  Blocking: 'blocking_error',
  ReviewRequired: 'review_required',
  Info: 'info',
} as const;
export type Severity = (typeof Severity)[keyof typeof Severity];

export interface ValidationIssue {
  code: string;
  severity: Severity;
  stage: string;
  object_ids: string[];
  description: string;
  evidence: string;
  suggested_fix: string;
}

/** Región en coordenadas de píxel de la imagen original (sección 2). */
export interface PixelRegion {
  object_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

/** needs_review: causa y objetos/regiones concretos (sección 6). */
export interface ReviewRequest {
  cause: string;
  issues: ValidationIssue[];
  regions: PixelRegion[];
}
