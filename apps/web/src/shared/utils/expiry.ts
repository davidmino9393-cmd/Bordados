import type { ArtifactDownload } from '../../contracts/artifacts';

/** Margen máximo para renovar un enlace antes de que venza, en ms (con el TTL real de 300 s). */
export const RENEW_MARGIN_MS = 10_000;
/** Un TTL corto no puede provocar un bucle de consultas: espera mínima entre renovaciones. */
export const MIN_RENEW_WAIT_MS = 500;
const MARGIN_RATIO = 0.2;

export function msUntil(isoDate: string, now: number): number {
  return Date.parse(isoDate) - now;
}

export function isExpired(isoDate: string | null | undefined, now: number, marginMs = 0): boolean {
  return !isoDate || msUntil(isoDate, now) <= marginMs;
}

/** Vencimiento más próximo de una lista (fechas ISO); undefined si no hay ninguna. */
export function earliestExpiry(dates: Array<string | null | undefined>): string | undefined {
  const valid = dates.filter((d): d is string => !!d);
  return valid.sort((a, b) => Date.parse(a) - Date.parse(b))[0];
}

/** El enlace que vence primero (su emisión se usa para calcular el margen). */
export function earliestDownload(downloads: Array<ArtifactDownload | null | undefined>): ArtifactDownload | undefined {
  const valid = downloads.filter((d): d is ArtifactDownload => !!d);
  return valid.sort((a, b) => Date.parse(a.expires_at) - Date.parse(b.expires_at))[0];
}

/** 10 s con el TTL de 300 s; como máximo el 20 % de la vida del enlace si es más corta. */
export function renewMargin(download: ArtifactDownload): number {
  const ttl = Date.parse(download.expires_at) - Date.parse(download.issued_at);
  return Math.min(RENEW_MARGIN_MS, Math.max(0, ttl * MARGIN_RATIO));
}
