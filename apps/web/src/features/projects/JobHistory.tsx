import { Link } from 'react-router-dom';
import type { JobResponse } from '../../contracts/job';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { JobStatusBadge, SewoutBadge } from '../../shared/components/Badges';
import { formatMm } from '../../shared/utils/format';

export function JobHistory({ jobs, hasMore }: { jobs: JobResponse[]; hasMore: boolean }) {
  return (
    <Card>
      <Card.Header>{es.jobs.history}</Card.Header>
      <Card.Body>
        {jobs.length === 0 ? (
          <p>{es.jobs.historyEmpty}</p>
        ) : (
          <ul className="list">
            {[...jobs].reverse().map((job) => (
              <li key={job.job_id} className="list__item">
                <span>
                  {formatMm(job.settings_snapshot.target.width_mm)} × {formatMm(job.settings_snapshot.target.height_mm)} mm
                  {job.parent_job_id && <span className="field__hint"> · {es.jobs.variantOf}</span>}
                </span>
                <span className="row">
                  <JobStatusBadge status={job.status} />
                  <SewoutBadge status={job.sewout_status} />
                  <Link to={`/trabajos/${job.job_id}`}>{es.jobs.open}</Link>
                </span>
              </li>
            ))}
          </ul>
        )}
        {hasMore && <p className="field__hint">{es.jobs.historyMore}</p>}
      </Card.Body>
    </Card>
  );
}
