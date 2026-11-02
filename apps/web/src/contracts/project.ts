// Contrato v0.1 — jobs.py (proyectos, revisiones), settings.py (SourceAsset), revisions.py, queries.py.
import type { ArtifactDownload } from './artifacts';
import type { JobResponse } from './job';
import type { JobSettings, MediaType, TargetSize } from './settings';

export interface ProjectResponse {
  schema_version: string;
  project_id: string;
  name: string;
  created_at: string;
}

export interface BoundsPX {
  x_px: number;
  y_px: number;
  width_px: number;
  height_px: number;
}

/** `sewout_photo`: foto de una muestra cosida; nunca se elige para bordar. */
export const AssetPurpose = {
  Design: 'design',
  SewoutPhoto: 'sewout_photo',
} as const;
export type AssetPurpose = (typeof AssetPurpose)[keyof typeof AssetPurpose];

export interface SourceAsset {
  schema_version: string;
  asset_id: string;
  project_id: string;
  sha256: string;
  media_type: MediaType;
  /** Solo para mostrar. */
  original_filename: string;
  /** Enlace temporal (300 s): se renueva consultando de nuevo el proyecto. */
  original_download: ArtifactDownload | null;
  /** Un SVG puede no declarar píxeles. No es tamaño físico de bordado. */
  original_width_px: number | null;
  original_height_px: number | null;
  crop_px: BoundsPX | null;
  original_preserved: true;
  purpose: AssetPurpose;
}

export interface ProjectList {
  schema_version: string;
  items: ProjectResponse[];
  next_cursor: string | null;
}

export interface ProjectDetail {
  schema_version: string;
  project: ProjectResponse;
  assets: SourceAsset[];
  jobs: JobResponse[];
  assets_next_cursor: string | null;
  jobs_next_cursor: string | null;
}

/** Primera revisión del proyecto: `base_revision_id` siempre null (201). */
export interface InitialRevisionRequest {
  schema_version: string;
  base_revision_id: null;
  reason: string;
  settings: JobSettings;
}

export interface RevisionResponse {
  schema_version: string;
  revision_id: string;
  project_id: string;
  base_revision_id: string | null;
  reason: string;
  created_at: string;
  /** `analysis_retry` (H2) solo aparece en respuestas: la crea el servidor al cambiar de proveedor. */
  kind: 'initial' | 'size_variant' | 'correction' | 'analysis_retry';
  parent_job_id: string | null;
  job_id: string | null;
}

export const Technique = {
  Running: 'running',
  Bean: 'bean',
  Satin: 'satin',
  Fill: 'fill',
} as const;
export type Technique = (typeof Technique)[keyof typeof Technique];

/** exclude_region exige exactamente uno: object_id o region_id. */
export type Correction =
  | { action: 'exclude_region'; object_id: string }
  | { action: 'exclude_region'; region_id: string }
  | { action: 'set_technique'; object_id: string; technique: Technique };

export interface SizeVariantRequest {
  schema_version: string;
  kind: 'size_variant';
  parent_job_id: string;
  target: TargetSize;
}

export interface CorrectionRequest {
  schema_version: string;
  kind: 'correction';
  parent_job_id: string;
  corrections: Correction[];
}

/** Variante o corrección: responde 202 con el trabajo nuevo. */
export type DerivedRevisionRequest = SizeVariantRequest | CorrectionRequest;
