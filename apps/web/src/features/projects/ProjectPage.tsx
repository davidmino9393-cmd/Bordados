import { useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import type { SourceAsset } from '../../contracts/project';
import type { JobSettings } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { newIdempotencyKey } from '../../shared/utils/idempotency';
import { SettingsForm } from '../settings/SettingsForm';
import { UploadPanel } from '../upload/UploadPanel';
import { JobHistory } from './JobHistory';

export function ProjectPage() {
  const { projectId = '' } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const project = useAsync(() => api.getProject(projectId), [api, projectId]);
  const catalog = useAsync(() => api.getProfiles(), [api]);
  const [pickedId, setPickedId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string>();
  // La misma clave se reutiliza si el envío falla y se reintenta.
  const idempotencyKey = useRef(newIdempotencyKey());

  const assets = project.data?.assets ?? [];
  const selected = assets.find((a) => a.id === pickedId) ?? assets.at(-1);

  const onUploaded = (asset: SourceAsset) => {
    setPickedId(asset.id);
    project.reload();
  };

  const generate = async (settings: JobSettings) => {
    if (!selected) return;
    setBusy(true);
    setSubmitError(undefined);
    try {
      const job = await api.createJob(projectId, selected.id, settings, idempotencyKey.current);
      idempotencyKey.current = newIdempotencyKey();
      navigate(`/trabajos/${job.id}`);
    } catch (e) {
      setSubmitError(errorMessage(e));
      setBusy(false);
    }
  };

  const loadError = project.error ?? catalog.error;
  if (loadError) return <Notice tone={NoticeTone.Error}>{loadError}</Notice>;
  if (!project.data || !catalog.data) return <p role="status">{es.loading}</p>;

  return (
    <>
      <h1>{project.data.project.name}</h1>
      <UploadPanel
        projectId={projectId}
        limits={catalog.data.upload_limits}
        assets={assets}
        selected={selected}
        onSelect={setPickedId}
        onUploaded={onUploaded}
      />
      <SettingsForm catalog={catalog.data} asset={selected} busy={busy} onSubmit={generate} />
      {submitError && <Notice tone={NoticeTone.Error}>{submitError}</Notice>}
      <JobHistory jobs={project.data.jobs} />
    </>
  );
}
