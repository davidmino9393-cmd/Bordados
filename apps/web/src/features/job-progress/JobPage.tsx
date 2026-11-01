import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../api/ApiProvider';
import { JobStatus } from '../../contracts/job';
import { es } from '../../copy/es';
import { Notice, NoticeTone } from '../../shared/components/Notice';
import { useAsync } from '../../shared/hooks/useAsync';
import { useJobPolling } from '../../shared/hooks/useJobPolling';
import { ReviewPanel } from '../review/ReviewPanel';
import { CancelledNotice, FailedNotice } from './FailureAndCancelled';
import { JobProgress } from './JobProgress';
import { ReadyResult } from './ReadyResult';

export function JobPage() {
  const { jobId = '' } = useParams();
  const api = useApi();
  const { job, error, replace } = useJobPolling(jobId);
  const projectId = job?.project_id;
  const project = useAsync(
    () => (projectId ? api.getProject(projectId) : Promise.resolve(null)),
    [api, projectId],
  );

  if (error && !job) return <Notice tone={NoticeTone.Error}>{error}</Notice>;
  if (!job) return <p role="status">{es.loading}</p>;

  const asset = project.data?.assets.find((a) => a.id === job.source_asset_id);
  return (
    <>
      <p>
        <Link to={`/proyectos/${job.project_id}`}>← {project.data?.project.name ?? es.back}</Link>
      </p>
      <h1>{es.progress.title}</h1>
      {error && <Notice tone={NoticeTone.Warning}>{error}</Notice>}
      <JobProgress job={job} onJobChanged={replace} />
      {job.status === JobStatus.Failed && <FailedNotice job={job} />}
      {job.status === JobStatus.Cancelled && <CancelledNotice job={job} />}
      {job.status === JobStatus.NeedsReview && <ReviewPanel job={job} asset={asset} />}
      {job.status === JobStatus.ReadyForSewout && <ReadyResult job={job} asset={asset} />}
    </>
  );
}
