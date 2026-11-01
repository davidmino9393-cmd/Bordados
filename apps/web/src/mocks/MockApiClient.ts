// SIMULADO — cliente de API en memoria. Ninguna respuesta proviene del backend real.
// Se activa con VITE_USE_MOCKS=true. El comportamiento por nombre de archivo está en docs.
import { ApiError, ApiErrorCode, type ApiClient } from '../api/ApiClient';
import { ArtifactKind, type Artifact, type ArtifactManifest } from '../contracts/artifacts';
import { CANCELLABLE_STATUSES, JobStatus, type Job } from '../contracts/job';
import { AssetFormat, type Project, type RevisionRequest, type SourceAsset } from '../contracts/project';
import type { JobSettings } from '../contracts/settings';
import { mockStitchPreviewImage, mockTextFile, mockVectorImage } from './fixtures/media';
import { buildMockProfiles } from './fixtures/profiles';
import { simulateJob, type SimulatedJobRecord } from './jobSimulation';
import { pickScenario, ScenarioOutcome, type Scenario } from './scenarios/scenarios';

const DEFAULT_STAGE_MS = 1500;
const FALLBACK_ASSET_PX = { width: 800, height: 600 };
const MOCK_SHA = 'simulado'.padEnd(64, '0');
const STITCHES_PER_MM2 = 0.4;

export interface MockOptions {
  now?: () => number;
  stageMs?: number;
  ollamaAvailable?: boolean;
}

async function readImageSize(file: File): Promise<{ width: number; height: number }> {
  if (typeof createImageBitmap !== 'function') return FALLBACK_ASSET_PX;
  try {
    const bitmap = await createImageBitmap(file);
    return { width: bitmap.width, height: bitmap.height };
  } catch {
    return FALLBACK_ASSET_PX;
  }
}

function assetFormat(file: File): SourceAsset['format'] {
  if (file.type === 'image/svg+xml') return AssetFormat.Svg;
  return file.type === 'image/png' ? AssetFormat.Png : AssetFormat.Jpeg;
}

