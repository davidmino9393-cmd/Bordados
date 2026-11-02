// Contrato v0.1 — issues.py y results.py (Issue). El catálogo de códigos vive en el backend.

export const Severity = {
  Blocking: 'blocking_error',
  ReviewRequired: 'review_required',
  Info: 'info',
} as const;
export type Severity = (typeof Severity)[keyof typeof Severity];

/** Código del catálogo (issue-catalog.json). Se mantiene como texto: el backend es la autoridad. */
export type IssueCode = string;

export interface Issue {
  code: IssueCode;
  severity: Severity;
  stage: string;
  object_ids: string[];
  region_ids: string[];
  description: string;
  /** JSON estructurado del motor; no se muestra crudo al usuario. */
  evidence: Record<string, unknown>;
  suggested_correction: string;
}

export interface FailureSummary {
  code: IssueCode;
  message: string;
  stage: 'queued' | 'analyzing' | 'vectorizing' | 'digitizing' | 'validating';
}

/** El contrato entrega ids de objetos/regiones, no cajas en píxeles. */
export interface ReviewSummary {
  cause: string;
  issues: Issue[];
  object_ids: string[];
  region_ids: string[];
}
