// Contrato v0.1 — jobs.py / job_views.py (aprobación física, independiente del estado digital).

export const SewoutStatus = {
  Untested: 'untested',
  Approved: 'approved',
  NeedsAdjustment: 'needs_adjustment',
} as const;
export type SewoutStatus = (typeof SewoutStatus)[keyof typeof SewoutStatus];

/** Proyección de solo lectura dentro de JobResponse. */
export interface SewoutProjection {
  sewout_id: string;
  revision_id: string;
  status: SewoutStatus;
  tested_at: string | null;
  observations: string;
  photo_asset_ids: string[];
}
