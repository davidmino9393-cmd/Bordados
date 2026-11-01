import { CONTRACT_SCHEMA_VERSION } from '../../contracts/version';
import {
  AiProvider,
  FitMode,
  type JobSettings,
  type MachineProfile,
  type ProfileCatalog,
} from '../../contracts/settings';

export interface SettingsFormValues {
  width_mm: string;
  height_mm: string;
  machine_profile: string;
  hoop_profile: string;
  fabric_profile: string;
  thread_profile: string;
  color_limit: string;
  ai_provider: AiProvider;
}

export const SettingsError = {
  Width: 'width_mm',
  Height: 'height_mm',
  Colors: 'color_limit',
} as const;
export type SettingsErrorField = (typeof SettingsError)[keyof typeof SettingsError];
export type SettingsErrors = Partial<Record<SettingsErrorField, 'positive' | 'range'>>;

export function parseMm(value: string): number {
  return Number(value.replace(',', '.'));
}

const isPositive = (n: number) => Number.isFinite(n) && n > 0;

export function validateSettings(values: SettingsFormValues, machine: MachineProfile): SettingsErrors {
  const errors: SettingsErrors = {};
  if (!isPositive(parseMm(values.width_mm))) errors.width_mm = 'positive';
  if (!isPositive(parseMm(values.height_mm))) errors.height_mm = 'positive';
  const colors = Number(values.color_limit);
  if (!Number.isInteger(colors) || colors < 1 || colors > machine.max_colors) errors.color_limit = 'range';
  return errors;
}

/** Arma JobSettings con las instantáneas de perfil del catálogo; la web no fija valores. */
export function toJobSettings(values: SettingsFormValues, catalog: ProfileCatalog): JobSettings {
  const machine = catalog.machines.find((m) => m.profile_id === values.machine_profile);
  const hoop = catalog.hoops.find((h) => h.profile_id === values.hoop_profile);
  const fabric = catalog.fabrics.find((f) => f.profile_id === values.fabric_profile);
  if (!machine || !hoop || !fabric) throw new Error('El perfil elegido ya no está en el catálogo.');
  return {
    schema_version: CONTRACT_SCHEMA_VERSION,
    target: { width_mm: parseMm(values.width_mm), height_mm: parseMm(values.height_mm), fit: FitMode.Contain },
    machine_profile: machine.profile_id,
    machine_profile_version: machine.profile_version,
    hoop_profile: hoop.profile_id,
    hoop: {
      profile_id: hoop.profile_id,
      profile_version: hoop.profile_version,
      width_mm: hoop.width_mm,
      height_mm: hoop.height_mm,
      jef_hoop_code: hoop.jef_hoop_code,
    },
    fabric_profile: fabric.profile_id,
    fabric_profile_version: fabric.profile_version,
    thread_profile: values.thread_profile,
    color_limit: Number(values.color_limit),
    ai_provider: values.ai_provider,
    ai_model: null,
  };
}
