import { useState, type FormEvent } from 'react';
import { useApi } from '../../api/ApiProvider';
import type { JobResponse } from '../../contracts/job';
import { SewoutStatus } from '../../contracts/sewout';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { Field } from '../../shared/components/Field';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { useIdempotencyKey } from '../../shared/hooks/useIdempotencyKey';
import {
  validateSewout,
  toSewoutRequest,
  type SewoutErrorKind,
  type SewoutErrors,
  type SewoutFormValues,
} from './validateSewout';

interface SewoutFormProps {
  /** Trabajo en ready_for_sewout: la muestra se registra sobre su revisión. */
  job: JobResponse;
  onJobChanged: (job: JobResponse) => void;
}

const RESULT_OPTIONS = [SewoutStatus.Approved, SewoutStatus.NeedsAdjustment, SewoutStatus.Untested] as const;

const errorText = (kind: SewoutErrorKind | undefined) => (kind ? es.sewout.errors[kind] : undefined);

/**
 * Registro de la muestra física (POST /projects/{id}/sewouts). Guarda el resultado de
 * coser una muestra real; nunca cambia el estado digital del trabajo: tras registrar,
 * se vuelve a pedir el trabajo y se muestra la proyección que informa el servidor.
 */
export function SewoutForm({ job, onJobChanged }: SewoutFormProps) {
  const api = useApi();
  const keyFor = useIdempotencyKey();
  const catalog = useAsync(() => api.getProfiles(), [api]);
  const [values, setValues] = useState<SewoutFormValues>({
    status: '',
    tested_at: '',
    fabric_profile: job.settings_snapshot.fabric_profile,
    stabilizer: '',
    thread: '',
    observations: '',
  });
  const [errors, setErrors] = useState<SewoutErrors>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState(false);
  const set = <K extends keyof SewoutFormValues>(key: K, value: SewoutFormValues[K]) => {
    setSaved(false);
    setValues((v) => ({ ...v, [key]: value }));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found = validateSewout(values, Date.now());
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    setError(undefined);
    try {
      const request = toSewoutRequest(values, job.revision_id);
      await api.recordSewout(job.project_id, request, keyFor(request));
      setSaved(true);
      setValues((v) => ({ ...v, status: '', tested_at: '', stabilizer: '', thread: '', observations: '' }));
      onJobChanged(await api.getJob(job.job_id));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const text = es.sewout;
  const untested = values.status === SewoutStatus.Untested;
  return (
    <Card>
      <Card.Header>{text.title}</Card.Header>
      <Card.Body>
        <p>{text.intro}</p>
        <form onSubmit={submit} noValidate className="stack">
          <fieldset aria-describedby={errors.status ? 'sewout-status-error' : undefined}>
            <legend>{text.result}</legend>
            {RESULT_OPTIONS.map((option) => (
              <label key={option} className="radio">
                <input
                  type="radio"
                  name="sewout_status"
                  value={option}
                  checked={values.status === option}
                  onChange={() => set('status', option)}
                />
                {text.options[option]}
              </label>
            ))}
            {errors.status && <p id="sewout-status-error" className="field__error">{errorText(errors.status)}</p>}
          </fieldset>
          <div className="form-grid">
            <Field label={text.testedAt} error={errorText(errors.tested_at)} hint={untested ? text.noDateIfUntested : undefined}>
              <input
                type="datetime-local"
                value={values.tested_at}
                disabled={untested}
                onChange={(e) => set('tested_at', e.target.value)}
              />
            </Field>
            <Field label={text.fabric} error={errorText(errors.fabric_profile)}>
              <select value={values.fabric_profile} onChange={(e) => set('fabric_profile', e.target.value)}>
                {(catalog.data?.fabrics ?? []).map((f) => (
                  <option key={f.profile_id} value={f.profile_id}>{f.label}</option>
                ))}
              </select>
            </Field>
            <Field label={text.stabilizer} error={errorText(errors.stabilizer)}>
              <input type="text" value={values.stabilizer} onChange={(e) => set('stabilizer', e.target.value)} />
            </Field>
            <Field label={text.thread} error={errorText(errors.thread)}>
              <input type="text" value={values.thread} onChange={(e) => set('thread', e.target.value)} />
            </Field>
          </div>
          <Field label={text.observations} error={errorText(errors.observations)}>
            <textarea rows={4} value={values.observations} onChange={(e) => set('observations', e.target.value)} />
          </Field>
          {error && <Notice tone={NoticeTone.Error}>{error}</Notice>}
          {saved && <Notice tone={NoticeTone.Success}>{text.saved}</Notice>}
          <div className="row">
            <button type="submit" disabled={busy || catalog.loading}>{busy ? text.submitting : text.submit}</button>
          </div>
        </form>
      </Card.Body>
    </Card>
  );
}
