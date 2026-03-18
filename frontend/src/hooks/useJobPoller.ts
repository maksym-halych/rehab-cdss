import { useState, useEffect, useRef } from 'react';
import { getJob } from '../api/client';
import type { Job } from '../api/types';

interface UseJobPollerResult {
  job: Job | null;
  isPolling: boolean;
}

export function useJobPoller(jobId: string | null): UseJobPollerResult {
  const [job, setJob] = useState<Job | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setIsPolling(false);
      return;
    }

    setIsPolling(true);

    const poll = async () => {
      try {
        const result = await getJob(jobId);
        setJob(result);
        const m2Done = result.module2_status === 'completed' || result.module2_status === 'failed';
        const isTerminal =
          result.status === 'failed' ||
          (result.status === 'completed' && m2Done);
        if (isTerminal) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setIsPolling(false);
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

  return { job, isPolling };
}
