import React from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '../ui/Button';
import { isJobFinished, useJobList } from '../../hooks/useJobList';
import type { ConfigResponse, JobSummary } from '../../api/types';
import styles from './JobHistoryPanel.module.css';

interface JobHistoryPanelProps {
  currentJobId: string | null;
  config: ConfigResponse | null;
  onOpen: (jobId: string) => void;
}

const DATE_FORMAT = new Intl.DateTimeFormat('uk-UA', { dateStyle: 'medium', timeStyle: 'short' });

function jobState(job: JobSummary): { label: string; className: string } {
  if (job.status === 'failed' || job.module2_status === 'failed') {
    return { label: 'Помилка', className: styles.stateFailed };
  }
  if (isJobFinished(job)) return { label: 'Готово', className: styles.stateDone };
  return { label: 'Виконується', className: styles.stateRunning };
}

function patientLine(job: JobSummary, config: ConfigResponse | null): string {
  const level = config?.activity_levels.find((l) => l.value === job.activity_level)?.label;
  const parts = [
    job.age !== null ? `${job.age} р.` : null,
    job.gender,
    level ?? job.activity_level,
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'Дані пацієнта не вказано';
}

export const JobHistoryPanel: React.FC<JobHistoryPanelProps> = ({ currentJobId, config, onOpen }) => {
  const { jobs, error, reload } = useJobList();

  return (
    <section className={styles.panel} aria-label="Мої аналізи">
      <div className={styles.header}>
        <h2 className={styles.title}>Мої аналізи</h2>
        <Button variant="ghost" size="sm" iconOnly aria-label="Оновити список" onClick={reload}>
          <RefreshCw size={16} aria-hidden="true" />
        </Button>
      </div>

      {error && <p className={styles.message}>Не вдалося завантажити список аналізів</p>}
      {!error && jobs === null && <p className={styles.message}>Завантаження...</p>}
      {!error && jobs?.length === 0 && (
        <p className={styles.message}>Ще немає аналізів. Запустіть перший на вкладці «Аналіз».</p>
      )}

      {jobs && jobs.length > 0 && (
        <ul className={styles.list}>
          {jobs.map((job) => {
            const state = jobState(job);
            const isCurrent = job.job_id === currentJobId;
            return (
              <li key={job.job_id}>
                <button
                  type="button"
                  className={[styles.item, isCurrent ? styles.itemCurrent : ''].filter(Boolean).join(' ')}
                  aria-current={isCurrent || undefined}
                  onClick={() => onOpen(job.job_id)}
                >
                  <span className={styles.itemMain}>
                    <span className={styles.date}>{DATE_FORMAT.format(new Date(job.created_at))}</span>
                    <span className={styles.patient}>{patientLine(job, config)}</span>
                  </span>
                  <span className={[styles.state, state.className].join(' ')}>{state.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
};