export function createMockApiClient(options: MockOptions = {}): ApiClient {
  const now = options.now ?? Date.now;
  const stageMs = options.stageMs ?? DEFAULT_STAGE_MS;
  const profiles = buildMockProfiles({ ollamaAvailable: options.ollamaAvailable ?? true });
  const projects = new Map<string, Project>();
  const assets = new Map<string, SourceAsset>();
  const scenarios = new Map<string, Scenario>();
  const records = new Map<string, SimulatedJobRecord>();
  const idempotent = new Map<string, string>();
  let counter = 0;
  const nextId = (prefix: string) => `${prefix}_sim_${String(++counter).padStart(3, '0')}`;

  const view = (record: SimulatedJobRecord): Job => simulateJob(record, now(), stageMs);
  const requireRecord = (jobId: string): SimulatedJobRecord => {
    const record = records.get(jobId);
    if (!record) throw new ApiError(ApiErrorCode.NotFound, 'No se encontró el trabajo.');
    return record;
  };

  const startJob = (
    projectId: string,
    asset: SourceAsset,
    settings: JobSettings,
    scenario: Scenario,
    parentJobId: string | null,
  ): Job => {
    const record: SimulatedJobRecord = {
      id: nextId('job'),
      projectId,
      assetId: asset.id,
      settings,
      scenario,
      parentJobId,
      createdAt: now(),
      assetWidthPx: asset.width_px,
      assetHeightPx: asset.height_px,
      cancelledAt: null,
    };
    records.set(record.id, record);
    return view(record);
  };

  const artifactsFor = (job: Job): ArtifactManifest => {
    if (job.status !== JobStatus.ReadyForSewout) {
      return { job_id: job.id, artifacts: [], metrics: null };
    }
    const asset = assets.get(job.source_asset_id);
    const { width_mm: maxW, height_mm: maxH } = job.settings.target;
    const ratio = asset ? asset.width_px / asset.height_px : 1;
    const widthMm = Math.min(maxW, maxH * ratio);
    const heightMm = widthMm / ratio;
    const make = (kind: ArtifactKind, filename: string, content_type: string, url: string): Artifact => ({
      kind,
      job_id: job.id,
      filename,
      sha256: MOCK_SHA,
      size_bytes: 1024,
      content_type,
      download_url: url,
    });
    return {
      job_id: job.id,
      artifacts: [
        make(ArtifactKind.SvgEditable, `${job.id}.svg`, 'image/svg+xml', mockVectorImage()),
        make(ArtifactKind.SvgInkStitch, `${job.id}-inkstitch.svg`, 'image/svg+xml', mockVectorImage()),
        make(ArtifactKind.Jef, `${job.id}.jef`, 'application/octet-stream', mockTextFile('JEF')),
        make(ArtifactKind.JefPreview, `${job.id}-preview.svg`, 'image/svg+xml', mockStitchPreviewImage()),
        make(ArtifactKind.Report, `${job.id}-informe.txt`, 'text/plain', mockTextFile('informe')),
      ],
      metrics: {
        source: 'jef_reread',
        width_mm: Number(widthMm.toFixed(1)),
        height_mm: Number(heightMm.toFixed(1)),
        needle_stitches: Math.round(widthMm * heightMm * STITCHES_PER_MM2),
        thread_blocks: Math.min(job.settings.color_limit, 3),
        color_changes: Math.max(0, Math.min(job.settings.color_limit, 3) - 1),
        jumps: 12,
        trims: 8,
        counting_method: 'valores simulados',
        processing_ms: stageMs * 4,
      },
    };
  };

  return {
    isSimulated: true,
    async getProfiles() {
      return profiles;
    },
    async listProjects() {
      return [...projects.values()].map((project) => {
        const jobs = [...records.values()].filter((r) => r.projectId === project.id).map(view);
        const latest = jobs.at(-1);
        return {
          ...project,
          job_count: jobs.length,
          latest_job_status: latest?.status ?? null,
          latest_sewout_status: latest?.sewout_status ?? null,
        };
      });
    },
    async createProject(name) {
      const project: Project = { id: nextId('proj'), name: name.trim(), created_at: new Date(now()).toISOString() };
      projects.set(project.id, project);
      return project;
    },
    async getProject(projectId) {
      const project = projects.get(projectId);
      if (!project) throw new ApiError(ApiErrorCode.NotFound, 'No se encontró el proyecto.');
      return {
        project,
        assets: [...assets.values()].filter((a) => a.project_id === projectId),
        jobs: [...records.values()].filter((r) => r.projectId === projectId).map(view),
      };
    },
    async uploadAsset(projectId, file) {
      if (!projects.has(projectId)) throw new ApiError(ApiErrorCode.NotFound, 'No se encontró el proyecto.');
      const limits = profiles.upload_limits;
      if (file.size > limits.max_bytes || !limits.accepted_mime_types.includes(file.type)) {
        throw new ApiError(ApiErrorCode.InvalidInput, 'El archivo no es un formato o tamaño admitido.');
      }
      const size = await readImageSize(file);
      const original_url =
        typeof URL.createObjectURL === 'function' ? URL.createObjectURL(file) : mockVectorImage();
      const asset: SourceAsset = {
        id: nextId('asset'),
        project_id: projectId,
        sha256: MOCK_SHA,
        original_filename: file.name,
        format: assetFormat(file),
        width_px: size.width,
        height_px: size.height,
        original_url,
      };
      assets.set(asset.id, asset);
      scenarios.set(asset.id, pickScenario(file.name, asset.format === AssetFormat.Svg));
      return asset;
    },
    async createJob(projectId, assetId, settings, idempotencyKey) {
      const existing = idempotent.get(idempotencyKey);
      if (existing) return view(requireRecord(existing));
      const asset = assets.get(assetId);
      const scenario = scenarios.get(assetId);
      if (!asset || !scenario || asset.project_id !== projectId) {
        throw new ApiError(ApiErrorCode.NotFound, 'No se encontró la imagen del proyecto.');
      }
      if (!profiles.providers.find((p) => p.id === settings.ai_provider)?.available) {
        throw new ApiError(ApiErrorCode.Unavailable, 'El proveedor de IA elegido no está disponible.');
      }
      const job = startJob(projectId, asset, settings, scenario, null);
      idempotent.set(idempotencyKey, job.id);
      return job;
    },
    async getJob(jobId) {
      return view(requireRecord(jobId));
    },
    async getArtifacts(jobId) {
      return artifactsFor(view(requireRecord(jobId)));
    },
    async cancelJob(jobId) {
      const record = requireRecord(jobId);
      if (CANCELLABLE_STATUSES.includes(view(record).status)) record.cancelledAt = now();
      return view(record);
    },
    async createRevision(projectId, request: RevisionRequest) {
      const parent = requireRecord(request.parent_job_id);
      const asset = assets.get(parent.assetId);
      if (!asset || parent.projectId !== projectId) {
        throw new ApiError(ApiErrorCode.NotFound, 'No se encontró el trabajo de origen.');
      }
      const settings: JobSettings =
        request.kind === 'size_variant' ? { ...parent.settings, target: request.target } : parent.settings;
      const scenario: Scenario = { ...parent.scenario, outcome: ScenarioOutcome.Ready, failAt: undefined };
      return startJob(projectId, asset, settings, scenario, parent.id);
    },
  };
}
