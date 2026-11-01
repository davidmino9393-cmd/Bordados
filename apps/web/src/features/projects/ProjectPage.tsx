import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import { startGeneration } from '../../api/startGeneration';
import type { SourceAsset } from '../../contracts/project';
import type { JobSettings } from '../../contracts/settings';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { useDocumentTitle } from '../../shared/hooks/useDocumentTitle';
import { useIdempotencyKey } from '../../shared/hooks/useIdempotencyKey';
import { useRenewBeforeExpiry } from '../../shared/hooks/useRenewBeforeExpiry';
import { earliestDownload } from '../../shared/utils/expiry';
import { SettingsForm } from '../settings/SettingsForm';
import { UploadPanel } from '../upload/UploadPanel';
import { JobHistory } from './JobHistory';

export function ProjectPage() {
  const { projectId = '' } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const keyFor = useIdempotencyKey();
  const project = useAsync(() => api.getProject(projectId), [api, projectId]);
  const catalog = useAsync(() => api.getProfiles(), [api]);
  const [pickedId, setPickedId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string>();

  useDocumentTitle(project.data?.project.name);
  const assets = project.data?.assets ?? [];
  const selected = assets.find((a) => a.asset_id === pickedId) ?? assets.at(-1);

  // Los originales se sirven con enlaces temporales: se renuevan antes de vencer.
  useRenewBeforeExpiry(earliestDownload(assets.map((a) => a.original_download)), project.reload);

  const onUploaded = (asset: SourceAsset) => {
    setPickedId(asset.asset_id);
    project.reload();
  };

  const generate = async (settings: JobSettings) => {
    if (!selected) return;
    setBusy(true);
    setSubmitError(undefined);
    try {
      // Flujo inicial: revisión inicial (base_revision_id: null) y después el trabajo.
      const baseKey = keyFor({ asset: selected.asset_id, settings });
      const job = await startGeneration(api, selected, settings, baseKey);
      navigate(`/trabajos/${job.job_id}`);
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
      <JobHistory jobs={project.data.jobs} hasMore={project.data.jobs_next_cursor !== null} />
    </>
  );
}
