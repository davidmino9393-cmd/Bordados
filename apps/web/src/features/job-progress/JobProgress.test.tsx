import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiProvider } from '../../api/ApiProvider';
import { JobStatus, StageOutcome, type JobResponse } from '../../contracts/job';
import { createMockApiClient } from '../../mocks/MockApiClient';
import { JobProgress } from './JobProgress';

function job(outcome: StageOutcome, status: JobStatus = JobStatus.Digitizing): JobResponse {
  return {
    job_id: 'job_1', status, estimated_remaining_s: null, cancellation_requested: false,
    stages: [
      { stage: 'vectorizing', outcome: StageOutcome.Completed, reason: null, measured_duration_ms: 13200 },
      { stage: 'digitizing', outcome, reason: null, measured_duration_ms: null },
    ],
  } as unknown as JobResponse;
}

function show(value: JobResponse) {
  return render(
    <ApiProvider client={createMockApiClient()}>
      <JobProgress job={value} onJobChanged={() => undefined} />
    </ApiProvider>,
  );
}

describe('progreso del trabajo', () => {
  afterEach(() => vi.useRealTimers());

  it('la etapa en curso muestra que sigue trabajando y cuánto lleva', () => {
    vi.useFakeTimers();
    show(job(StageOutcome.Running));
    expect(screen.getByText(/trabajando hace 0:00/)).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(65_000));
    expect(screen.getByText(/trabajando hace 1:05/)).toBeInTheDocument();
  });

  it('sin etapa en curso no hay contador', () => {
    show(job(StageOutcome.Completed, JobStatus.NeedsReview));
    expect(screen.queryByText(/trabajando hace/)).not.toBeInTheDocument();
  });
});
