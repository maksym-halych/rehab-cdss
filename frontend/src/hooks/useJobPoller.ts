import { useState, useEffect, useRef } from 'react';
import { getJob } from '../api/client';
import type { Job } from '../api/types';

interface UseJobPollerResult {
  job: Job | null;
  isPolling: boolean;
}

function isTerminal(job: Job): boolean {
  const m2Done = job.module2_status === 'completed' || job.module2_status === 'failed';
  return job.status === 'failed' || (job.status === 'completed' && m2Done);
}

export function useJobPoller(jobId: string | null): UseJobPollerResult {
  // Keyed by job id, so a stale job is never returned after jobId changes
  const [polled, setPolled] = useState<{ jobId: string; job: Job } | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const result = await getJob(jobId);
        setPolled({ jobId, job: result });
        if (isTerminal(result) && intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      } catch {
        // keep polling on transient errors
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId]);

  const job = polled && polled.jobId === jobId ? polled.job : null;
  const isPolling = jobId !== null && !(job && isTerminal(job));
  return { job, isPolling };
}
