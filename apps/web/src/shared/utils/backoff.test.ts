import { describe, expect, it } from 'vitest';
import { backoffDelay } from './backoff';

const MIDDLE = () => 0.5; // sin jitter
const LOWEST = () => 0; // −20 %
const HIGHEST = () => 1; // +20 %

describe('backoffDelay', () => {
  it('duplica la espera: 1, 2, 4, 8, 16 s y se queda en 30 s', () => {
    const delays = [0, 1, 2, 3, 4, 5, 6, 10].map((attempt) => backoffDelay(attempt, MIDDLE));
    expect(delays).toEqual([1000, 2000, 4000, 8000, 16000, 30000, 30000, 30000]);
  });

  it('aplica ±20 % de jitter alrededor de cada espera', () => {
    expect([0, 1, 2, 3, 4].map((a) => backoffDelay(a, LOWEST))).toEqual([800, 1600, 3200, 6400, 12800]);
    expect([0, 1, 2, 3, 4].map((a) => backoffDelay(a, HIGHEST))).toEqual([1200, 2400, 4800, 9600, 19200]);
  });

  it('nunca supera el tope de 30 s, ni siquiera con jitter positivo', () => {
    expect(backoffDelay(5, HIGHEST)).toBe(30000);
    expect(backoffDelay(20, HIGHEST)).toBe(30000);
    expect(backoffDelay(5, LOWEST)).toBe(24000);
  });

  it('con azar real queda siempre dentro del rango esperado', () => {
    for (let i = 0; i < 200; i++) {
      const delay = backoffDelay(2);
      expect(delay).toBeGreaterThanOrEqual(3200);
      expect(delay).toBeLessThanOrEqual(4800);
    }
  });
});
