// BORRADOR v0.1 — JobSettings (sección 2 del contrato).

export const FitMode = { Contain: 'contain' } as const;
export type FitMode = (typeof FitMode)[keyof typeof FitMode];

export const AiProvider = { OpenAI: 'openai', Ollama: 'ollama' } as const;
export type AiProvider = (typeof AiProvider)[keyof typeof AiProvider];

export interface TargetSize {
  width_mm: number;
  height_mm: number;
  fit: FitMode;
}

export interface JobSettings {
  schema_version: string;
  target: TargetSize;
  machine_profile: string;
  /** Cambio propuesto: el texto menciona bastidor pero el ejemplo JSON no lo incluye. */
  hoop_profile: string;
  fabric_profile: string;
  color_limit: number;
  ai_provider: AiProvider;
}

/** Cambio propuesto: catálogo de perfiles leído del backend (no fijado en la web). */
export interface HoopProfile {
  id: string;
  label: string;
  width_mm: number;
  height_mm: number;
}

export interface MachineProfile {
  id: string;
  label: string;
  hoops: HoopProfile[];
  max_colors: number;
}

export interface FabricProfile {
  id: string;
  label: string;
}

export interface ProviderAvailability {
  id: AiProvider;
  label: string;
  available: boolean;
  /** Motivo en lenguaje de usuario cuando no está disponible. */
  unavailable_reason?: string;
}

export interface UploadLimits {
  max_bytes: number;
  accepted_mime_types: string[];
}

export interface ProfileCatalog {
  machines: MachineProfile[];
  fabrics: FabricProfile[];
  providers: ProviderAvailability[];
  upload_limits: UploadLimits;
}
