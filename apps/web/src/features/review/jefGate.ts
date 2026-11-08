import type { ValidationCheck } from '../../contracts/artifacts';
import type { JobResponse } from '../../contracts/job';
import { SewoutStatus } from '../../contracts/sewout';
import type { Issue } from '../../contracts/validation';

/** Código que emite el motor (ronda 5 de Codex) cuando el trazo es demasiado fino para la técnica elegida. */
export const LEGIBILITY_RISK = 'LEGIBILITY_RISK';

export interface JefGate {
  /** true si el informe existe, todos los controles digitales pasaron y `digital_checks_passed` es true. */
  digitalPassed: boolean;
  hasReport: boolean;
  /** Controles que no pasaron o no se ejecutaron, con su estado, para listarlos antes de descargar. */
  pending: ValidationCheck[];
  notRun: ValidationCheck[];
  physicalApproved: boolean;
  /** La descarga pide confirmación explícita mientras falte algo digital o físico. Nunca se rotula «listo para coser». */
  needsConfirmation: boolean;
  legibilityIssues: Issue[];
}

export function jefGate(job: JobResponse): JefGate {
  const report = job.validation_report;
  const checks = report?.checks ?? [];
  const pending = checks.filter((check) => check.outcome !== 'passed');
  const digitalPassed = !!report && report.digital_checks_passed && pending.length === 0;
  const physicalApproved = job.sewout_status === SewoutStatus.Approved;
  return {
    digitalPassed,
    hasReport: !!report,
    pending,
    notRun: checks.filter((check) => check.outcome === 'not_run'),
    physicalApproved,
    needsConfirmation: !digitalPassed || !physicalApproved,
    legibilityIssues: job.issues.filter((issue) => issue.code === LEGIBILITY_RISK),
  };
}

/**
 * Técnica por objeto, si el motor la informa en la evidencia de la incidencia (`technique_by_object`, o `objects[id].technique`).
 * Esta versión del motor todavía no la emite: devuelve [] y la pantalla lo dice en vez de inventarla.
 */
export function techniquesByObject(issue: Issue): Array<{ objectId: string; technique: string }> {
  const evidence = issue.evidence as Record<string, unknown>;
  const direct = evidence.technique_by_object;
  if (direct && typeof direct === 'object') {
    return Object.entries(direct as Record<string, unknown>).map(([objectId, technique]) => ({ objectId, technique: String(technique) }));
  }
  const objects = evidence.objects;
  if (objects && typeof objects === 'object') {
    return Object.entries(objects as Record<string, { technique?: unknown }>)
      .filter(([, value]) => value && typeof value.technique === 'string')
      .map(([objectId, value]) => ({ objectId, technique: String(value.technique) }));
  }
  return [];
}
