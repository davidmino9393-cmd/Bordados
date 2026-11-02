import { beforeEach, describe, expect, it } from 'vitest';
import type { ApiClient } from '../api/ApiClient';
import { startGeneration } from '../api/startGeneration';
import { ErrorCode } from '../contracts/http';
import { JobStatus, StageOutcome } from '../contracts/job';
import type { SourceAsset } from '../contracts/project';
import { AiProvider, type JobSettings } from '../contracts/settings';
import { toJobSettings } from '../features/settings/validateSettings';
import { QUEUE_MS, CANCEL_STOP_MS } from './jobSimulation';
import { createMockApiClient } from './MockApiClient';

const STAGE_MS = 1000;
const WELL_PAST_END = QUEUE_MS + 10 * STAGE_MS;
const TTL_MS = 300_000;

let clock = 0;
let api: ApiClient;
const file = (name: string, type = 'image/png') => new File(['x'], name, { type });

async function settingsFor(provider: AiProvider = AiProvider.OpenAI): Promise<JobSettings> {
  const catalog = await api.getProfiles();
  return toJobSettings(
    {
      width_mm: '130',
      height_mm: '120',
      machine_profile: 'janome_mc550e',
      hoop_profile: 'sq20b',
      fabric_profile: 'gabardina_inicial',
      thread_profile: 'embroidery_thread_initial',
      color_limit: '3',
      ai_provider: provider,
    },
    catalog,
  );
}

async function start(name: string, type?: string, key = `key-${name}`) {
  const project = await api.createProject('Prueba');
  const asset = await api.uploadAsset(project.project_id, file(name, type));
  const provider = type === 'image/svg+xml' ? AiProvider.None : AiProvider.OpenAI;
  const job = await startGeneration(api, asset, await settingsFor(provider), key);
  return { project, asset, job };
}

beforeEach(() => {
  clock = Date.parse('2026-11-01T12:00:00Z');
  api = createMockApiClient({ now: () => clock, stageMs: STAGE_MS });
});

