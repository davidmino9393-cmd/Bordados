import { describe, expect, it } from 'vitest';
import type { ValidationCheck } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';
import type { Issue } from '../../contracts/validation';
import { jefGate, LEGIBILITY_RISK, techniquesByObject } from './jefGate';

const CHECKS: ValidationCheck[] = [
  { kind: 'file', outcome: 'passed', method: 'relectura del JEF' },
  { kind: 'dimensions', outcome: 'passed', method: 'bounds' },
  { kind: 'hoop', outcome: 'passed', method: 'bounds' },
  { kind: 'geometry', outcome: 'not_run', method: 'not implemented in H0-04' },
  { kind: 'satin', outcome: 'not_run', method: 'not implemented in H0-04' },
  { kind: 'routing', outcome: 'not_run', method: 'not implemented in H0-04' },
  { kind: 'visual', outcome: 'not_run', method: 'not implemented in H0-04' },
];

function job(over: Partial<JobResponse>): JobResponse {
  return { sewout_status: 'untested', issues: [], validation_report: null, ...over } as unknown as JobResponse;
}

function report(checks: ValidationCheck[], passed: boolean) {
  return { checks, digital_checks_passed: passed } as unknown as JobResponse['validation_report'];
}

function issue(code: string, evidence: Record<string, unknown> = {}): Issue {
  return { code, severity: 'review_required', stage: 'digitizing', object_ids: ['obj_1'], region_ids: [], description: 'd', evidence, suggested_correction: '' };
}

describe('gate de la descarga del JEF', () => {
  it('con digital_checks_passed falso y checks sin ejecutar pide confirmación y lista los pendientes', () => {
    const gate = jefGate(job({ validation_report: report(CHECKS, false) }));
    expect(gate.digitalPassed).toBe(false);
    expect(gate.hasReport).toBe(true);
    expect(gate.needsConfirmation).toBe(true);
    expect(gate.notRun.map((c) => c.kind)).toEqual(['geometry', 'satin', 'routing', 'visual']);
    expect(gate.pending).toHaveLength(4);
  });

  it('un informe que dice pasó pero trae un check sin ejecutar no se toma como pasado', () => {
    const gate = jefGate(job({ validation_report: report(CHECKS, true), sewout_status: 'approved' }));
    expect(gate.digitalPassed).toBe(false);
    expect(gate.needsConfirmation).toBe(true);
  });

  it('sin informe no se afirma nada y se pide confirmación', () => {
    const gate = jefGate(job({}));
    expect(gate).toMatchObject({ hasReport: false, digitalPassed: false, needsConfirmation: true });
  });

  it('con todo pasado pero sin muestra física aprobada sigue pidiendo confirmación', () => {
    const passed = CHECKS.map((c) => ({ ...c, outcome: 'passed' as const }));
    expect(jefGate(job({ validation_report: report(passed, true), sewout_status: 'untested' })).needsConfirmation).toBe(true);
    expect(jefGate(job({ validation_report: report(passed, true), sewout_status: 'approved' })).needsConfirmation).toBe(false);
  });

  it('separa las incidencias LEGIBILITY_RISK', () => {
    const gate = jefGate(job({ issues: [issue('SATIN_RUNG_WARNING'), issue(LEGIBILITY_RISK)] }));
    expect(gate.legibilityIssues.map((i) => i.code)).toEqual([LEGIBILITY_RISK]);
  });

  it('la técnica por objeto sale de la evidencia si el motor la informa y es vacía si no', () => {
    expect(techniquesByObject(issue(LEGIBILITY_RISK, { technique_by_object: { obj_1: 'running' } }))).toEqual([{ objectId: 'obj_1', technique: 'running' }]);
    expect(techniquesByObject(issue(LEGIBILITY_RISK, { objects: { obj_2: { technique: 'satin' }, obj_3: {} } }))).toEqual([{ objectId: 'obj_2', technique: 'satin' }]);
    expect(techniquesByObject(issue(LEGIBILITY_RISK))).toEqual([]);
  });
});
