/** Margen para renovar un enlace antes de que venza, en ms. */
export const RENEW_MARGIN_MS = 10_000;

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
