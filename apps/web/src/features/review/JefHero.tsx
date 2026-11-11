import { useState } from 'react';
import type { JobResponse } from '../../contracts/job';
import { ArtifactKind } from '../../contracts/artifacts';
import { SewoutStatus } from '../../contracts/sewout';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { formatBytes } from '../../shared/utils/format';
import { guardArtifacts } from '../artifacts/artifactGuard';
import { useArtifactDownload } from '../artifacts/useArtifactDownload';
import { useArtifacts } from '../artifacts/useArtifacts';
import { jefGate, techniquesByObject } from './jefGate';

interface JefHeroProps {
  job: JobResponse;
}

function physicalLine(status: JobResponse['sewout_status']): string {
  if (status === SewoutStatus.Approved) return es.review.gatePhysicalApproved;
  if (status === SewoutStatus.NeedsAdjustment) return es.review.gatePhysicalNeedsAdjustment;
  return es.review.gatePhysicalUntested;
}

/**
 * El JEF, con el estado real de los controles a la vista. Nunca se rotula «listo para coser» con controles digitales sin
 * pasar o sin muestra física aprobada; la descarga existe, pero pide una confirmación explícita con la lista de pendientes.
 */
export function JefHero({ job }: JefHeroProps) {
  const { manifest, refresh } = useArtifacts(job.job_id);
  const { renewing, onDownload } = useArtifactDownload(refresh);
  const [confirmed, setConfirmed] = useState(false);
  const gate = jefGate(job);
  const jef = manifest ? guardArtifacts(manifest, job.job_id).artifacts.find((a) => a.kind === ArtifactKind.Jef) : undefined;
  if (!jef) return null;
  const text = es.review;
  const digitalLine = !gate.hasReport ? text.gateDigitalNoReport : gate.digitalPassed ? text.gateDigitalPassed : text.gateDigitalFailed;
  const pendingList = gate.pending.map((c) => `${text.checkKind[c.kind] ?? c.kind}: ${text.checkOutcome[c.outcome] ?? c.outcome}`).join('; ');
  const confirmText = !gate.hasReport
    ? text.confirmDownloadNoReport
    : gate.pending.length > 0
      ? text.confirmDownload(pendingList)
      : text.confirmDownloadUnapproved;
  const unlocked = !gate.needsConfirmation || confirmed;
  return (
    <Card>
      <Card.Header>{text.jefHeroTitle}</Card.Header>
      <Card.Body>
        <p>{text.jefHeroText}</p>
        <Notice tone={gate.digitalPassed && gate.physicalApproved ? NoticeTone.Info : NoticeTone.Warning}>
          <p><strong>{digitalLine}</strong></p>
          <p><strong>{physicalLine(job.sewout_status)}</strong></p>
        </Notice>
        {job.validation_report && (
          <div>
            <strong>{text.gateChecksTitle}</strong>
            <ul aria-label={text.gateChecksTitle}>
              {job.validation_report.checks.map((check) => (
                <li key={check.kind}>
                  {text.checkKind[check.kind] ?? check.kind}:{' '}
                  {check.outcome === 'passed' ? text.checkOutcome.passed : <strong>{text.checkOutcome[check.outcome] ?? check.outcome}</strong>}
                  <span className="field__hint"> · {check.method}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {gate.legibilityIssues.map((issue, index) => {
          const techniques = techniquesByObject(issue);
          return (
            <Notice key={`${issue.code}-${index}`} tone={NoticeTone.Warning} title={text.legibilityTitle}>
              <p>{issue.description}</p>
              <p className="field__hint">{[...issue.object_ids, ...issue.region_ids].join(', ')}</p>
              <p><strong>{text.legibilityTechniques}:</strong>{' '}
                {techniques.length > 0 ? techniques.map((t) => `${t.objectId} → ${t.technique}`).join('; ') : text.legibilityNoTechnique}
              </p>
            </Notice>
          );
        })}
        {gate.needsConfirmation && (
          <label className="radio">
            <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> {confirmText}
          </label>
        )}
        <div className="row">
          {unlocked ? (
            <a className="button" href={jef.download?.url} download={jef.filename} onClick={(e) => void onDownload(e, jef)}>
              {text.jefHeroDownload}
            </a>
          ) : (
            <button type="button" disabled>{text.jefHeroDownload}</button>
          )}
          <span className="field__hint">{jef.filename} · {formatBytes(jef.byte_size)}</span>
        </div>
        {!unlocked && <p className="field__hint">{text.downloadLocked}</p>}
        {renewing && <p role="status">{es.result.renewing}</p>}
      </Card.Body>
    </Card>
  );
}
