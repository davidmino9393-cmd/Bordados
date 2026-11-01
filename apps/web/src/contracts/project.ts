// BORRADOR v0.1 — SourceAsset (sección 1) y Project. Project y las lecturas son cambio propuesto.
import type { Job } from './job';
import type { SewoutStatus } from './sewout';

export interface Project {
  id: string;
  name: string;
  created_at: string;
}

export const AssetFormat = { Png: 'png', Jpeg: 'jpeg', Svg: 'svg' } as const;
export type AssetFormat = (typeof AssetFormat)[keyof typeof AssetFormat];

export interface SourceAsset {
  id: string;
  project_id: string;
  sha256: string;
  format: AssetFormat;
  /** Píxeles de la imagen original. No es tamaño físico de bordado. */
  width_px: number;
  height_px: number;
  /** URL para mostrar el original. */
  original_url: string;
}

export interface ProjectDetail {
  project: Project;
  assets: SourceAsset[];
  jobs: Job[];
}

export interface ProjectSummary extends Project {
  job_count: number;
  latest_job_status: Job['status'] | null;
  latest_sewout_status: SewoutStatus | null;
}

/** Cambio propuesto: cuerpo de POST /projects/{id}/revisions. */
export type RevisionRequest =
  | {
      kind: 'size_variant';
      parent_job_id: string;
      target: { width_mm: number; height_mm: number; fit: 'contain' };
    }
  | {
      kind: 'correction';
      parent_job_id: string;
      corrections: Correction[];
    };

export type Correction =
  | { action: 'exclude_region'; object_id: string }
  | { action: 'set_technique'; object_id: string; technique: Technique };

export const Technique = {
  Running: 'running',
  Bean: 'bean',
  Satin: 'satin',
  Fill: 'fill',
} as const;
export type Technique = (typeof Technique)[keyof typeof Technique];
