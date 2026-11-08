// SIMULADO — cliente de API en memoria con la forma de contratos-v0.1.
// Ninguna respuesta proviene del backend real. Se activa con VITE_USE_MOCKS=true.
// Las respuestas parten de los fixtures de apps/web/mocks (marcados simulated=true).
import profilesFixture from '../../mocks/profiles.json';
import { ApiError, type ApiClient } from '../api/ApiClient';
import { ErrorCode } from '../contracts/http';
import { ACTIVE_STATUSES, JobStatus, type JobCreate, type JobResponse } from '../contracts/job';
import type { ArtifactDownload, AuthorizedArtifactManifest } from '../contracts/artifacts';
import {
  AssetPurpose,
  type DerivedRevisionRequest,
  type ProjectResponse,
  type RevisionResponse,
  type SourceAsset,
} from '../contracts/project';
import type { SewoutProjection, SewoutResponse } from '../contracts/sewout';
import { AiProvider, MediaType, type JobSettings, type ProfileCatalog } from '../contracts/settings';
import { es } from '../copy/es';
import { newIdempotencyKey } from '../shared/utils/idempotency';
import { mockStitchPreviewImage, mockTextFile, mockVectorImage } from './fixtures/media';
import { CANCEL_STOP_MS, simulateJob, type SimulatedJob } from './jobSimulation';
import { buildAnalysisSpec } from './analysis';
import { pickScenario, ScenarioOutcome, type Scenario } from './scenarios/scenarios';

const DEFAULT_STAGE_MS = 1500;
/** Nombre del guion de un job que continúa tras aprobar un análisis. */
const APPROVED_SCENARIO = 'analisis-aprobado';
/** Mismo texto que escribe el backend para una imagen enviada sin análisis de IA. */
const SKIPPED_BY_CHOICE = 'Sin análisis de IA: la persona eligió continuar sin él';
const FALLBACK_RASTER_PX = { width: 800, height: 600 };
/** El contrato fija 300 s; solo las pruebas lo acortan (downloadTtlMs). */
const DEFAULT_DOWNLOAD_TTL_MS = 300_000;
const MOCK_SHA = 'a'.repeat(64);

export interface MockOptions {
  now?: () => number;
  stageMs?: number;
  ollamaAvailable?: boolean;
  /** Solo para probar vencimientos; el contrato real es siempre 300 s. */
  downloadTtlMs?: number;
  /** Recibe el nombre de cada operación llamada (para pruebas e2e). */
  onCall?: (method: string) => void;
}

interface StoredAsset {
  asset: SourceAsset;
  scenario: Scenario;
  objectUrl: string;
}

async function readImageSize(file: File): Promise<{ width: number; height: number }> {
  if (typeof createImageBitmap !== 'function') return FALLBACK_RASTER_PX;
  try {
    const bitmap = await createImageBitmap(file);
    return { width: bitmap.width, height: bitmap.height };
  } catch {
    return FALLBACK_RASTER_PX;
  }
}

function problem(code: string, detail?: string): ApiError {
  return new ApiError(code, detail ?? es.errors.byCode[code] ?? es.errors.generic);
}

function liveUrl(kind: string): string {
  if (kind === 'editable_svg' || kind === 'inkstitch_svg') return mockVectorImage();
  if (kind === 'preview_png') return mockStitchPreviewImage();
  return mockTextFile(kind);
}

