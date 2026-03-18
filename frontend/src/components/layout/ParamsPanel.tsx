import React from 'react';
import { PatientParamsForm } from '../params/PatientParamsForm';
import { ActionBar } from '../params/ActionBar';
import { JobProgressBar } from '../params/JobProgressBar';
import { WarningBanner } from '../params/WarningBanner';
import { DownloadSection } from '../params/DownloadSection';
import type { PatientParams, ConfigResponse, Job } from '../../api/types';
import styles from './ParamsPanel.module.css';

interface ParamsPanelProps {
  params: PatientParams;
  onParamChange: <K extends keyof PatientParams>(key: K, value: PatientParams[K]) => void;
  config: ConfigResponse | null;
  onProcess: () => void;
  isProcessing: boolean;
  hasFiles: boolean;
  job: Job | null;
  isPolling: boolean;
  currentJobId: string | null;
}

export const ParamsPanel: React.FC<ParamsPanelProps> = ({
  params,
  onParamChange,
  config,
  onProcess,
  isProcessing,
  hasFiles,
  job,
  isPolling,
  currentJobId,
}) => {
  const warnings = job?.warnings ?? [];
  const jobCompleted = job?.status === 'completed';

  return (
    <section className={styles.panel} aria-label="Параметри пацієнта">
      <div className={styles.header}>
        <h2 className={styles.title}>Параметри пацієнта</h2>
      </div>

      <div className={styles.body}>
        <PatientParamsForm
          params={params}
          onParamChange={onParamChange}
          config={config}
        />

        {warnings.length > 0 && <WarningBanner messages={warnings} />}

        <ActionBar
          onProcess={onProcess}
          isProcessing={isProcessing}
          hasFiles={hasFiles}
        />

        {(isProcessing || isPolling || job) && (
          <JobProgressBar job={job} isPolling={isPolling} />
        )}

        {jobCompleted && currentJobId && (
          <DownloadSection jobId={currentJobId} />
        )}
      </div>
    </section>
  );
};
