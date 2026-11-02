import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import { startGeneration } from '../../api/startGeneration';
import type { JobResponse } from '../../contracts/job';
import type { SourceAsset } from '../../contracts/project';
import type { JobSettings } from '../../contracts/settings';
import { es } from '../../copy/es';
import { LoadMore } from '../../shared/components/LoadMore';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { errorMessage, useAsync } from '../../shared/hooks/useAsync';
import { useDocumentTitle } from '../../shared/hooks/useDocumentTitle';
import { useIdempotencyKey } from '../../shared/hooks/useIdempotencyKey';
import { useLoadMore } from '../../shared/hooks/useLoadMore';
import { useRenewBeforeExpiry } from '../../shared/hooks/useRenewBeforeExpiry';
import { earliestDownload } from '../../shared/utils/expiry';
import { SettingsForm } from '../settings/SettingsForm';
import { UploadPanel } from '../upload/UploadPanel';
import { JobHistory } from './JobHistory';

const NO_ASSETS: SourceAsset[] = [];
const NO_JOBS: JobResponse[] = [];

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

  const fetchAssets = useCallback(
    async (cursor: string) => {
      const page = await api.getProject(projectId, { assetsCursor: cursor });
      return { items: page.assets, next: page.assets_next_cursor };
    },
    [api, projectId],
  );
  const fetchJobs = useCallback(
    async (cursor: string) => {
      const page = await api.getProject(projectId, { jobsCursor: cursor });
      return { items: page.jobs, next: page.jobs_next_cursor };
    },
    [api, projectId],
  );
  const assetList = useLoadMore(
    { items: project.data?.assets ?? NO_ASSETS, next: project.data?.assets_next_cursor ?? null },
    (asset) => asset.asset_id,
    fetchAssets,
    projectId,
  );
  const jobList = useLoadMore(
    { items: project.data?.jobs ?? NO_JOBS, next: project.data?.jobs_next_cursor ?? null },
    (job) => job.job_id,
    fetchJobs,
    projectId,
  );

  useDocumentTitle(project.data?.project.name);
  const assets = assetList.items;
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
        assetsFooter={
          <LoadMore hasMore={assetList.hasMore} loading={assetList.loading} error={assetList.error} onLoadMore={assetList.loadMore} label={es.upload.moreAssets} />
        }
      />
      <SettingsForm catalog={catalog.data} asset={selected} busy={busy} onSubmit={generate} />
      {submitError && <Notice tone={NoticeTone.Error}>{submitError}</Notice>}
      <JobHistory jobs={jobList.items}>
        <LoadMore hasMore={jobList.hasMore} loading={jobList.loading} error={jobList.error} onLoadMore={jobList.loadMore} label={es.jobs.historyMore} />
      </JobHistory>
    </>
  );
}
