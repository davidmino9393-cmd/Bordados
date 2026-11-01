import { Link } from 'react-router-dom';
import type { Job } from '../../contracts/job';
import { es } from '../../copy/es';
import { Card } from '../../shared/components/Card';
import { JobStatusBadge, SewoutBadge } from '../../shared/components/Badges';
import { formatMm } from '../../shared/utils/format';

export function JobHistory({ jobs }: { jobs: Job[] }) {
  return (
    <Card>
      <Card.Header>{es.jobs.history}</Card.Header>
      <Card.Body>
        {jobs.length === 0 ? (
          <p>{es.jobs.historyEmpty}</p>
        ) : (
          <ul className="list">
            {[...jobs].reverse().map((job) => (
              <li key={job.id} className="list__item">
                <span>
                  {formatMm(job.settings.target.width_mm)} × {formatMm(job.settings.target.height_mm)} mm
                  {job.parent_job_id && <span className="field__hint"> · {es.jobs.variantOf}</span>}
                </span>
                <span className="row">
                  <JobStatusBadge status={job.status} />
                  <SewoutBadge status={job.sewout_status} />
                  <Link to={`/trabajos/${job.id}`}>{es.jobs.open}</Link>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card.Body>
    </Card>
  );
}
