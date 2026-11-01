import { describe, expect, it, vi } from 'vitest';
import { ErrorCode } from '../contracts/http';
import { ApiError, ClientErrorCode } from './ApiClient';
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
});
