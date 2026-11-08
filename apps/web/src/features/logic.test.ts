import { describe, expect, it } from 'vitest';
import catalogFixture from '../../mocks/profiles.json';
import { ArtifactKind, type Artifact, type ArtifactManifest } from '../contracts/artifacts';
import { StageOutcome, type JobResponse, type StageRecord } from '../contracts/job';
import { AiProvider, type ProfileCatalog } from '../contracts/settings';
import { earliestExpiry, isExpired } from '../shared/utils/expiry';
import { estimateContain } from '../shared/utils/fit';
import { guardArtifacts } from './artifacts/artifactGuard';
import { summarizeProgress } from './job-progress/progress';
import { isGeometryOnly } from './review/geometryOnly';
import { toJobSettings, validateSettings, type SettingsFormValues } from './settings/validateSettings';

const catalog = catalogFixture.payload as ProfileCatalog;
const machine = catalog.machines[0];
const values: SettingsFormValues = {
  machine_profile: 'janome_mc550e',
  hoop_profile: 'sq20b',
  fabric_profile: 'gabardina_inicial',
  color_limit: '3',
  ai_provider: AiProvider.OpenAI,
};

const stage = (name: StageRecord['stage'], outcome: StageRecord['outcome']): StageRecord => ({
  stage: name,
  outcome,
  reason: outcome === StageOutcome.Skipped ? 'motivo' : null,
  measured_duration_ms: null,
});

describe('summarizeProgress', () => {
  it('no cuenta las etapas omitidas', () => {
    const stages = [
      stage('analyzing', StageOutcome.Skipped),
      stage('vectorizing', StageOutcome.Skipped),
      stage('digitizing', StageOutcome.Completed),
      stage('validating', StageOutcome.Running),
    ];
    expect(summarizeProgress(stages)).toEqual({ done: 1, total: 2 });
  });
});

describe('validateSettings / toJobSettings', () => {
  it('acepta valores válidos', () => {
    expect(validateSettings(values, machine)).toEqual({});
  });
  it('rechaza cantidades de colores inválidas', () => {
    expect(validateSettings({ ...values, color_limit: '17' }, machine)).toEqual({ color_limit: 'range' });
    expect(validateSettings({ ...values, color_limit: '0' }, machine)).toEqual({ color_limit: 'range' });
  });
  it('arma las instantáneas de perfil desde el catálogo, sin valores fijos en la web', () => {
    const settings = toJobSettings(values, catalog);
    expect(settings.target).toEqual({ width_mm: 200, height_mm: 200, fit: 'contain' });
    expect(settings.hoop).toEqual({
      profile_id: 'sq20b',
      profile_version: '0.1',
      width_mm: 200,
      height_mm: 200,
      jef_hoop_code: 4,
    });
    expect(settings.hoop_profile).toBe(settings.hoop.profile_id);
    expect(settings.machine_profile_version).toBe('0.1');
    expect(settings.fabric_profile_version).toBe('0.1');
  });
});

describe('estimateContain', () => {
  it('conserva proporciones dentro del área', () => {
    expect(estimateContain(200, 100, { width_mm: 100, height_mm: 100 })).toEqual({ width_mm: 100, height_mm: 50 });
    expect(estimateContain(0, 100, { width_mm: 100, height_mm: 100 })).toBeNull();
  });
});

describe('guardArtifacts', () => {
  const artifact = (job_id: string): Artifact => ({
    artifact_id: `a_${job_id}`,
    kind: ArtifactKind.Jef,
    job_id,
    filename: 'a.jef',
    media_type: 'application/octet-stream',
    sha256: 'x',
    byte_size: 1,
    derived_from: 'export',
    download: null,
    download_url: null,
    expires_at: null,
  });
  const manifest = (job_id: string, artifacts: Artifact[]): ArtifactManifest =>
    ({ job_id, artifacts, reread_metrics: null }) as unknown as ArtifactManifest;

  it('descarta archivos de otro trabajo', () => {
    const guarded = guardArtifacts(manifest('A', [artifact('A'), artifact('B')]), 'A');
    expect(guarded.artifacts).toHaveLength(1);
    expect(guarded.hadMismatch).toBe(true);
  });
  it('rechaza un manifiesto completo de otro trabajo', () => {
    expect(guardArtifacts(manifest('B', [artifact('B')]), 'A')).toMatchObject({ artifacts: [], hadMismatch: true });
  });
});

describe('vencimiento de enlaces', () => {
  const now = Date.parse('2026-11-01T12:00:00Z');
  it('detecta enlaces vencidos o por vencer', () => {
    expect(isExpired('2026-11-01T11:59:59Z', now)).toBe(true);
    expect(isExpired('2026-11-01T12:00:05Z', now, 10_000)).toBe(true);
    expect(isExpired('2026-11-01T12:04:00Z', now, 10_000)).toBe(false);
    expect(isExpired(null, now)).toBe(true);
  });
  it('elige el vencimiento más próximo', () => {
    expect(earliestExpiry(['2026-11-01T12:05:00Z', null, '2026-11-01T12:01:00Z'])).toBe('2026-11-01T12:01:00Z');
    expect(earliestExpiry([null])).toBeUndefined();
  });
});

describe('isGeometryOnly', () => {
  const job = (kinds: string[] | null) =>
    ({ artifact_manifest: kinds && { artifacts: kinds.map((kind) => ({ kind })) } }) as unknown as JobResponse;

  it('es verdadero solo si hay manifiesto y ninguno de sus archivos es un JEF', () => {
    expect(isGeometryOnly(job(['editable_svg']))).toBe(true);
    expect(isGeometryOnly(job(['editable_svg', 'jef', 'preview_png']))).toBe(false);
    expect(isGeometryOnly(job(null))).toBe(false);
  });
});
