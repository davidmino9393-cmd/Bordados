import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Testing Library solo avanza los timers falsos si ve un global `jest`.
// Con esto, findBy*/waitFor funcionan bajo vi.useFakeTimers().
Object.assign(globalThis, { jest: { advanceTimersByTime: (ms: number) => vi.advanceTimersByTime(ms) } });
