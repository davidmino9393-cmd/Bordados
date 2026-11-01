import { JobStatus } from '../../contracts/job';
import { SewoutStatus } from '../../contracts/sewout';
import { jobStatusLabel, sewoutLabel } from '../../copy/es';

const STATUS_TONE: Record<JobStatus, string> = {
  [JobStatus.Queued]: 'neutral',
  [JobStatus.Analyzing]: 'progress',
  [JobStatus.Vectorizing]: 'progress',
  [JobStatus.Digitizing]: 'progress',
  [JobStatus.Validating]: 'progress',
  [JobStatus.ReadyForSewout]: 'ok',
  [JobStatus.NeedsReview]: 'warn',
  [JobStatus.Failed]: 'bad',
  [JobStatus.Cancelled]: 'neutral',
};

/** Estado digital del trabajo. Nunca implica que la muestra física esté aprobada. */
export function JobStatusBadge({ status }: { status: JobStatus }) {
  return <span className={`badge badge--${STATUS_TONE[status]}`}>{jobStatusLabel[status]}</span>;
}

/** Estado de la muestra física, independiente del estado digital. */
export function SewoutBadge({ status }: { status: SewoutStatus }) {
  const tone = status === SewoutStatus.Approved ? 'ok' : status === SewoutStatus.NeedsAdjustment ? 'warn' : 'neutral';
  return <span className={`badge badge--${tone}`}>{sewoutLabel[status]}</span>;
}
