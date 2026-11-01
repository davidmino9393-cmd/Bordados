import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { Job } from '../../contracts/job';
import { Technique, type Correction, type SourceAsset } from '../../contracts/project';
import { es, severityLabel, techniqueLabel } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { RegionOverlay } from './RegionOverlay';

const KEEP = 'keep';
const EXCLUDE = 'exclude';
type Choice = typeof KEEP | typeof EXCLUDE | Technique;

interface ReviewPanelProps {
  job: Job;
  asset: SourceAsset | undefined;
}

function toCorrection(objectId: string, choice: Choice): Correction | null {
  if (choice === KEEP) return null;
  if (choice === EXCLUDE) return { action: 'exclude_region', object_id: objectId };
  return { action: 'set_technique', object_id: objectId, technique: choice };
}

/** Revisión localizada: causa, objetos concretos y correcciones que crean una revisión nueva. */
export function ReviewPanel({ job, asset }: ReviewPanelProps) {
  const api = useApi();
  const navigate = useNavigate();
  const review = job.review;
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  if (!review) return null;

  const objectIds = [...new Set(review.issues.flatMap((i) => i.object_ids))];
  const corrections = objectIds
    .map((id) => toCorrection(id, choices[id] ?? KEEP))
    .filter((c): c is Correction => c !== null);

  const apply = async () => {
    if (corrections.length === 0) return setError(es.review.nothingChosen);
    setBusy(true);
    setError(undefined);
    try {
      const next = await api.createRevision(job.project_id, {
        kind: 'correction',
        parent_job_id: job.id,
        corrections,
      });
      navigate(`/trabajos/${next.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Card>
      <Card.Header>{es.review.title}</Card.Header>
      <Card.Body>
        <Notice tone={NoticeTone.Warning} title={review.cause} />
        {asset && (
          <figure className="region-view">
            <RegionOverlay asset={asset} regions={review.regions} />
            <figcaption className="field__hint">{es.review.marked}</figcaption>
          </figure>
        )}
        {review.issues.map((issue) => (
          <div key={issue.code} className="issue">
            <strong>{severityLabel[issue.severity]}: {issue.description}</strong>
            <span>{es.review.objects}: {issue.object_ids.join(', ')}</span>
            <span>{es.review.evidence}: {issue.evidence}</span>
            <span>{es.review.suggestion}: {issue.suggested_fix}</span>
          </div>
        ))}
        {objectIds.map((id) => (
          <Field key={id} label={`${es.review.action} (${id})`}>
            <select value={choices[id] ?? KEEP} onChange={(e) => setChoices({ ...choices, [id]: e.target.value as Choice })}>
              <option value={KEEP}>{es.review.keep}</option>
              {Object.values(Technique).map((t) => (
                <option key={t} value={t}>{es.review.setTechnique}: {techniqueLabel[t]}</option>
              ))}
              <option value={EXCLUDE}>{es.review.exclude}</option>
            </select>
          </Field>
        ))}
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
        <div className="row">
          <button type="button" onClick={apply} disabled={busy}>{es.review.apply}</button>
        </div>
      </Card.Body>
    </Card>
  );
}
