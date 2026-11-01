// BORRADOR v0.1 — ArtifactManifest (sección 1 y 8). Los campos de cada artefacto son cambio propuesto.

export const ArtifactKind = {
  SvgEditable: 'svg_editable',
  SvgInkStitch: 'svg_inkstitch',
  Jef: 'jef',
  JefPreview: 'jef_preview_png',
  Report: 'report',
} as const;
export type ArtifactKind = (typeof ArtifactKind)[keyof typeof ArtifactKind];

export interface Artifact {
  kind: ArtifactKind;
  /** Trabajo que produjo el archivo. La web rechaza artefactos de otro trabajo. */
  job_id: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  content_type: string;
  download_url: string;
}

/** Medidas tomadas sobre el JEF releído (sección 8). Distintas de la página SVG. */
export interface ReadbackMetrics {
  source: 'jef_reread';
  width_mm: number;
  height_mm: number;
  needle_stitches: number;
  thread_blocks: number;
  color_changes: number;
  jumps: number;
  trims: number;
  counting_method: string;
  processing_ms: number;
}

export interface ArtifactManifest {
  job_id: string;
  artifacts: Artifact[];
  metrics: ReadbackMetrics | null;
}
