// Comprueba que los fixtures cumplen las reglas del contrato que la web asume.
// No reemplaza la validación Pydantic del backend: replica a mano sus invariantes principales.
import { describe, expect, it } from 'vitest';
import issueCatalog from '../../../../packages/contracts/issue-catalog.json';
import cancellation from '../../mocks/cancellation.json';
import completed from '../../mocks/job-completed-real.json';
import failure from '../../mocks/failure.json';
import needsReview from '../../mocks/needs-review.json';
import validResult from '../../mocks/valid-result.json';
import type { JobResponse } from '../contracts/job';

const catalog = issueCatalog.issues as Record<string, { severity: string; stage: string }>;
const fixtures = { cancellation, completed, failure, needsReview, validResult } as unknown as Record<
  string,
  { simulated: boolean; payload: JobResponse }
>;

describe.each(Object.entries(fixtures))('fixture %s', (_name, fixture) => {
  const job = fixture.payload;

  it('está marcado como simulado y es schema 0.1', () => {
    expect(fixture.simulated).toBe(true);
    expect(job.schema_version).toBe('0.1');
  });

  it('cada incidencia coincide con severidad y etapa del catálogo', () => {
    for (const issue of job.issues) {
      expect(catalog[issue.code], issue.code).toBeDefined();
      expect({ severity: issue.severity, stage: issue.stage }).toEqual({
        severity: catalog[issue.code].severity,
        stage: catalog[issue.code].stage,
      });
    }
  });

  it('las vistas derivadas (diagnostics, review, failure) concuerdan con issues', () => {
    expect(job.diagnostics ?? []).toEqual(job.issues);
    if (job.status === 'needs_review') {
      const reviews = job.issues.filter((i) => i.severity === 'review_required');
      expect(reviews.some((i) => i.object_ids.length + i.region_ids.length > 0)).toBe(true);
      expect(job.review?.object_ids).toEqual([...new Set(reviews.flatMap((i) => i.object_ids))].sort());
    }
    if (job.status === 'failed') {
      expect(job.issues.some((i) => i.severity === 'blocking_error')).toBe(true);
      expect(job.failure?.code).toBe(job.issues.find((i) => i.severity === 'blocking_error')?.code);
    }
  });

  it('manifiesto y reporte pertenecen al job y a la revisión, con sus archivos coherentes', () => {
    for (const doc of [job.artifact_manifest, job.validation_report]) {
      if (!doc) continue;
      expect(doc.job_id).toBe(job.job_id);
      expect(doc.revision_id).toBe(job.revision_id);
    }
    const manifest = job.artifact_manifest;
    if (!manifest) return;
    const ids = manifest.artifacts.map((a) => a.artifact_id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(manifest.artifacts.every((a) => a.job_id === manifest.job_id)).toBe(true);
    const raw = manifest.artifacts.find((a) => a.artifact_id === manifest.reread_metrics.raw_commands_artifact_id);
    expect(raw?.kind).toBe('raw_commands_json');
    for (const a of manifest.artifacts) {
      expect(a.sha256).toMatch(/^[a-f0-9]{64}$/);
      expect(a.byte_size).toBeGreaterThan(0);
    }
  });
});

describe('fixture job-completed-real (SIMULADO)', () => {
  const job = completed.payload as unknown as JobResponse;
  const manifest = job.artifact_manifest!;

  it('es un SVG preparado en needs_review con controles digitales sin aprobar', () => {
    expect(job.input_kind).toBe('prepared_svg');
    expect(job.status).toBe('needs_review');
    expect(job.validation_report?.digital_checks_passed).toBe(false);
    expect(job.stages.filter((s) => s.outcome === 'skipped').map((s) => s.stage)).toEqual(['analyzing', 'vectorizing']);
    expect(manifest.provenance.simulated).toBe(true);
  });

  it('lleva 14 avisos de satén idénticos, cada uno con los mismos 14 object_ids reales (sin asignar)', () => {
    expect(job.issues).toHaveLength(14);
    expect(job.issues.every((i) => i.stage === 'satin' && i.severity === 'review_required')).toBe(true);
    expect(new Set(job.issues.map((i) => i.description)).size).toBe(1);
    const listed = new Set(job.issues.map((i) => JSON.stringify(i.object_ids)));
    expect(listed.size).toBe(1);
    const ids = job.issues[0].object_ids;
    expect(ids).toHaveLength(14);
    expect(ids).toEqual(expect.arrayContaining(['satin_A_descenso_0', 'satin_SOCKS_S_1_0', 'satin_n_0']));
    expect(ids.some((id) => id.startsWith('object_mock'))).toBe(false);
    expect(job.review?.object_ids).toEqual([...ids].sort());
    expect(job.issues[0].evidence).toMatchObject({ source_object_mapping_verified: false });
  });

  it('declara las medidas y conteos pedidos', () => {
    const m = manifest.reread_metrics;
    // Origen centrado, como en el JEF real: el ancho y el alto salen de la diferencia, no del máximo.
    expect(m.stitch_bounds_mm).toEqual({ min_x_mm: -75, min_y_mm: -71.4, max_x_mm: 75, max_y_mm: 71.4 });
    expect(m.needle_stitches).toBe(6789);
    expect(m.thread_blocks).toBe(3);
    expect(m.physical_trim_execution_verified).toBe(false);
  });

  it('incluye los 6 artefactos del backend real, con hashes ficticios evidentes y sin enlaces', () => {
    const byName = Object.fromEntries(manifest.artifacts.map((a) => [a.filename, a]));
    expect(Object.keys(byName).sort()).toEqual(
      ['editable.svg', 'inkstitch.svg', 'output.jef', 'preview.png', 'raw-commands.json', 'validation.json'],
    );
    expect(byName['output.jef']).toMatchObject({ kind: 'jef', byte_size: 14816, derived_from: 'export' });
    expect(byName['preview.png']).toMatchObject({ kind: 'preview_png', derived_from: 'jef_reread' });
    expect(byName['editable.svg']).toMatchObject({ kind: 'editable_svg', derived_from: 'document' });
    expect(byName['inkstitch.svg']).toMatchObject({ kind: 'inkstitch_svg' });
    expect(byName['validation.json']).toMatchObject({ kind: 'validation_json', derived_from: 'validation' });
    expect(byName['raw-commands.json']).toMatchObject({ kind: 'raw_commands_json', derived_from: 'jef_reread' });
    expect(manifest.artifacts.every((a) => a.download === null && a.download_url === null)).toBe(true);
    // Hashes claramente ficticios: 000…001, 000…002, … (válidos para el contrato, imposibles de confundir con reales).
    expect(manifest.artifacts.every((a) => /^0{60}[0-9a-f]{4}$/.test(a.sha256))).toBe(true);
    expect(manifest.provenance.simulated).toBe(true);
  });

  it('refleja los controles del backend real: archivo, medidas y bastidor pasan; geometría, satén y recorrido no se ejecutaron', () => {
    const outcomes = Object.fromEntries((job.validation_report?.checks ?? []).map((c) => [c.kind, c.outcome]));
    expect(outcomes).toMatchObject({ file: 'passed', dimensions: 'passed', hoop: 'passed', geometry: 'not_run', satin: 'not_run', routing: 'not_run' });
  });
});
