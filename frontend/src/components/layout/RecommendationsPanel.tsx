import React, { useState, useEffect, useCallback } from 'react';
import { Download, Copy, Check, Loader2 } from 'lucide-react';
import { Button } from '../ui/Button';
import { MarkdownReport } from '../ui/MarkdownReport';
import { Module2Timeline } from '../recommendations/Module2Timeline';
import { getRehabReport, downloadRehabDocx } from '../../api/client';
import type { Job } from '../../api/types';
import styles from './RecommendationsPanel.module.css';

interface RecommendationsPanelProps {
  job: Job | null;
  currentJobId: string | null;
}

export const RecommendationsPanel: React.FC<RecommendationsPanelProps> = ({
  job,
  currentJobId,
}) => {
  // Report and fetch failure are keyed by job id, so a new job shows no stale report
  const [report, setReport] = useState<{ jobId: string; markdown: string } | null>(null);
  const [failedJobId, setFailedJobId] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  const reportMarkdown = report && report.jobId === currentJobId ? report.markdown : null;
  const isLoadingReport =
    job?.module2_status === 'completed' &&
    currentJobId !== null &&
    reportMarkdown === null &&
    failedJobId !== currentJobId;

  // Fetch report when module2 completes
  useEffect(() => {
    if (!isLoadingReport || !currentJobId) return;
    let cancelled = false;
    getRehabReport(currentJobId)
      .then((markdown) => {
        if (!cancelled) setReport({ jobId: currentJobId, markdown });
      })
      .catch((err: unknown) => {
        console.error(err);
        if (!cancelled) setFailedJobId(currentJobId);
      });
    return () => {
      cancelled = true;
    };
  }, [isLoadingReport, currentJobId]);

  const handleCopy = useCallback(async () => {
    if (reportMarkdown) {
      try {
        await navigator.clipboard.writeText(reportMarkdown);
        setCopySuccess(true);
        setTimeout(() => setCopySuccess(false), 2000);
      } catch {
        // Clipboard API may fail if page is not focused
      }
    }
  }, [reportMarkdown]);

  const handleDownload = useCallback(() => {
    if (currentJobId) {
      downloadRehabDocx(currentJobId);
    }
  }, [currentJobId]);

  // No job or no currentJobId
  if (!job || !currentJobId) {
    return (
      <div className={styles.panel}>
        <div className={styles.emptyState}>
          <p className={styles.emptyText}>
            Спершу запустiть аналiз на вкладцi &laquo;Аналiз&raquo;
          </p>
        </div>
      </div>
    );
  }

  // Module 1 running
  if (job.status === 'pending' || job.status === 'running') {
    return (
      <div className={styles.panel}>
        <div className={styles.centeredState}>
          <Loader2 size={32} className={styles.spinner} aria-hidden="true" />
          <p className={styles.statusText}>Очiкування завершення аналiзу...</p>
        </div>
      </div>
    );
  }

  // Module 1 failed
  if (job.status === 'failed') {
    return (
      <div className={styles.panel}>
        <div className={styles.centeredState}>
          <div className={styles.errorBanner}>
            <p className={styles.errorTitle}>Помилка аналiзу</p>
            {job.error && <p className={styles.errorDetail}>{job.error}</p>}
          </div>
        </div>
      </div>
    );
  }

  // Module 2 running
  if (job.module2_status === 'running' || job.module2_status === 'idle') {
    return (
      <div className={styles.panel}>
        <div className={styles.centeredState}>
          <h2 className={styles.sectionTitle}>Генерацiя клiнiчних рекомендацiй</h2>
          <Module2Timeline
            stepIndex={job.module2_step_index}

            status={job.module2_status === 'idle' ? 'running' : job.module2_status}
            error={job.module2_error}
          />
        </div>
      </div>
    );
  }

  // Module 2 failed
  if (job.module2_status === 'failed') {
    return (
      <div className={styles.panel}>
        <div className={styles.centeredState}>
          <h2 className={styles.sectionTitle}>Генерацiя клiнiчних рекомендацiй</h2>
          <Module2Timeline
            stepIndex={job.module2_step_index}

            status="failed"
            error={job.module2_error}
          />
          <div className={styles.errorBanner}>
            <p className={styles.errorTitle}>Помилка генерацiї рекомендацiй</p>
            {job.module2_error && <p className={styles.errorDetail}>{job.module2_error}</p>}
          </div>
        </div>
      </div>
    );
  }

  // Module 2 completed
  return (
    <div className={styles.panel}>
      {isLoadingReport ? (
        <div className={styles.centeredState}>
          <Loader2 size={32} className={styles.spinner} aria-hidden="true" />
          <p className={styles.statusText}>Завантаження звiту...</p>
        </div>
      ) : reportMarkdown ? (
        <>
          <div className={styles.actionBar}>
            <Button variant="primary" size="sm" onClick={handleDownload}>
              <Download size={16} aria-hidden="true" />
              Завантажити план реабiлiтацiї (.docx)
            </Button>
            <Button variant="secondary" size="sm" onClick={handleCopy}>
              {copySuccess ? (
                <Check size={16} aria-hidden="true" />
              ) : (
                <Copy size={16} aria-hidden="true" />
              )}
              {copySuccess ? 'Скопiйовано!' : 'Копiювати'}
            </Button>
          </div>
          <div className={styles.reportContent}>
            <MarkdownReport markdown={reportMarkdown} />
          </div>
        </>
      ) : (
        <div className={styles.centeredState}>
          <p className={styles.statusText}>Звiт недоступний</p>
        </div>
      )}

      {copySuccess && (
        <div className={styles.toast} role="status" aria-live="polite">
          <Check size={16} aria-hidden="true" />
          Скопiйовано!
        </div>
      )}
    </div>
  );
};
