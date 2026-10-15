import React from 'react';
import { X } from 'lucide-react';
import type { Job } from '../../api/types';
import styles from './JobProgressBar.module.css';

interface JobProgressBarProps {
  job: Job | null;
  isPolling: boolean;
}

export const JobProgressBar: React.FC<JobProgressBarProps> = ({ job, isPolling }) => {
  if (!job && !isPolling) return null;

  const status = job?.status ?? 'pending';

  if (status === 'completed') {
    return null;
  }

  if (status === 'failed') {
    return (
      <div className={[styles.bar, styles.barFailed].join(' ')}>
        <X size={16} aria-hidden="true" />
        <span>{job?.error ?? 'Виникла помилка під час обробки'}</span>
      </div>
    );
  }

  return (
    <div className={[styles.bar, styles.barRunning].join(' ')}>
      <div className={styles.progressTrack}>
        <div className={styles.progressIndeterminate} role="progressbar" aria-label="Обробка" />
      </div>
      <span className={styles.statusLabel}>Обробка…</span>
    </div>
  );
};
