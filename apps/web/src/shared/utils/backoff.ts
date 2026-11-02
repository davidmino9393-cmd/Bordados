const BACKOFF_BASE_MS = 1000;
const BACKOFF_CAP_MS = 30_000;
const JITTER_RATIO = 0.2;

/**
 * Espera antes del reintento número `attempt` (0 = primer reintento):
 * 1 s, 2 s, 4 s, 8 s, 16 s y luego 30 s, con ±20 % de jitter para que varios
 * clientes no reintenten a la vez. Nunca supera el tope de 30 s.
 */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(BACKOFF_BASE_MS * 2 ** attempt, BACKOFF_CAP_MS);
  const jitter = 1 + (random() * 2 - 1) * JITTER_RATIO;
  return Math.min(Math.round(base * jitter), BACKOFF_CAP_MS);
}