describe('MockApiClient (SIMULADO, forma de contratos-v0.1)', () => {
  it('sigue el flujo inicial: revisión inicial con base null y luego el job que la referencia', async () => {
    const project = await api.createProject('P');
    const asset = await api.uploadAsset(project.project_id, file('logo.png'));
    const settings = await settingsFor();
    const revision = await api.createInitialRevision(
      project.project_id,
      { schema_version: '0.1', base_revision_id: null, reason: 'Ajustes iniciales', settings },
      'k-rev',
    );
    expect(revision).toMatchObject({ kind: 'initial', base_revision_id: null, job_id: null, parent_job_id: null });
    const job = await api.createJob(
      project.project_id,
      { schema_version: '0.1', asset_id: asset.asset_id, revision_id: revision.revision_id, input_kind: 'raster_image', settings },
      'k-job',
    );
    expect(job.revision_id).toBe(revision.revision_id);
    expect(job.status).toBe(JobStatus.Queued);
  });

  it('no crea una revisión implícita: un job con revisión inexistente es NOT_FOUND', async () => {
    const project = await api.createProject('P');
    const asset = await api.uploadAsset(project.project_id, file('logo.png'));
    await expect(
      api.createJob(project.project_id, {
        schema_version: '0.1',
        asset_id: asset.asset_id,
        revision_id: 'rev_inexistente',
        input_kind: 'raster_image',
        settings: await settingsFor(),
      }),
    ).rejects.toMatchObject({ code: ErrorCode.NotFound });
  });

  it('avanza por las etapas reales hasta ready_for_sewout', async () => {
    const { job } = await start('logo.png');
    expect(job.status).toBe(JobStatus.Queued);
    const seen: string[] = [];
    for (let i = 0; i < 6; i++) {
      clock += i === 0 ? QUEUE_MS : STAGE_MS;
      seen.push((await api.getJob(job.job_id)).status);
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

  it('registra análisis y vectorización como omitidos, con motivo, para un SVG preparado', async () => {
    const { job } = await start('preparado.svg', 'image/svg+xml');
    const stages = Object.fromEntries(job.stages.map((s) => [s.stage, s]));
    expect(stages.analyzing).toMatchObject({ outcome: StageOutcome.Skipped });
    expect(stages.analyzing.reason).toBeTruthy();
    expect(job.input_kind).toBe('prepared_svg');
    clock += QUEUE_MS;
    expect((await api.getJob(job.job_id)).status).toBe(JobStatus.Digitizing);
    clock += STAGE_MS;
    expect((await api.getJob(job.job_id)).status).toBe(JobStatus.Validating);
  });

  it('falla en la etapa indicada con diagnóstico bloqueante', async () => {
    const { job } = await start('logo-fallo.png');
    clock += WELL_PAST_END;
    const failed = await api.getJob(job.job_id);
    expect(failed.status).toBe(JobStatus.Failed);
    expect(failed.failure?.stage).toBe(JobStatus.Digitizing);
    expect(failed.issues[0].severity).toBe('blocking_error');
    await expect(api.getArtifacts(job.job_id)).rejects.toMatchObject({ code: ErrorCode.ArtifactsUnavailable });
  });

  it('pide revisión con objetos concretos y sin cajas en píxeles', async () => {
    const { job } = await start('logo-revision.png');
    clock += WELL_PAST_END;
    const reviewed = await api.getJob(job.job_id);
    expect(reviewed.status).toBe(JobStatus.NeedsReview);
    expect(reviewed.review?.object_ids).toEqual(['object_mock_satin']);
    expect(reviewed.review?.issues[0].code).toBe('SATIN_RAILS_UNVERIFIED');
  });

  it('la cancelación (202) solo registra la solicitud y el servidor publica cancelled después', async () => {
    const { job } = await start('logo.png');
    clock += QUEUE_MS + STAGE_MS;
    const accepted = await api.cancelJob(job.job_id);
    expect(accepted.cancellation_requested).toBe(true);
    expect(accepted.status).not.toBe(JobStatus.Cancelled);
    clock += CANCEL_STOP_MS;
    const stopped = await api.getJob(job.job_id);
    expect(stopped.status).toBe(JobStatus.Cancelled);
    expect(stopped.stages.some((s) => s.outcome === StageOutcome.Cancelled)).toBe(true);
    await expect(api.getArtifacts(job.job_id)).rejects.toMatchObject({ code: ErrorCode.ArtifactsUnavailable });
  });

  it('cancelar un trabajo terminal responde sin reiniciarlo ni cambiarlo', async () => {
    const { job } = await start('logo.png');
    clock += WELL_PAST_END;
    const response = await api.cancelJob(job.job_id);
    expect(response.status).toBe(JobStatus.ReadyForSewout);
    expect(response.cancellation_requested).toBe(false);
  });

  it('GET artifacts emite URLs nuevas con TTL de 300 s y artefactos del job correcto', async () => {
    const a = await start('uno.png');
    const b = await start('dos.png');
    clock += WELL_PAST_END;
    const first = await api.getArtifacts(a.job.job_id);
    expect(first.artifacts.every((x) => x.job_id === a.job.job_id)).toBe(true);
    expect((await api.getArtifacts(b.job.job_id)).artifacts.every((x) => x.job_id === b.job.job_id)).toBe(true);
    const download = first.artifacts[0].download!;
    expect(Date.parse(download.expires_at) - Date.parse(download.issued_at)).toBe(TTL_MS);
    expect(first.artifacts[0].download_url).toBe(download.url);
    clock += 120_000;
    const second = await api.getArtifacts(a.job.job_id);
    expect(second.artifacts[0].download!.issued_at).not.toBe(download.issued_at);
    const snapshot = (await api.getJob(a.job.job_id)).artifact_manifest!;
    expect(snapshot.artifacts.every((x) => x.download === null)).toBe(true);
    expect(snapshot.reread_metrics.physical_trim_execution_verified).toBe(false);
    expect((await api.getJob(a.job.job_id)).sewout_status).toBe('untested');
  });

  it('los originales también llevan enlace temporal que se renueva con GET project', async () => {
    const { project, asset } = await start('logo.png');
    clock += 200_000;
    const detail = await api.getProject(project.project_id);
    const fresh = detail.assets.find((x: SourceAsset) => x.asset_id === asset.asset_id)!.original_download!;
    expect(Date.parse(fresh.expires_at) - Date.parse(fresh.issued_at)).toBe(TTL_MS);
    expect(fresh.issued_at).not.toBe(asset.original_download!.issued_at);
  });

  it('es idempotente con la misma clave y rechaza la misma clave con otro contenido', async () => {
    const project = await api.createProject('P');
    const asset = await api.uploadAsset(project.project_id, file('logo.png'));
    const settings = await settingsFor();
    const request = { schema_version: '0.1', base_revision_id: null, reason: 'x', settings } as const;
    const first = await api.createInitialRevision(project.project_id, request, 'misma');
    const second = await api.createInitialRevision(project.project_id, request, 'misma');
    expect(second.revision_id).toBe(first.revision_id);
    await expect(
      api.createInitialRevision(project.project_id, { ...request, reason: 'otro' }, 'misma'),
    ).rejects.toMatchObject({ code: ErrorCode.IdempotencyConflict });
    const job = await startGeneration(api, asset, settings, 'dup');
    expect((await startGeneration(api, asset, settings, 'dup')).job_id).toBe(job.job_id);
    expect((await api.getProject(project.project_id)).jobs).toHaveLength(1);
  });

  it('una variante es un trabajo nuevo enlazado al origen y con otro tamaño', async () => {
    const { project, job } = await start('logo.png');
    clock += WELL_PAST_END;
    const variant = await api.createDerivedRevision(project.project_id, {
      schema_version: '0.1',
      kind: 'size_variant',
      parent_job_id: job.job_id,
      target: { width_mm: 90, height_mm: 80, fit: 'contain' },
    });
    expect(variant.job_id).not.toBe(job.job_id);
    expect(variant.parent_job_id).toBe(job.job_id);
    expect(variant.settings_snapshot.target.width_mm).toBe(90);
    expect((await api.getJob(job.job_id)).settings_snapshot.target.width_mm).toBe(130);
  });

  it('la muestra física actualiza solo sewout_status; el estado digital no cambia', async () => {
    const { project, job } = await start('logo.png');
    clock += WELL_PAST_END;
    const before = await api.getJob(job.job_id);
    expect(before.status).toBe(JobStatus.ReadyForSewout);
    expect(before.sewout_status).toBe('untested');
    expect(before.sewout_record).toBeNull();

    const saved = await api.recordSewout(project.project_id, {
      schema_version: '0.1',
      revision_id: job.revision_id,
      status: 'approved',
      tested_at: '2026-11-01T11:00:00.000Z',
      fabric_profile: 'gabardina_inicial',
      stabilizer: 'Cut-away',
      thread: 'Poliéster 40',
      observations: 'Sin arrugas.',
      photo_asset_ids: [],
    });
    expect(saved).toMatchObject({ project_id: project.project_id, revision_id: job.revision_id, status: 'approved' });
    expect(saved.sewout_id).toBeTruthy();
    expect(saved.recorded_at).toBeTruthy();

    const after = await api.getJob(job.job_id);
    expect(after.status).toBe(JobStatus.ReadyForSewout);
    expect(after.sewout_status).toBe('approved');
    expect(after.sewout_record).toMatchObject({ sewout_id: saved.sewout_id, revision_id: job.revision_id, status: 'approved' });
  });

  it('rechaza una muestra que viola el contrato (resultado sin fecha, revisión ajena)', async () => {
    const { project, job } = await start('logo.png');
    const base = {
      schema_version: '0.1',
      revision_id: job.revision_id,
      fabric_profile: 'gabardina_inicial',
      stabilizer: 's',
      thread: 't',
      observations: 'o',
      photo_asset_ids: [],
    };
    await expect(
      api.recordSewout(project.project_id, { ...base, status: 'approved', tested_at: null }),
    ).rejects.toMatchObject({ code: ErrorCode.InvalidRequest });
    await expect(
      api.recordSewout(project.project_id, { ...base, status: 'untested', tested_at: '2026-11-01T11:00:00.000Z' }),
    ).rejects.toMatchObject({ code: ErrorCode.InvalidRequest });
    await expect(
      api.recordSewout(project.project_id, { ...base, revision_id: 'rev_ajena', status: 'untested', tested_at: null }),
    ).rejects.toMatchObject({ code: ErrorCode.NotFound });
  });

  it('un SVG "completo" devuelve el job del fixture: needs_review, 14 incidencias de satén y archivos', async () => {
    const { job } = await start('logo-completo.svg', 'image/svg+xml');
    expect(job.input_kind).toBe('prepared_svg');
    clock += WELL_PAST_END;
    const done = await api.getJob(job.job_id);
    expect(done.status).toBe(JobStatus.NeedsReview);
    expect(done.issues).toHaveLength(14);
    expect(done.review?.object_ids).toHaveLength(14);
    expect(done.validation_report?.digital_checks_passed).toBe(false);
    expect(done.artifact_manifest?.reread_metrics.stitch_bounds_mm).toMatchObject({ min_x_mm: -75, max_x_mm: 75, min_y_mm: -71.4, max_y_mm: 71.4 });
    expect(done.review?.object_ids).toContain('satin_A_descenso_0');
    expect(done.artifact_manifest?.reread_metrics).toMatchObject({ needle_stitches: 6789, thread_blocks: 3 });

    const manifest = await api.getArtifacts(job.job_id);
    const names = manifest.artifacts.map((a) => a.filename.replace(`${job.job_id}-`, '')).sort();
    expect(names).toEqual(['editable.svg', 'inkstitch.svg', 'output.jef', 'preview.png', 'raw-commands.json', 'validation.json']);
    expect(manifest.artifacts.every((a) => a.job_id === job.job_id && a.download)).toBe(true);
    expect(manifest.artifacts.find((a) => a.kind === 'jef')?.byte_size).toBe(14816);
  });

  it('el nombre "completo" solo aplica a un SVG preparado', async () => {
    const { job } = await start('logo-completo.png');
    clock += WELL_PAST_END;
    expect((await api.getJob(job.job_id)).status).toBe(JobStatus.ReadyForSewout);
  });

  it('el TTL de las descargas es configurable solo para pruebas (300 s por defecto)', async () => {
    const short = createMockApiClient({ now: () => clock, stageMs: STAGE_MS, downloadTtlMs: 1000 });
    const project = await short.createProject('P');
    const asset = await short.uploadAsset(project.project_id, file('a.png'));
    expect(asset.original_download && Date.parse(asset.original_download.expires_at) - Date.parse(asset.original_download.issued_at)).toBe(1000);
    const calls: string[] = [];
    const traced = createMockApiClient({ onCall: (m) => calls.push(m) });
    await traced.getProfiles();
    expect(calls).toEqual(['getProfiles']);
  });

  describe('análisis visual de una imagen (H2, SIMULADO, operaciones propuestas)', () => {
    const reachReview = async (name: string) => {
      const started = await start(name);
      clock += QUEUE_MS + 2 * STAGE_MS;
      return { ...started, review: await api.getJob(started.job.job_id) };
    };

    it('"analisis": se detiene en needs_review tras analizar, con una región incierta localizada', async () => {
      const { review } = await reachReview('logo-analisis.png');
      expect(review.status).toBe(JobStatus.NeedsReview);
      expect(review.input_kind).toBe('raster_image');
      expect(review.stages.map((s) => s.outcome)).toEqual(['completed', 'pending', 'pending', 'pending']);
      expect(review.review?.region_ids).toEqual(['region_3']);
      expect(review.review?.object_ids).toEqual([]);
      expect(review.issues[0]).toMatchObject({ code: 'ANALYSIS_REGION_INCOHERENT', severity: 'review_required', stage: 'analysis' });
      expect(review.artifact_manifest).toBeNull();
    });

    it('"ambiguo": tres regiones inciertas', async () => {
      const { review } = await reachReview('logo-ambiguo.png');
      expect(review.review?.region_ids).toEqual(['region_3', 'region_5', 'region_6']);
    });

    it('getAnalysis devuelve un AnalysisSpec con regiones, colores, texto e incertidumbres', async () => {
      const { job } = await reachReview('logo-ambiguo.png');
      const analysis = await api.getAnalysis(job.job_id);
      expect(analysis.regions).toHaveLength(6);
      expect(analysis.provider).toBe('openai');
      expect(analysis.regions.find((r) => r.region_id === 'region_1')).toMatchObject({ observed_text: 'ESTRELLA', suggested_colors: ['#1F3A93'] });
      expect(analysis.regions.every((r) => r.representation === 'estimated_bbox')).toBe(true);
      expect(analysis.regions.filter((r) => r.uncertainties.length > 0).map((r) => r.region_id)).toEqual(['region_3', 'region_5', 'region_6']);
    });

    it('getAnalysis no existe para un trabajo sin análisis pendiente', async () => {
      const { job } = await start('logo.png');
      await expect(api.getAnalysis(job.job_id)).rejects.toMatchObject({ code: ErrorCode.NotFound });
    });

    it('aprobar crea un job nuevo que omite el análisis con su motivo y llega a ready', async () => {
      const { job } = await reachReview('logo-analisis.png');
      const next = await api.decideAnalysis(job.job_id, { action: 'approve', flagged_region_ids: ['region_3'] });
      expect(next.job_id).not.toBe(job.job_id);
      expect(next.parent_job_id).toBe(job.job_id);
      const analyzing = next.stages.find((s) => s.stage === 'analyzing');
      expect(analyzing).toMatchObject({ outcome: StageOutcome.Skipped });
      expect(analyzing?.reason).toContain(job.job_id);
      clock += WELL_PAST_END;
      expect((await api.getJob(next.job_id)).status).toBe(JobStatus.ReadyForSewout);
      expect((await api.getJob(job.job_id)).status).toBe(JobStatus.NeedsReview);
    });

    it('cambiar de proveedor crea otro job con ese proveedor; el mismo o uno no disponible se rechaza', async () => {
      const { job } = await reachReview('logo-analisis.png');
      const next = await api.decideAnalysis(job.job_id, { action: 'change_provider', ai_provider: 'ollama' });
      expect(next.settings_snapshot.ai_provider).toBe('ollama');
      expect(next.parent_job_id).toBe(job.job_id);
      await expect(api.decideAnalysis(job.job_id, { action: 'change_provider', ai_provider: 'openai' })).rejects.toMatchObject({ code: ErrorCode.InvalidRequest });
      clock += QUEUE_MS + 2 * STAGE_MS;
      expect((await api.getAnalysis(next.job_id)).provider).toBe('ollama');
    });

    it('solo se decide un análisis que está en needs_review', async () => {
      const { job } = await start('logo-analisis.png');
      await expect(api.decideAnalysis(job.job_id, { action: 'approve', flagged_region_ids: [] })).rejects.toMatchObject({ code: ErrorCode.RevisionConflict });
    });

    it('escala las regiones al tamaño real del original', async () => {
      const { job, asset } = await reachReview('logo-analisis.png');
      const analysis = await api.getAnalysis(job.job_id);
      const region = analysis.regions.find((r) => r.region_id === 'region_1')!;
      // 800 × 600 es el tamaño de referencia y también el de reserva del mock en jsdom.
      expect(asset.original_width_px).toBe(800);
      expect(region.bounds_px).toMatchObject({ x_px: 120, y_px: 80, width_px: 560, height_px: 140 });
    });
  });

  it('rechaza formatos no admitidos y proveedores no disponibles', async () => {
    const project = await api.createProject('P');
    await expect(api.uploadAsset(project.project_id, file('x.gif', 'image/gif'))).rejects.toMatchObject({
      code: ErrorCode.UnsupportedMediaType,
    });
    const local = createMockApiClient({ ollamaAvailable: false });
    const p = await local.createProject('P');
    const asset = await local.uploadAsset(p.project_id, file('logo.png'));
    const catalog = await local.getProfiles();
    const settings = toJobSettings(
      {
        width_mm: '130', height_mm: '120', machine_profile: 'janome_mc550e', hoop_profile: 'sq20b',
        fabric_profile: 'gabardina_inicial', thread_profile: 'embroidery_thread_initial',
        color_limit: '3', ai_provider: AiProvider.Ollama,
      },
      catalog,
    );
    await expect(startGeneration(local, asset, settings, 'k')).rejects.toMatchObject({ code: ErrorCode.InvalidRequest });
  });
});
