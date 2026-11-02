import type { ProblemResponse } from '../contracts/http';
import { es } from '../copy/es';
import { newIdempotencyKey } from '../shared/utils/idempotency';
import { ApiError, ClientErrorCode, type ApiClient } from './ApiClient';

const API_PREFIX = '/api/v1';
const PROBLEM_CONTENT_TYPE = 'application/problem+json';
const HTTP_NOT_IMPLEMENTED = 501;

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_UPLOAD_TIMEOUT_MS = 120_000;
/** Máximo que admite el backend por página; menos viajes y la lista más completa de entrada. */
const PAGE_LIMIT = 100;

/** `?limit=…&cursor=…` con solo los parámetros presentes. */
function pageQuery(cursors: Record<string, string | undefined>): string {
  const query = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  for (const [name, value] of Object.entries(cursors)) if (value) query.set(name, value);
  return `?${query}`;
}

interface RequestOptions {
  body?: unknown;
  form?: FormData;
  key?: string;
  timeoutMs?: number;
}

export interface HttpClientConfig {
  /** Vacío = mismo origen (despliegue previsto). */
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  /** Tiempo máximo de espera por respuesta; las subidas usan `uploadTimeoutMs`. */
  timeoutMs?: number;
  uploadTimeoutMs?: number;
}

async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get('X-Request-ID') ?? undefined;
  if (response.status === HTTP_NOT_IMPLEMENTED) {
    return new ApiError(ClientErrorCode.NotImplemented, es.errors.notImplemented, response.status, requestId);
  }
  const isProblem = (response.headers.get('Content-Type') ?? '').includes(PROBLEM_CONTENT_TYPE);
  if (isProblem) {
    try {
      const problem = (await response.json()) as ProblemResponse;
      const message = es.errors.byCode[problem.code] ?? problem.detail;
      return new ApiError(problem.code, message, response.status, problem.request_id);
    } catch {
      // cae al error genérico
    }
  }
  return new ApiError(ClientErrorCode.Unexpected, es.errors.generic, response.status, requestId);
}

/**
 * Cliente real del contrato v0.1 (openapi.json). Autenticación: el despliegue es de
 * mismo origen y el navegador gestiona HTTP Basic; la web nunca guarda credenciales
 * ni claves de proveedores.
 */
export function createHttpApiClient(config: HttpClientConfig = {}): ApiClient {
  const base = config.baseUrl ?? '';
  const doFetch = config.fetchImpl ?? ((input, init) => fetch(input, init));
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const uploadTimeoutMs = config.uploadTimeoutMs ?? DEFAULT_UPLOAD_TIMEOUT_MS;

  async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (method === 'POST') headers['Idempotency-Key'] = options.key ?? newIdempotencyKey();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? timeoutMs);
    let response: Response;
    try {
      response = await doFetch(`${base}${API_PREFIX}${path}`, {
        method,
        headers,
        body: options.form ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
        cache: 'no-store',
        credentials: 'same-origin',
        signal: controller.signal,
      });
    } catch {
      if (controller.signal.aborted) throw new ApiError(ClientErrorCode.Timeout, es.errors.timeout);
      throw new ApiError(ClientErrorCode.Network, es.errors.network);
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) throw await toApiError(response);
    return (await response.json()) as T;
  }

  const id = encodeURIComponent;
  return {
    isSimulated: false,
    getProfiles: () => request('GET', '/profiles'),
    listProjects: (cursor) => request('GET', `/projects${pageQuery({ cursor })}`),
    createProject: (name, key) =>
      request('POST', '/projects', { key, body: { schema_version: '0.1', name } }),
    getProject: (projectId, cursors) =>
      request('GET', `/projects/${id(projectId)}${pageQuery({ assets_cursor: cursors?.assetsCursor, jobs_cursor: cursors?.jobsCursor })}`),
    uploadAsset: (projectId, file, key, purpose) => {
      const form = new FormData();
      if (purpose) form.append('purpose', purpose);
      form.append('file', file);
      return request('POST', `/projects/${id(projectId)}/assets`, { key, form, timeoutMs: uploadTimeoutMs });
    },
    createInitialRevision: (projectId, body, key) =>
      request('POST', `/projects/${id(projectId)}/revisions`, { key, body }),
    createJob: (projectId, body, key) => request('POST', `/projects/${id(projectId)}/jobs`, { key, body }),
    getJob: (jobId) => request('GET', `/jobs/${id(jobId)}`),
    getArtifacts: (jobId) => request('GET', `/jobs/${id(jobId)}/artifacts`),
    cancelJob: (jobId, key) =>
      request('POST', `/jobs/${id(jobId)}/cancel`, { key, body: { schema_version: '0.1' } }),
    // H2: forma confirmada por OpenCode; falta incorporarla a OpenAPI/contracts. La web solo las usa con un
    // job de imagen en needs_review por análisis, algo que el backend de H0-04 todavía no produce.
    getAnalysis: (jobId) => request('GET', `/jobs/${id(jobId)}/analysis`),
    decideAnalysis: (jobId, body, key) => request('POST', `/jobs/${id(jobId)}/analysis-decision`, { key, body }),
    recordSewout: (projectId, body, key) => request('POST', `/projects/${id(projectId)}/sewouts`, { key, body }),
    createDerivedRevision: (projectId, body, key) =>
      request('POST', `/projects/${id(projectId)}/revisions`, { key, body }),
  };
}
