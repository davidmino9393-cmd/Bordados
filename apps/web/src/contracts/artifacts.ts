// Contrato v0.1 — results.py (Artifact, ArtifactManifest, RereadMetrics).

export const ArtifactKind = {
  Jef: 'jef',
  EditableSvg: 'editable_svg',
  InkStitchSvg: 'inkstitch_svg',
  PreviewPng: 'preview_png',
  ValidationJson: 'validation_json',
  StitchPlanJson: 'stitch_plan_json',
  RawCommandsJson: 'raw_commands_json',
  ProviderRawJson: 'provider_raw_json',
} as const;
export type ArtifactKind = (typeof ArtifactKind)[keyof typeof ArtifactKind];

export type DerivedFrom = 'export' | 'jef_reread' | 'document' | 'validation' | 'provider';

/** Enlace privado temporal: vence exactamente 300 s después de `issued_at` (UTC). */
export interface ArtifactDownload {
  url: string;
  issued_at: string;
  expires_at: string;
}

export interface Artifact {
  artifact_id: string;
  job_id: string;
  kind: ArtifactKind;
  filename: string;
  media_type: string;
  sha256: string;
  byte_size: number;
  derived_from: DerivedFrom;
  download: ArtifactDownload | null;
  download_url: string | null;
  expires_at: string | null;
}

export interface BoundsMM {
  min_x_mm: number;
  min_y_mm: number;
  max_x_mm: number;
  max_y_mm: number;
}

/** Medidas del JEF releído (sección 8 de la propuesta). */
export interface RereadMetrics {
  stitch_bounds_mm: BoundsMM;
  needle_stitches: number;
  thread_blocks: number;
  color_changes: number;
  raw_jump_commands: number;
  displacement_jump_commands: number;
  interpreted_trims: number;
  max_stitch_length_mm: number;
  jump_travel_mm: number;
  processing_duration_ms: number;
  count_method: string;
  raw_commands_artifact_id: string;
  /** Siempre false en v0.1: el corte en máquina se verifica por separado. */
  physical_trim_execution_verified: false;
}

export interface Provenance {
  simulated: boolean;
  method: string;
  engine_version?: string | null;
  parser_version?: string | null;
}

export interface ArtifactManifest {
  schema_version: string;
  manifest_id: string;
  job_id: string;
  revision_id: string;
  provenance: Provenance;
  input_sha256: string;
  settings_sha256: string;
  geometry_sha256: string;
  artifacts: Artifact[];
  /** null mientras no exista un JEF releído (H2: solo geometría vectorizada). */
  reread_metrics: RereadMetrics | null;
}

/** Respuesta de GET /jobs/{id}/artifacts: todos los artefactos traen `download`. */
export type AuthorizedArtifactManifest = ArtifactManifest;

export interface ValidationCheck {
  kind: 'file' | 'dimensions' | 'hoop' | 'geometry' | 'satin' | 'routing' | 'visual';
  outcome: 'passed' | 'failed' | 'needs_review' | 'not_run';
  method: string;
}

export interface ValidationReport {
  schema_version: string;
  report_id: string;
  job_id: string;
  revision_id: string;
  provenance: Provenance;
  checks: ValidationCheck[];
  issues: unknown[];
  digital_checks_passed: boolean;
  metrics: RereadMetrics | null;
}
