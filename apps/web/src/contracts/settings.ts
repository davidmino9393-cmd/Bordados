// Contrato v0.1 — settings.py y profiles.py.

export const FitMode = { Contain: 'contain' } as const;
export type FitMode = (typeof FitMode)[keyof typeof FitMode];

/** "none": un SVG ya preparado, o una imagen que la persona elige procesar sin análisis de IA. */
export const AiProvider = { None: 'none', OpenAI: 'openai', Ollama: 'ollama' } as const;
export type AiProvider = (typeof AiProvider)[keyof typeof AiProvider];

export const MediaType = { Png: 'image/png', Jpeg: 'image/jpeg', Svg: 'image/svg+xml' } as const;
export type MediaType = (typeof MediaType)[keyof typeof MediaType];

export interface TargetSize {
  width_mm: number;
  height_mm: number;
  fit: FitMode;
}

export interface HoopSettings {
  profile_id: string;
  profile_version: string;
  width_mm: number;
  height_mm: number;
  jef_hoop_code: number;
}

export interface JobSettings {
  schema_version: string;
  target: TargetSize;
  machine_profile: string;
  machine_profile_version: string;
  hoop_profile: string;
  hoop: HoopSettings;
  fabric_profile: string;
  fabric_profile_version: string;
  thread_profile: string;
  color_limit: number;
  ai_provider: AiProvider;
  ai_model?: string | null;
}

export type CalibrationStatus = 'proposed' | 'physically_calibrated';

export interface MachineProfile {
  profile_id: string;
  profile_version: string;
  label: string;
  hoop_profile_ids: string[];
  max_colors: number;
  calibration_status: CalibrationStatus;
  calibration_record_id: string | null;
}

export interface HoopProfile {
  profile_id: string;
  profile_version: string;
  label: string;
  width_mm: number;
  height_mm: number;
  jef_hoop_code: number;
}

export interface FabricProfile {
  profile_id: string;
  profile_version: string;
  label: string;
  calibration_status: CalibrationStatus;
  calibration_record_id: string | null;
}

export interface ThreadProfile {
  profile_id: string;
  profile_version: string;
  label: string;
}

export interface ProviderAvailability {
  provider_id: Exclude<AiProvider, 'none'>;
  available: boolean;
  unavailable_reason: string | null;
}

export interface UploadLimits {
  max_bytes: number;
  max_decoded_pixels: number;
  accepted_mime_types: MediaType[];
}

export interface ProfileCatalog {
  schema_version: string;
  catalog_version: string;
  machines: MachineProfile[];
  hoops: HoopProfile[];
  fabrics: FabricProfile[];
  thread_profiles: ThreadProfile[];
  max_colors: number;
  providers: ProviderAvailability[];
  upload_limits: UploadLimits;
}
