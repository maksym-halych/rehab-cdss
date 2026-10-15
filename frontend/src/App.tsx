import { useState, useEffect, useRef } from 'react';
import { Moon, Sun } from 'lucide-react';
import { RehabLayout } from './components/layout/RehabLayout';
import { FilesPanel } from './components/layout/FilesPanel';
import { ParamsPanel } from './components/layout/ParamsPanel';
import { RecommendationsPanel } from './components/layout/RecommendationsPanel';
import { TabNav } from './components/ui/TabNav';
import type { Tab } from './components/ui/TabNav';
import { Button } from './components/ui/Button';
import { useRehabStore } from './store/useRehabStore';
import { useDetectFiles } from './hooks/useDetectFiles';
import { useJobPoller } from './hooks/useJobPoller';
import { useConfig } from './hooks/useConfig';
import { submitJob } from './api/client';
import type { UploadedFile } from './api/types';
import styles from './App.module.css';

const BASE_TABS: Tab[] = [
  { key: 'analysis', label: 'Аналіз' },
  { key: 'recommendations', label: 'Клінічні рекомендації' },
];

function AppHeader({ isDark, onToggleTheme }: { isDark: boolean; onToggleTheme: () => void }) {
  return (
    <div className={styles.headerInner}>
      <span className={styles.appName}>Rehab CDSS</span>
      <Button
        variant="ghost"
        size="sm"
        iconOnly
        aria-label={isDark ? 'Увімкнути світлу тему' : 'Увімкнути темну тему'}
        onClick={onToggleTheme}
      >
        {isDark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
      </Button>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('analysis');
  const [isDark, setIsDark] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const {
    files,
    addFiles,
    removeFile,
    clearFiles,
    pushupTypeOverrides,
    manualTestOverrides,
    setPushupVariant,
    selectedPersonKey,
    setSelectedPersonKey,
    patientParams,
    setPatientParam,
    currentJobId,
    setCurrentJobId,
    clearJob,
  } = useRehabStore();

  const { config } = useConfig();
  const { detectedPeople, fileGroups, fileAssignments, isLoading: isLoadingDetect } = useDetectFiles(
    files,
    patientParams.personName
  );
  const { job, isPolling } = useJobPoller(currentJobId);

  const prevHadPeople = useRef(false);
  useEffect(() => {
    const hasPeople = detectedPeople.length > 0;
    if (hasPeople && !prevHadPeople.current) {
      setSelectedPersonKey(detectedPeople[0].key);
    }
    prevHadPeople.current = hasPeople;
  }, [detectedPeople, setSelectedPersonKey]);

  useEffect(() => {
    if (!selectedPersonKey || detectedPeople.length === 0) return;
    const person = detectedPeople.find((p) => p.key === selectedPersonKey);
    if (person?.display) {
      setPatientParam('personName', person.display);
    }
  }, [selectedPersonKey, detectedPeople, setPatientParam]);

  const toggleTheme = () => {
    const next = !isDark;
    document.documentElement.setAttribute('data-theme-transition', '');
    requestAnimationFrame(() => {
      if (next) {
        document.documentElement.setAttribute('data-theme', 'dark');
      } else {
        document.documentElement.removeAttribute('data-theme');
      }
      setIsDark(next);
      setTimeout(() => {
        document.documentElement.removeAttribute('data-theme-transition');
      }, 220);
    });
  };

  const handleFilesAdded = (incoming: UploadedFile[]) => {
    addFiles(incoming);
    clearJob();
    setSubmitError(null);
  };

  const handleClear = () => {
    clearFiles();
    clearJob();
    setSubmitError(null);
    setIsProcessing(false);
    setPatientParam('personName', '');
  };

  const handleRemoveFile = (fileName: string) => {
    const uploaded = files.find((f) => f.originalName === fileName);
    if (uploaded) removeFile(uploaded.clientId);
  };

  const handleProcess = async () => {
    if (!files.length || isProcessing) return;
    setIsProcessing(true);
    setSubmitError(null);
    clearJob();

    const effectivePersonKey = selectedPersonKey || detectedPeople[0]?.key || '';
    try {
      const result = await submitJob({
        files: files.map((f) => f.file),
        age: patientParams.age,
        gender: patientParams.gender,
        activityLevel: patientParams.activityLevel,
        manualPersonName: patientParams.personName,
        selectedPersonKey: effectivePersonKey,
        patientCode: patientParams.patientCode,
        pushupTypeOverrides,
        manualTestOverrides,
      });
      setCurrentJobId(result.job_id);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Невідома помилка');
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    if (job?.status === 'failed') {
      setIsProcessing(false);
      return;
    }
    if (job?.status === 'completed' &&
        (job?.module2_status === 'completed' || job?.module2_status === 'failed')) {
      setIsProcessing(false);
    }
  }, [job?.status, job?.module2_status]);

  const hasFiles = files.length > 0;

  const totalFiles = fileGroups
    ? (() => {
        let count = 0;
        Object.values(fileGroups.pdf).forEach((a) => (count += a.length));
        Object.values(fileGroups.csv).forEach((a) => (count += a.length));
        count += fileGroups.unknown.length;
        return count;
      })()
    : 0;

  const recognizedFiles = fileGroups
    ? (() => {
        let count = 0;
        Object.values(fileGroups.pdf).forEach((a) => (count += a.length));
        Object.values(fileGroups.csv).forEach((a) => (count += a.length));
        return count;
      })()
    : 0;

  const module2Defaults = {
    module2_status: 'idle' as const,
    module2_step: null,
    module2_step_index: 0,
    module2_total_steps: 0,
    module2_step_label: null,
    module2_error: null,
  };

  const effectiveJob =
    submitError
      ? {
          ...(job ?? {
            job_id: '',
            status: 'failed' as const,
            created_at: '',
            completed_at: null,
            result: null,
            warnings: [],
            ...module2Defaults,
          }),
          status: 'failed' as const,
          error: submitError,
        }
      : job;

  const tabs = BASE_TABS.map(tab => ({
    ...tab,
    badge: tab.key === 'recommendations' && effectiveJob?.module2_status === 'running'
      ? 'pulse' as const
      : null,
  }));

  return (
    <RehabLayout
      header={<AppHeader isDark={isDark} onToggleTheme={toggleTheme} />}
      tabNav={
        <TabNav tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      }
    >
      {activeTab === 'analysis' && (
        <div className={styles.analysisLayout}>
          <FilesPanel
            detectedPeople={detectedPeople}
            fileGroups={fileGroups}
            fileAssignments={fileAssignments}
            isLoadingDetect={isLoadingDetect}
            selectedPersonKey={selectedPersonKey}
            onSelectPerson={setSelectedPersonKey}
            pushupTypeOverrides={pushupTypeOverrides}
            onPushupVariantChange={setPushupVariant}
            onRemoveFile={handleRemoveFile}
            onFilesAdded={handleFilesAdded}
            onClear={handleClear}
            isProcessing={isProcessing}
            config={config}
            hasFiles={hasFiles}
            totalFiles={totalFiles}
            recognizedFiles={recognizedFiles}
          />
          <ParamsPanel
            params={patientParams}
            onParamChange={setPatientParam}
            config={config}
            onProcess={handleProcess}
            isProcessing={isProcessing}
            hasFiles={hasFiles}
            job={effectiveJob}
            isPolling={isPolling}
            currentJobId={currentJobId}
          />
        </div>
      )}

      {activeTab === 'recommendations' && (
        <RecommendationsPanel job={effectiveJob} currentJobId={currentJobId} />
      )}
    </RehabLayout>
  );
}
