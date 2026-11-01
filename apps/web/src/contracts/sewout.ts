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

/** Cuerpo de POST /projects/{id}/sewouts (SewoutRecord). Fotos: opcionales, aún sin subida en la web. */
export interface SewoutRecordRequest {
  schema_version: string;
  revision_id: string;
  status: SewoutStatus;
  /** Obligatorio si el resultado no es `untested`; debe ser null si es `untested`. */
  tested_at: string | null;
  /** Identificador de un perfil de tela del catálogo, no texto libre. */
  fabric_profile: string;
  stabilizer: string;
  thread: string;
  observations: string;
  photo_asset_ids: string[];
}

/** Respuesta 201: el registro creado. */
export interface SewoutResponse extends SewoutRecordRequest {
  sewout_id: string;
  project_id: string;
  recorded_at: string;
}
