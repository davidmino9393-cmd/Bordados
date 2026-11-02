import { act, cleanup, render, renderHook, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, ClientErrorCode, type ApiClient } from '../../api/ApiClient';
import { ApiProvider } from '../../api/ApiProvider';
import type { JobResponse } from '../../contracts/job';
import { RetryCountdown } from '../components/RetryCountdown';
import { useJobPolling } from './useJobPolling';

const timeout = () => new ApiError(ClientErrorCode.Timeout, 'El servidor tardó demasiado en responder.');
const activeJob = { job_id: 'j', status: 'analyzing' } as JobResponse;

/** Cliente de prueba: registra cuándo se llamó a getJob y responde según el guion. */
function scripted(steps: Array<'fail' | 'ok' | ApiError>) {
  const calls: Array<{ jobId: string; at: number }> = [];
  let index = 0;
  const client = {
    isSimulated: true,
    async getJob(jobId: string) {
      calls.push({ jobId, at: Date.now() });
      const step = steps[Math.min(index++, steps.length - 1)];
      if (step === 'ok') return { ...activeJob, job_id: jobId };
      throw step === 'fail' ? timeout() : step;
    },
  } as unknown as ApiClient;
  return { client, calls };
}

const wrapperFor = (client: ApiClient) =>
  function Wrapper({ children }: { children: ReactNode }) {
    return <ApiProvider client={client}>{children}</ApiProvider>;
  };

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(Math, 'random').mockReturnValue(0.5); // jitter nulo: la secuencia es exacta
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('useJobPolling: backoff ante errores transitorios', () => {
  it('reintenta a 1, 2, 4, 8, 16 s y después cada 30 s', async () => {
    const { client, calls } = scripted(['fail']);
    renderHook(() => useJobPolling('j'), { wrapper: wrapperFor(client) });
    const start = Date.now();
    await advance(91_000);
    expect(calls.map((c) => c.at - start)).toEqual([0, 1000, 3000, 7000, 15000, 31000, 61000, 91000]);
  });

  it('expone cuándo es el próximo intento para mostrar la cuenta regresiva', async () => {
    const { client } = scripted(['fail']);
    const { result } = renderHook(() => useJobPolling('j'), { wrapper: wrapperFor(client) });
    const start = Date.now();
    await advance(0);
    expect(result.current.retryAt).toBe(start + 1000);
    expect(result.current.error).toMatch(/Código de incidencia: TIMEOUT/);
    await advance(1000);
    expect(result.current.retryAt).toBe(start + 1000 + 2000);
  });

  it('reinicia el contador al cambiar de pantalla (otro trabajo)', async () => {
    const { client, calls } = scripted(['fail']);
    const { rerender } = renderHook(({ id }) => useJobPolling(id), {
      wrapper: wrapperFor(client),
      initialProps: { id: 'a' },
    });
    await advance(7000); // a: 0, 1, 3, 7 s → ya va por el cuarto intento
    const before = calls.length;
    rerender({ id: 'b' });
    await advance(0);
    const switchedAt = Date.now();
    await advance(3000);
    const forB = calls.filter((c) => c.jobId === 'b').map((c) => c.at - switchedAt);
    expect(calls.length).toBeGreaterThan(before);
    expect(forB).toEqual([0, 1000, 3000]);
    expect(calls.filter((c) => c.jobId === 'a')).toHaveLength(before);
  });

  it('reinicia el contador tras una respuesta correcta', async () => {
    const { client, calls } = scripted(['fail', 'fail', 'ok', 'fail', 'fail']);
    renderHook(() => useJobPolling('j'), { wrapper: wrapperFor(client) });
    const start = Date.now();
    await advance(8000);
    // 0 falla · +1 s falla · +2 s ok · +1 s (consulta normal) falla · +1 s (no +4 s) vuelve a intentar
    expect(calls.map((c) => c.at - start).slice(0, 5)).toEqual([0, 1000, 3000, 4000, 5000]);
  });

  it('limpia la cuenta regresiva cuando vuelve a responder', async () => {
    const { client } = scripted(['fail', 'ok']);
    const { result } = renderHook(() => useJobPolling('j'), { wrapper: wrapperFor(client) });
    await advance(0);
    expect(result.current.retryAt).not.toBeNull();
    await advance(1000);
    expect(result.current.retryAt).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it.each([
    ['NOT_FOUND', 404],
    ['FORBIDDEN', 403],
    ['MALFORMED_REQUEST', 400],
    ['INVALID_REQUEST', 422],
    [ClientErrorCode.NotImplemented, 501],
  ])('un error permanente (%s) no se reintenta', async (code, status) => {
    const { client, calls } = scripted([new ApiError(code, 'No.', status)]);
    const { result } = renderHook(() => useJobPolling('j'), { wrapper: wrapperFor(client) });
    await advance(120_000);
    expect(calls).toHaveLength(1);
    expect(result.current.retryAt).toBeNull();
    expect(result.current.error).toContain(`Código de incidencia: ${code}`);
  });
});

describe('RetryCountdown', () => {
  it('muestra «Reintentando en X s» y baja cada segundo', async () => {
    render(<RetryCountdown retryAt={Date.now() + 4000} />);
    expect(screen.getByText('Reintentando en 4 s…')).toBeInTheDocument();
    await advance(1000);
    expect(screen.getByText('Reintentando en 3 s…')).toBeInTheDocument();
    await advance(5000);
    expect(screen.getByText('Reintentando en 0 s…')).toBeInTheDocument();
  });
});
