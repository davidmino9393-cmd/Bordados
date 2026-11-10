import { publicIssues } from '../artifacts/publicIssues';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { JobResponse } from '../../contracts/job';
import { Technique, type Correction, type SourceAsset } from '../../contracts/project';
import { CONTRACT_SCHEMA_VERSION } from '../../contracts/version';
import { es, issueTitle, severityLabel, techniqueLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { useIdempotencyKey } from '../../shared/hooks/useIdempotencyKey';

const KEEP = 'keep';
const EXCLUDE = 'exclude';
type Choice = typeof KEEP | typeof EXCLUDE | Technique;
type TargetKind = 'object' | 'region';

interface ReviewPanelProps {
  job: JobResponse;
  asset: SourceAsset | undefined;
  /** Falso cuando no hay puntadas que corregir (solo geometría): se muestran las incidencias sin el formulario. */
  correctable?: boolean;
}

function toCorrection(kind: TargetKind, id: string, choice: Choice): Correction | null {
  if (choice === KEEP) return null;
  if (choice === EXCLUDE) {
    return kind === 'object' ? { action: 'exclude_region', object_id: id } : { action: 'exclude_region', region_id: id };
  }
  // set_technique solo aplica a objetos (el contrato exige object_id).
  return kind === 'object' ? { action: 'set_technique', object_id: id, technique: choice } : null;
}

/** Revisión localizada: causa, objetos/zonas concretos y correcciones que crean un trabajo nuevo. */
export function ReviewPanel({ job, asset, correctable = true }: ReviewPanelProps) {
  const api = useApi();
  const navigate = useNavigate();
  const keyFor = useIdempotencyKey();
  const review = job.review;
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  if (!review) return null;

  const targets: Array<{ kind: TargetKind; id: string }> = [
    ...review.object_ids.map((id) => ({ kind: 'object' as const, id })),
    ...review.region_ids.map((id) => ({ kind: 'region' as const, id })),
  ];
  const corrections = targets
    .map((t) => toCorrection(t.kind, t.id, choices[`${t.kind}:${t.id}`] ?? KEEP))
    .filter((c): c is Correction => c !== null);

  const apply = async () => {
    if (corrections.length === 0) return setError(es.review.nothingChosen);
    setBusy(true);
    setError(undefined);
    try {
      const request = {
        schema_version: CONTRACT_SCHEMA_VERSION,
        kind: 'correction' as const,
        parent_job_id: job.job_id,
        corrections,
      };
      const next = await api.createDerivedRevision(job.project_id, request, keyFor(request));
      navigate(`/trabajos/${next.job_id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  const originalUrl = asset?.original_download?.url;
  return (
    <Card>
      <Card.Header>{es.review.title}</Card.Header>
      <Card.Body>
        {publicIssues(job.issues).map((issue) => (
          <p key={issue.code} className="issue">
            <strong>{severityLabel[issue.severity]}: {issueTitle(issue.code, 'Revisá el resultado')}</strong>
          </p>
        ))}
        {originalUrl && (
          <figure className="region-view">
            <img src={originalUrl} alt={es.review.originalRef} />
            <figcaption className="field__hint">{es.review.originalRef}</figcaption>
          </figure>
        )}
        {correctable && targets.map(({ kind, id }, index) => (
          <Field key={`${kind}:${id}`} label={`${es.review.action} (${kind === 'object' ? 'elemento' : 'zona'} ${index + 1})`}>
            <select
              value={choices[`${kind}:${id}`] ?? KEEP}
              onChange={(e) => setChoices({ ...choices, [`${kind}:${id}`]: e.target.value as Choice })}
            >
              <option value={KEEP}>{es.review.keep}</option>
              {kind === 'object' &&
                Object.values(Technique).map((t) => (
                  <option key={t} value={t}>{es.review.setTechnique}: {techniqueLabel[t]}</option>
                ))}
              <option value={EXCLUDE}>{es.review.exclude}</option>
            </select>
          </Field>
        ))}
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
        {correctable && (
          <div className="row">
            <button type="button" onClick={apply} disabled={busy}>{es.review.apply}</button>
          </div>
        )}
      </Card.Body>
    </Card>
  );
}
