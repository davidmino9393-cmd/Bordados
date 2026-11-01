import { afterEach, describe, expect, it, vi } from 'vitest';
import { ErrorCode } from '../contracts/http';
import { errorMessage } from '../shared/hooks/useAsync';
import { ApiError, ClientErrorCode, isTransientError } from './ApiClient';
import { createHttpApiClient } from './HttpApiClient';

const json = (body: unknown, status = 200, type = 'application/json') =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': type, 'X-Request-ID': 'req_1' } });

function clientWith(fetchImpl: typeof fetch) {
  return createHttpApiClient({ fetchImpl });
}

describe('createHttpApiClient (contratos-v0.1)', () => {
  it('usa /api/v1, no cachea y envía Idempotency-Key solo en los POST', async () => {
    const fetchImpl = vi.fn(async () => json({ ok: true }));
    const api = clientWith(fetchImpl as unknown as typeof fetch);
    await api.getJob('job_1');
    await api.cancelJob('job_1', 'clave-fija');
    const [get, post] = fetchImpl.mock.calls as unknown as Array<[string, RequestInit]>;
    expect(get[0]).toBe('/api/v1/jobs/job_1');
    expect(get[1].cache).toBe('no-store');
    expect((get[1].headers as Record<string, string>)['Idempotency-Key']).toBeUndefined();
    expect(post[0]).toBe('/api/v1/jobs/job_1/cancel');
    expect((post[1].headers as Record<string, string>)['Idempotency-Key']).toBe('clave-fija');
  });

  it('genera una Idempotency-Key cuando no se pasa ninguna', async () => {
    const fetchImpl = vi.fn(async () => json({}));
    await clientWith(fetchImpl as unknown as typeof fetch).createProject('P');
    const init = (fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>)['Idempotency-Key']).toBeTruthy();
    expect(JSON.parse(init.body as string)).toEqual({ schema_version: '0.1', name: 'P' });
  });

  it('sube el archivo como multipart/form-data sin fijar Content-Type a mano', async () => {
    const fetchImpl = vi.fn(async () => json({}));
    await clientWith(fetchImpl as unknown as typeof fetch).uploadAsset('p1', new File(['x'], 'a.png', { type: 'image/png' }), 'k');
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v1/projects/p1/assets');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });

  it('la revisión inicial y el job usan sus rutas y cuerpos del contrato', async () => {
    const fetchImpl = vi.fn(async () => json({}));
    const api = clientWith(fetchImpl as unknown as typeof fetch);
    await api.createInitialRevision('p1', { schema_version: '0.1', base_revision_id: null, reason: 'r', settings: {} as never }, 'a');
    await api.createJob('p1', { schema_version: '0.1', asset_id: 'x', revision_id: 'r1', input_kind: 'prepared_svg', settings: {} as never }, 'b');
    const urls = fetchImpl.mock.calls.map((c) => (c as unknown as [string])[0]);
    expect(urls).toEqual(['/api/v1/projects/p1/revisions', '/api/v1/projects/p1/jobs']);
  });

  it('registra la muestra física con POST /projects/{id}/sewouts y su Idempotency-Key', async () => {
    const fetchImpl = vi.fn(async () => json({}, 201));
    await clientWith(fetchImpl as unknown as typeof fetch).recordSewout('p1', { revision_id: 'r1' } as never, 'k-sewout');
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v1/projects/p1/sewouts');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['Idempotency-Key']).toBe('k-sewout');
    expect(JSON.parse(init.body as string)).toEqual({ revision_id: 'r1' });
  });

  it('traduce application/problem+json al código del contrato y a un mensaje en español', async () => {
    const problem = {
      schema_version: '0.1', type: 'urn:embroidery:problem:forbidden', title: 'Forbidden', status: 403,
      detail: 'English detail', instance: '/api/v1/jobs/j', code: ErrorCode.Forbidden, request_id: 'req_9', errors: [],
    };
    const api = clientWith((async () => json(problem, 403, 'application/problem+json')) as unknown as typeof fetch);
    const error = (await api.getJob('j').catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: ErrorCode.Forbidden, status: 403, requestId: 'req_9' });
    expect(error.message).toBe('No tenés permiso para ver o modificar esto.');
  });

  it('un 501 se informa como operación no ofrecida todavía', async () => {
    const api = clientWith((async () => new Response('', { status: 501 })) as unknown as typeof fetch);
    const error = (await api.createJob('p', {} as never, 'k').catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ code: ClientErrorCode.NotImplemented, status: 501 });
    expect(error.message).toMatch(/todavía no ofrece/);
  });

  it('un corte de red se informa en español', async () => {
    const api = clientWith((async () => {
      throw new TypeError('fetch failed');
    }) as unknown as typeof fetch);
    await expect(api.getProfiles()).rejects.toMatchObject({ code: ClientErrorCode.Network });
  });

  describe('timeout y códigos de incidencia', () => {
    afterEach(() => vi.useRealTimers());

    it('un servidor que no responde se corta con TIMEOUT y mensaje en español', async () => {
      vi.useFakeTimers();
      const hanging = ((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('abort', 'AbortError')));
        })) as unknown as typeof fetch;
      const api = createHttpApiClient({ fetchImpl: hanging, timeoutMs: 5000 });
      const pending = api.getJob('j').catch((e: unknown) => e);
      await vi.advanceTimersByTimeAsync(5000);
      const error = (await pending) as ApiError;
      expect(error).toMatchObject({ code: ClientErrorCode.Timeout });
      expect(error.message).toMatch(/tardó demasiado/);
      expect(isTransientError(error)).toBe(true);
    });

    it('la subida admite más tiempo que una consulta común', async () => {
      vi.useFakeTimers();
      const slow = ((_url: string, init: RequestInit) =>
        new Promise((resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('abort', 'AbortError')));
          setTimeout(() => resolve(json({ asset_id: 'a' }, 201)), 8000);
        })) as unknown as typeof fetch;
      const api = createHttpApiClient({ fetchImpl: slow, timeoutMs: 5000, uploadTimeoutMs: 20_000 });
      const upload = api.uploadAsset('p', new File(['x'], 'a.png', { type: 'image/png' }), 'k');
      await vi.advanceTimersByTimeAsync(8000);
      await expect(upload).resolves.toMatchObject({ asset_id: 'a' });
    });

    it('el mensaje para el usuario incluye el código de incidencia y el id de solicitud', () => {
      const error = new ApiError('SERVICE_UNAVAILABLE', 'El servicio no está disponible.', 503, 'req_7');
      expect(errorMessage(error)).toBe(
        'El servicio no está disponible. (Código de incidencia: SERVICE_UNAVAILABLE · solicitud req_7)',
      );
      expect(isTransientError(error)).toBe(true);
      expect(isTransientError(new ApiError('NOT_FOUND', 'x', 404))).toBe(false);
      expect(isTransientError(new ApiError(ClientErrorCode.NotImplemented, 'x', 501))).toBe(false);
    });
  });
});
