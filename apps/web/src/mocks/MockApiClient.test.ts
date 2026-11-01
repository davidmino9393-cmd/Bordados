import { beforeEach, describe, expect, it } from 'vitest';
import { JobStatus, StageState } from '../contracts/job';
import { CONTRACT_SCHEMA_VERSION } from '../contracts/version';
import { AiProvider, FitMode, type JobSettings } from '../contracts/settings';
import { createMockApiClient } from './MockApiClient';
import { QUEUE_MS } from './jobSimulation';
import type { ApiClient } from '../api/ApiClient';

const STAGE_MS = 1000;
const WELL_PAST_END = QUEUE_MS + 10 * STAGE_MS;
const settings: JobSettings = {
  schema_version: CONTRACT_SCHEMA_VERSION,
  target: { width_mm: 130, height_mm: 120, fit: FitMode.Contain },
  machine_profile: 'janome_mc550e',
  hoop_profile: 'hoop_large',
  fabric_profile: 'gabardina_inicial',
  color_limit: 3,
  ai_provider: AiProvider.OpenAI,
};

let clock = 0;
let api: ApiClient;
const file = (name: string, type = 'image/png') => new File(['x'], name, { type });

async function start(name: string, type?: string) {
  const project = await api.createProject('Prueba');
  const asset = await api.uploadAsset(project.id, file(name, type));
  const job = await api.createJob(project.id, asset.id, settings, `key-${name}`);
  return { project, asset, job };
}

beforeEach(() => {
  clock = 1_000;
  api = createMockApiClient({ now: () => clock, stageMs: STAGE_MS });
});

describe('MockApiClient (SIMULADO)', () => {
  it('avanza por las etapas reales hasta ready_for_sewout', async () => {
    const { job } = await start('logo.png');
    expect(job.status).toBe(JobStatus.Queued);
    const seen: string[] = [];
    for (let i = 0; i < 6; i++) {
      clock += i === 0 ? QUEUE_MS : STAGE_MS;
      seen.push((await api.getJob(job.id)).status);
    }
    expect(seen).toEqual([
      JobStatus.Analyzing,
      JobStatus.Vectorizing,
      JobStatus.Digitizing,
      JobStatus.Validating,
      JobStatus.ReadyForSewout,
      JobStatus.ReadyForSewout,
    ]);
  });

  it('registra análisis y vectorización como omitidos para un SVG preparado', async () => {
    const { job } = await start('preparado.svg', 'image/svg+xml');
    const stages = Object.fromEntries(job.stages.map((s) => [s.stage, s.state]));
    expect(stages.analyzing).toBe(StageState.Skipped);
    expect(stages.vectorizing).toBe(StageState.Skipped);
    clock += QUEUE_MS;
    expect((await api.getJob(job.id)).status).toBe(JobStatus.Digitizing);
    clock += STAGE_MS;
    expect((await api.getJob(job.id)).status).toBe(JobStatus.Validating);
  });

  it('falla en la etapa indicada con causa legible', async () => {
    const { job } = await start('logo-fallo.png');
    clock += WELL_PAST_END;
    const failed = await api.getJob(job.id);
    expect(failed.status).toBe(JobStatus.Failed);
    expect(failed.failure?.stage).toBe(JobStatus.Digitizing);
    expect(failed.stages.find((s) => s.stage === 'digitizing')?.state).toBe(StageState.Failed);
    expect((await api.getArtifacts(job.id)).artifacts).toEqual([]);
  });

  it('pide revisión con causa y objetos concretos', async () => {
    const { job } = await start('logo-revision.png');
    clock += WELL_PAST_END;
    const reviewed = await api.getJob(job.id);
    expect(reviewed.status).toBe(JobStatus.NeedsReview);
    expect(reviewed.review?.issues[0].object_ids).toEqual(['obj_007']);
    expect(reviewed.review?.regions[0].object_id).toBe('obj_007');
  });

  it('cancela un trabajo en curso y no deja archivos', async () => {
    const { job } = await start('logo.png');
    clock += QUEUE_MS + STAGE_MS;
    const cancelled = await api.cancelJob(job.id);
    expect(cancelled.status).toBe(JobStatus.Cancelled);
    clock += 10 * STAGE_MS;
    expect((await api.getJob(job.id)).status).toBe(JobStatus.Cancelled);
    expect((await api.getArtifacts(job.id)).artifacts).toEqual([]);
  });

  it('no cancela un trabajo ya terminado', async () => {
    const { job } = await start('logo.png');
    clock += WELL_PAST_END;
    expect((await api.cancelJob(job.id)).status).toBe(JobStatus.ReadyForSewout);
  });

  it('los artefactos pertenecen al trabajo y la muestra física queda sin probar', async () => {
    const a = await start('uno.png');
    const b = await start('dos.png');
    clock += WELL_PAST_END;
    const manifestA = await api.getArtifacts(a.job.id);
    const manifestB = await api.getArtifacts(b.job.id);
    expect(manifestA.artifacts.every((x) => x.job_id === a.job.id)).toBe(true);
    expect(manifestB.artifacts.every((x) => x.job_id === b.job.id)).toBe(true);
    expect(manifestA.metrics?.source).toBe('jef_reread');
    expect((await api.getJob(a.job.id)).sewout_status).toBe('untested');
  });

  it('es idempotente con la misma clave', async () => {
    const project = await api.createProject('P');
    const asset = await api.uploadAsset(project.id, file('logo.png'));
    const first = await api.createJob(project.id, asset.id, settings, 'misma');
    const second = await api.createJob(project.id, asset.id, settings, 'misma');
    expect(second.id).toBe(first.id);
    expect((await api.getProject(project.id)).jobs).toHaveLength(1);
  });

  it('una variante es un trabajo nuevo con otro tamaño y enlazado al origen', async () => {
    const { project, job } = await start('logo.png');
    clock += WELL_PAST_END;
    const variant = await api.createRevision(project.id, {
      kind: 'size_variant',
      parent_job_id: job.id,
      target: { width_mm: 90, height_mm: 80, fit: 'contain' },
    });
    expect(variant.id).not.toBe(job.id);
    expect(variant.parent_job_id).toBe(job.id);
    expect(variant.settings.target.width_mm).toBe(90);
    expect((await api.getJob(job.id)).settings.target.width_mm).toBe(130);
  });

  it('rechaza formatos no admitidos y proveedores no disponibles', async () => {
    const project = await api.createProject('P');
    await expect(api.uploadAsset(project.id, file('x.gif', 'image/gif'))).rejects.toThrow();
    const local = createMockApiClient({ ollamaAvailable: false });
    const p = await local.createProject('P');
    const asset = await local.uploadAsset(p.id, file('logo.png'));
    await expect(
      local.createJob(p.id, asset.id, { ...settings, ai_provider: AiProvider.Ollama }, 'k'),
    ).rejects.toThrow();
  });
});
