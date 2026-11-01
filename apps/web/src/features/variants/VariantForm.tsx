import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import { FitMode } from '../../contracts/settings';
import type { Job } from '../../contracts/job';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage } from '../../shared/hooks/useAsync';
import { parseMm } from '../settings/validateSettings';

/** Una variante es un trabajo nuevo regenerado desde la geometría; la web nunca escala puntadas. */
export function VariantForm({ job }: { job: Job }) {
  const api = useApi();
  const navigate = useNavigate();
  const [width, setWidth] = useState(String(job.settings.target.width_mm));
  const [height, setHeight] = useState(String(job.settings.target.height_mm));
  const [errors, setErrors] = useState<{ width?: boolean; height?: boolean }>({});
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const w = parseMm(width);
    const h = parseMm(height);
    const found = { width: !(w > 0), height: !(h > 0) };
    setErrors(found);
    if (found.width || found.height) return;
    setBusy(true);
    setError(undefined);
    try {
      const variant = await api.createRevision(job.project_id, {
        kind: 'size_variant',
        parent_job_id: job.id,
        target: { width_mm: w, height_mm: h, fit: FitMode.Contain },
      });
      navigate(`/trabajos/${variant.id}`);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Card>
      <Card.Header>{es.variants.title}</Card.Header>
      <Card.Body>
        <p>{es.variants.text}</p>
        <form onSubmit={submit} noValidate className="stack">
          <div className="form-grid">
            <Field label={es.settings.width} error={errors.width ? es.settings.positive : undefined}>
              <input type="text" inputMode="decimal" value={width} onChange={(e) => setWidth(e.target.value)} />
            </Field>
            <Field label={es.settings.height} error={errors.height ? es.settings.positive : undefined}>
              <input type="text" inputMode="decimal" value={height} onChange={(e) => setHeight(e.target.value)} />
            </Field>
          </div>
          <div className="row">
            <button type="submit" disabled={busy}>{es.variants.create}</button>
          </div>
        </form>
        {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
      </Card.Body>
    </Card>
  );
}
