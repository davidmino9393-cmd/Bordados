import { SewoutStatus, type SewoutRecordRequest } from '../../contracts/sewout';
import { CONTRACT_SCHEMA_VERSION } from '../../contracts/version';

/** Largo máximo de los textos obligatorios (NonEmpty en el contrato). */
export const SEWOUT_TEXT_MAX = 2000;

export interface SewoutFormValues {
  status: SewoutStatus | '';
  /** Valor de <input type="datetime-local"> (hora local), p. ej. 2026-11-01T11:00. */
  tested_at: string;
  fabric_profile: string;
  stabilizer: string;
  thread: string;
  observations: string;
}

export type SewoutErrorField = 'status' | 'tested_at' | 'fabric_profile' | 'stabilizer' | 'thread' | 'observations';
export type SewoutErrorKind = 'required' | 'future' | 'tooLong';
export type SewoutErrors = Partial<Record<SewoutErrorField, SewoutErrorKind>>;

const TEXT_FIELDS = ['stabilizer', 'thread', 'observations'] as const;

export function validateSewout(values: SewoutFormValues, now: number): SewoutErrors {
  const errors: SewoutErrors = {};
  if (!values.status) errors.status = 'required';
  if (!values.fabric_profile) errors.fabric_profile = 'required';
  for (const field of TEXT_FIELDS) {
    const text = values[field].trim();
    if (!text) errors[field] = 'required';
    else if (text.length > SEWOUT_TEXT_MAX) errors[field] = 'tooLong';
  }
  // Un resultado físico exige la fecha de la prueba; "sin probar" no la admite.
  if (values.status && values.status !== SewoutStatus.Untested) {
    const tested = Date.parse(values.tested_at);
    if (Number.isNaN(tested)) errors.tested_at = 'required';
    else if (tested > now) errors.tested_at = 'future';
  }
  return errors;
}

/** Arma el SewoutRecord del contrato; `tested_at` sale en UTC con zona explícita (AwareDatetime). */
export function toSewoutRequest(values: SewoutFormValues, revisionId: string): SewoutRecordRequest {
  const status = values.status as SewoutStatus;
  return {
    schema_version: CONTRACT_SCHEMA_VERSION,
    revision_id: revisionId,
    status,
    tested_at: status === SewoutStatus.Untested ? null : new Date(values.tested_at).toISOString(),
    fabric_profile: values.fabric_profile,
    stabilizer: values.stabilizer.trim(),
    thread: values.thread.trim(),
    observations: values.observations.trim(),
    photo_asset_ids: [],
  };
}
