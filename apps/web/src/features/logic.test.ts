import { describe, expect, it } from 'vitest';
import { StageState, type StageProgress } from '../contracts/job';
import { ArtifactKind, type ArtifactManifest } from '../contracts/artifacts';
import { AiProvider } from '../contracts/settings';
import { estimateContain } from '../shared/utils/fit';
import { guardArtifacts } from './artifacts/artifactGuard';
import { summarizeProgress } from './job-progress/progress';
import { toJobSettings, validateSettings, type SettingsFormValues } from './settings/validateSettings';

const machine = { id: 'm', label: 'M', hoops: [], max_colors: 12 };
const values: SettingsFormValues = {
  width_mm: '130',
  height_mm: '120',
  machine_profile: 'm',
  hoop_profile: 'h',
  fabric_profile: 'f',
  color_limit: '3',
  ai_provider: AiProvider.OpenAI,
};

describe('summarizeProgress', () => {
  it('no cuenta las etapas omitidas', () => {
    const stages: StageProgress[] = [
      { stage: 'analyzing', state: StageState.Skipped },
      { stage: 'vectorizing', state: StageState.Skipped },
      { stage: 'digitizing', state: StageState.Done },
      { stage: 'validating', state: StageState.Running },
    ];
    expect(summarizeProgress(stages)).toEqual({ done: 1, total: 2 });
  });
});

describe('validateSettings', () => {
  it('acepta valores válidos con coma decimal', () => {
    expect(validateSettings({ ...values, width_mm: '130,5' }, machine)).toEqual({});
    expect(toJobSettings({ ...values, width_mm: '130,5' }).target).toEqual({
      width_mm: 130.5,
      height_mm: 120,
      fit: 'contain',
    });
  });
  it('rechaza tamaños y colores inválidos', () => {
    const errors = validateSettings({ ...values, width_mm: '0', height_mm: 'abc', color_limit: '13' }, machine);
    expect(errors).toEqual({ width_mm: 'positive', height_mm: 'positive', color_limit: 'range' });
  });
});

describe('estimateContain', () => {
  it('conserva proporciones dentro del área', () => {
    expect(estimateContain(200, 100, { width_mm: 100, height_mm: 100 })).toEqual({
      width_mm: 100,
      height_mm: 50,
    });
    expect(estimateContain(0, 100, { width_mm: 100, height_mm: 100 })).toBeNull();
  });
});

describe('guardArtifacts', () => {
  const artifact = (job_id: string) => ({
    kind: ArtifactKind.Jef,
    job_id,
    filename: 'a.jef',
    sha256: 'x',
    size_bytes: 1,
    content_type: 'a',
    download_url: 'u',
  });
  it('descarta archivos de otro trabajo', () => {
    const manifest: ArtifactManifest = { job_id: 'A', artifacts: [artifact('A'), artifact('B')], metrics: null };
    const guarded = guardArtifacts(manifest, 'A');
    expect(guarded.artifacts).toHaveLength(1);
    expect(guarded.hadMismatch).toBe(true);
  });
  it('rechaza un manifiesto completo de otro trabajo', () => {
    const manifest: ArtifactManifest = { job_id: 'B', artifacts: [artifact('B')], metrics: null };
    expect(guardArtifacts(manifest, 'A')).toMatchObject({ artifacts: [], hadMismatch: true });
  });
});