export function createMockApiClient(options: MockOptions = {}): ApiClient {
  const now = options.now ?? Date.now;
  const stageMs = options.stageMs ?? DEFAULT_STAGE_MS;
  const downloadTtlMs = options.downloadTtlMs ?? DEFAULT_DOWNLOAD_TTL_MS;
  const catalog = structuredClone(profilesFixture.payload) as ProfileCatalog;
  if (options.ollamaAvailable === false) {
    const ollama = catalog.providers.find((p) => p.provider_id === AiProvider.Ollama);
    if (ollama) {
      ollama.available = false;
      ollama.unavailable_reason = 'SIMULADO: el modelo local no está disponible en el servidor.';
    }
  }
  const projects = new Map<string, ProjectResponse>();
  const assets = new Map<string, StoredAsset>();
  const revisions = new Map<string, RevisionResponse & { settings: JobSettings }>();
  const jobs = new Map<string, SimulatedJob>();
  const sewouts = new Map<string, SewoutResponse[]>();
  const replays = new Map<string, { fingerprint: string; value: unknown }>();
  let counter = 0;
  const nextId = (prefix: string) => `${prefix}_sim_${String(++counter).padStart(3, '0')}`;
  const iso = (ms: number) => new Date(ms).toISOString();

  /** Misma clave y mismo contenido repite la respuesta; distinto contenido es conflicto. */
  async function idempotent<T>(scope: string, key: string | undefined, fingerprint: unknown, produce: () => Promise<T>): Promise<T> {
    const id = `${scope}:${key ?? newIdempotencyKey()}`;
    const print = JSON.stringify(fingerprint);
    const known = replays.get(id);
    if (known) {
      if (known.fingerprint !== print) throw problem(ErrorCode.IdempotencyConflict);
      return structuredClone(known.value) as T;
    }
    const value = await produce();
    replays.set(id, { fingerprint: print, value: structuredClone(value) });
    return value;
  }

  const requireJob = (jobId: string): SimulatedJob => {
    const job = jobs.get(jobId);
    if (!job) throw problem(ErrorCode.NotFound);
    return job;
  };
  const latestSewout = (revisionId: string): SewoutProjection | null => {
    const latest = sewouts.get(revisionId)?.at(-1);
    if (!latest) return null;
    return {
      sewout_id: latest.sewout_id,
      revision_id: latest.revision_id,
      status: latest.status,
      tested_at: latest.tested_at,
      observations: latest.observations,
      photo_asset_ids: latest.photo_asset_ids,
    };
  };
  const view = (job: SimulatedJob): JobResponse => simulateJob(job, now(), stageMs, latestSewout(job.revisionId));

  // Cada emisión lleva su marca (#issued) para poder distinguir un enlace nuevo de uno anterior.
  const freshDownload = (url: string): ArtifactDownload => ({
    url: `${url}#issued=${now()}`,
    issued_at: iso(now()),
    expires_at: iso(now() + downloadTtlMs),
  });
  const assetView = (stored: StoredAsset): SourceAsset => ({
    ...stored.asset,
    // El backend real devuelve null para un SVG (el contrato lo permite): no se simula con una URL ficticia.
    original_download: stored.asset.media_type === MediaType.Svg ? null : freshDownload(stored.objectUrl),
  });

  function startJob(
    projectId: string,
    revisionId: string,
    stored: StoredAsset,
    settings: JobSettings,
    scenario: Scenario,
    parentJobId: string | null,
  ): JobResponse {
    const { original_width_px: w, original_height_px: h } = stored.asset;
    const job: SimulatedJob = {
      id: nextId('job'),
      projectId,
      revisionId,
      assetId: stored.asset.asset_id,
      inputKind: stored.asset.media_type === MediaType.Svg ? 'prepared_svg' : 'raster_image',
      settings,
      scenario,
      parentJobId,
      createdAt: now(),
      aspectRatio: w && h ? w / h : null,
      assetPx: w && h ? { width: w, height: h } : null,
      cancelRequestedAt: null,
    };
    jobs.set(job.id, job);
    return view(job);
  }

  const client: ApiClient = {
    isSimulated: true,
    async getProfiles() {
      return structuredClone(catalog);
    },
    async listProjects() {
      return { schema_version: '0.1', items: [...projects.values()], next_cursor: null };
    },
    createProject(name, key) {
      return idempotent('project', key, { name }, async () => {
        const project: ProjectResponse = {
          schema_version: '0.1',
          project_id: nextId('project'),
          name: name.trim(),
          created_at: iso(now()),
        };
        projects.set(project.project_id, project);
        return project;
      });
    },
    async getProject(projectId) {
      const project = projects.get(projectId);
      if (!project) throw problem(ErrorCode.NotFound);
      return {
        schema_version: '0.1',
        project,
        assets: [...assets.values()].filter((a) => a.asset.project_id === projectId).map(assetView),
        jobs: [...jobs.values()].filter((j) => j.projectId === projectId).map(view),
        assets_next_cursor: null,
        jobs_next_cursor: null,
      };
    },
    uploadAsset(projectId, file, key, purpose = AssetPurpose.Design) {
      return idempotent('asset', key, { projectId, name: file.name, size: file.size, purpose }, async () => {
        if (!projects.has(projectId)) throw problem(ErrorCode.NotFound);
        const limits = catalog.upload_limits;
        if (file.size > limits.max_bytes) throw problem(ErrorCode.PayloadTooLarge);
        if (!(limits.accepted_mime_types as string[]).includes(file.type)) throw problem(ErrorCode.UnsupportedMediaType);
        const isSvg = file.type === MediaType.Svg;
        if (purpose === AssetPurpose.SewoutPhoto && isSvg) throw problem(ErrorCode.InvalidRequest);
        const size = isSvg ? null : await readImageSize(file);
        const objectUrl = typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : mockVectorImage();
        const asset: SourceAsset = {
          schema_version: '0.1',
          asset_id: nextId('asset'),
          project_id: projectId,
          sha256: MOCK_SHA,
          media_type: file.type as SourceAsset['media_type'],
          original_filename: file.name,
          original_download: null,
          original_width_px: size?.width ?? null,
          original_height_px: size?.height ?? null,
          crop_px: null,
          original_preserved: true,
          purpose,
        };
        const stored = { asset, scenario: pickScenario(file.name, isSvg), objectUrl };
        assets.set(asset.asset_id, stored);
        return assetView(stored);
      });
    },
    createInitialRevision(projectId, request, key) {
      return idempotent('revision', key, { projectId, request }, async () => {
        if (!projects.has(projectId)) throw problem(ErrorCode.NotFound);
        if (request.base_revision_id !== null) throw problem(ErrorCode.RevisionConflict);
        const revision: RevisionResponse = {
          schema_version: '0.1',
          revision_id: nextId('rev'),
          project_id: projectId,
          base_revision_id: null,
          reason: request.reason,
          created_at: iso(now()),
          kind: 'initial',
          parent_job_id: null,
          job_id: null,
        };
        revisions.set(revision.revision_id, { ...revision, settings: request.settings });
        return revision;
      });
    },
    createJob(projectId, request: JobCreate, key) {
      return idempotent('job', key, { projectId, request }, async () => {
        const stored = assets.get(request.asset_id);
        const revision = revisions.get(request.revision_id);
        if (!stored || !revision || stored.asset.project_id !== projectId || revision.project_id !== projectId) {
          throw problem(ErrorCode.NotFound);
        }
        const provider = request.settings.ai_provider;
        const isSvg = request.input_kind === 'prepared_svg';
        const available = catalog.providers.find((p) => p.provider_id === provider)?.available ?? false;
        if (provider !== AiProvider.None && !available) throw problem(ErrorCode.InvalidRequest);
        // Una imagen con proveedor "none" se procesa sin análisis: la etapa se omite con motivo y nada pausa el trabajo.
        const scenario: Scenario =
          provider === AiProvider.None && !isSvg
            ? {
                ...stored.scenario,
                outcome: stored.scenario.outcome === ScenarioOutcome.AnalysisReview ? ScenarioOutcome.Ready : stored.scenario.outcome,
                skipped: ['analyzing'],
                skipReason: SKIPPED_BY_CHOICE,
              }
            : stored.scenario;
        return startJob(projectId, revision.revision_id, stored, request.settings, scenario, null);
      });
    },
    async getJob(jobId) {
      return view(requireJob(jobId));
    },
    async getArtifacts(jobId): Promise<AuthorizedArtifactManifest> {
      const manifest = view(requireJob(jobId)).artifact_manifest;
      if (!manifest) throw problem(ErrorCode.ArtifactsUnavailable);
      // Siempre URLs nuevas, con TTL de 300 s desde ahora.
      manifest.artifacts = manifest.artifacts.map((a) => {
        const download = freshDownload(liveUrl(a.kind));
        return { ...a, download, download_url: download.url, expires_at: download.expires_at };
      });
      return manifest;
    },
    cancelJob(jobId, key) {
      return idempotent('cancel', key, { jobId }, async () => {
        const job = requireJob(jobId);
        if (ACTIVE_STATUSES.includes(view(job).status) && job.cancelRequestedAt === null) {
          job.cancelRequestedAt = now();
        }
        return view(job);
      });
    },
    // Orden 3.2 (SIMULADO): sin medir píxeles; solo para recorrer la pantalla. El número real lo mide el servidor.
    async getLegibility(_projectId, assetId, query) {
      if (!assets.has(assetId)) throw problem(ErrorCode.NotFound);
      const thin = Math.min(0.95, Math.max(0.02, 18 / Math.max(query.width_mm, 1)));
      const minimum = 120;
      return {
        schema_version: '0.1-legibility',
        requested_width_mm: query.width_mm,
        requested_height_mm: query.height_mm,
        ink_width_mm: query.width_mm * 0.9,
        ink_height_mm: query.height_mm * 0.9,
        thin_share_below_0_6_mm: thin,
        thin_share_below_0_8_mm: Math.min(1, thin * 1.5),
        ink_area_share_below_0_6_mm: thin / 2,
        warn: thin > 0.3,
        message: thin > 0.3
          ? `El ${Math.round(thin * 100)}% del trazo mide menos de 0,6 mm; a ${Math.round(query.width_mm * 0.9)} mm las letras no van a quedar legibles. El tamaño mínimo para que el 80% del trazo supere 0,8 mm es de ~${minimum} x ${minimum} mm.`
          : null,
        minimum_size: {
          already_legible: query.width_mm >= minimum,
          scale_factor: minimum / (query.width_mm * 0.9),
          ink_width_mm: minimum,
          ink_height_mm: minimum,
          fits_in_hoop: query.hoop_width_mm === undefined ? null : minimum <= query.hoop_width_mm,
          message: `El tamaño mínimo para que el 80% del trazo supere 0,8 mm es de ~${minimum} x ${minimum} mm.`,
        },
        margin_option: null,
        palette_cleaning_applied: true,
        inks: ['#1f3a93'],
        method: 'SIMULADO',
      };
    },
    // H2 (confirmado por OpenCode, aún fuera de OpenAPI v0.1): 200 si el job tiene un análisis asociado,
    // propio o el aprobado de su padre en un job de continuación; 404 en cualquier otro caso.
    async getAnalysis(jobId) {
      const job = requireJob(jobId);
      if (job.scenario.outcome === ScenarioOutcome.AnalysisReview) return buildAnalysisSpec(job);
      const parent = job.parentJobId ? jobs.get(job.parentJobId) : undefined;
      if (job.scenario.name === APPROVED_SCENARIO && parent) return buildAnalysisSpec(parent);
      throw problem(ErrorCode.NotFound);
    },
    // H2 (confirmado): aprobar o cambiar de proveedor crea un job nuevo; el original no cambia.
    decideAnalysis(jobId, decision, key) {
      return idempotent('analysis-decision', key, { jobId, decision }, async () => {
        const parent = requireJob(jobId);
        const stored = assets.get(parent.assetId);
        if (!stored || parent.scenario.outcome !== ScenarioOutcome.AnalysisReview || view(parent).status !== JobStatus.NeedsReview) {
          throw problem(ErrorCode.RevisionConflict);
        }
        if (decision.action === 'approve') {
          // Las regiones marcadas deben ser del análisis; solo se guardan como metadato de la decisión.
          const known = new Set(buildAnalysisSpec(parent).regions.map((r) => r.region_id));
          if (decision.flagged_region_ids.some((id) => !known.has(id))) throw problem(ErrorCode.InvalidRequest);
          const scenario: Scenario = {
            name: APPROVED_SCENARIO,
            outcome: ScenarioOutcome.Ready,
            skipped: ['analyzing'],
            skipReason: `análisis aprobado en ${parent.id}`,
          };
          // Misma revisión (los ajustes no cambian) y mismo asset.
          return startJob(parent.projectId, parent.revisionId, stored, parent.settings, scenario, parent.id);
        }
        const available = catalog.providers.find((p) => p.provider_id === decision.ai_provider)?.available;
        if (!available || decision.ai_provider === parent.settings.ai_provider) throw problem(ErrorCode.InvalidRequest);
        // ai_provider es parte de JobSettings y la revisión es inmutable: el servidor crea una revisión nueva.
        const settings = { ...parent.settings, ai_provider: decision.ai_provider };
        const revisionId = nextId('rev');
        revisions.set(revisionId, {
          schema_version: '0.1',
          revision_id: revisionId,
          project_id: parent.projectId,
          base_revision_id: parent.revisionId,
          reason: decision.action,
          created_at: iso(now()),
          kind: 'analysis_retry',
          parent_job_id: parent.id,
          job_id: null,
          settings,
        });
        return startJob(parent.projectId, revisionId, stored, settings, { ...parent.scenario, skipped: [] }, parent.id);
      });
    },
    recordSewout(projectId, request, key) {
      return idempotent('sewout', key, { projectId, request }, async () => {
        if (!projects.has(projectId)) throw problem(ErrorCode.NotFound);
        const revision = revisions.get(request.revision_id);
        if (!revision || revision.project_id !== projectId) throw problem(ErrorCode.NotFound);
        // Invariantes de SewoutRecord (jobs.py): resultado físico ⇔ fecha de la prueba.
        const untested = request.status === 'untested';
        const empty = [request.stabilizer, request.thread, request.observations].some((t) => !t.trim());
        if (untested !== (request.tested_at === null) || empty) throw problem(ErrorCode.InvalidRequest);
        const record: SewoutResponse = {
          ...request,
          sewout_id: nextId('sewout'),
          project_id: projectId,
          recorded_at: iso(now()),
        };
        sewouts.set(request.revision_id, [...(sewouts.get(request.revision_id) ?? []), record]);
        return record;
      });
    },
    createDerivedRevision(projectId, request: DerivedRevisionRequest, key) {
      return idempotent('derived', key, { projectId, request }, async () => {
        const parent = requireJob(request.parent_job_id);
        const stored = assets.get(parent.assetId);
        if (!stored || parent.projectId !== projectId) throw problem(ErrorCode.NotFound);
        const settings: JobSettings =
          request.kind === 'size_variant' ? { ...parent.settings, target: request.target } : parent.settings;
        const revisionId = nextId('rev');
        revisions.set(revisionId, {
          schema_version: '0.1',
          revision_id: revisionId,
          project_id: projectId,
          base_revision_id: parent.revisionId,
          reason: request.kind,
          created_at: iso(now()),
          kind: request.kind,
          parent_job_id: parent.id,
          job_id: null,
          settings,
        });
        const scenario: Scenario = { ...parent.scenario, outcome: ScenarioOutcome.Ready, failAt: undefined };
        return startJob(projectId, revisionId, stored, settings, scenario, parent.id);
      });
    },
  };
  return options.onCall ? traced(client, options.onCall) : client;
}

/** Avisa de cada operación llamada, sin alterar su resultado. */
function traced(client: ApiClient, onCall: (method: string) => void): ApiClient {
  const wrapped: Record<string, unknown> = { ...client };
  for (const [name, value] of Object.entries(client)) {
    if (typeof value !== 'function') continue;
    wrapped[name] = (...args: unknown[]) => {
      onCall(name);
      return (value as (...a: unknown[]) => unknown)(...args);
    };
  }
  return wrapped as unknown as ApiClient;
}

export { CANCEL_STOP_MS };
