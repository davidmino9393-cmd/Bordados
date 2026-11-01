import { CONTRACT_SCHEMA_VERSION } from '../../contracts/version';
import { AiProvider, FitMode, type JobSettings, type MachineProfile } from '../../contracts/settings';

export interface SettingsFormValues {
  width_mm: string;
  height_mm: string;
  machine_profile: string;
  hoop_profile: string;
  fabric_profile: string;
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

export function toJobSettings(values: SettingsFormValues): JobSettings {
  return {
    schema_version: CONTRACT_SCHEMA_VERSION,
    target: {
      width_mm: parseMm(values.width_mm),
      height_mm: parseMm(values.height_mm),
      fit: FitMode.Contain,
    },
    machine_profile: values.machine_profile,
    hoop_profile: values.hoop_profile,
    fabric_profile: values.fabric_profile,
    color_limit: Number(values.color_limit),
    ai_provider: values.ai_provider,
  };
}
