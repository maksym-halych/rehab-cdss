import { useCallback, useEffect, useState } from 'react';
import { listJobs } from '../api/client';
import type { JobSummary } from '../api/types';

const REFRESH_MS = 5000;

export function isJobFinished(job: Pick<JobSummary, 'status' | 'module2_status'>): boolean {
  const m2Done = job.module2_status === 'completed' || job.module2_status === 'failed';
  return job.status === 'failed' || (job.status === 'completed' && m2Done);
}

interface UseJobListResult {
  jobs: JobSummary[] | null;
  error: boolean;
  reload: () => void;
}

// Loads the user's jobs and reloads them every 5 s while one of them is still running
export function useJobList(): UseJobListResult {
  const [jobs, setJobs] = useState<JobSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    listJobs()
      .then((res) => {
        if (cancelled) return;
        setJobs(res.jobs);
        setError(false);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const hasRunning = jobs?.some((j) => !isJobFinished(j)) ?? false;
  useEffect(() => {
    if (!hasRunning) return;
    const timer = setTimeout(reload, REFRESH_MS);
    return () => clearTimeout(timer);
  }, [hasRunning, jobs, reload]);

  return { jobs, error, reload };
}
