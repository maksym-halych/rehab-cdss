import { useState, useEffect, useRef } from 'react';
import { Moon, Sun } from 'lucide-react';
import { UserButton } from '@clerk/react';
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
import { submitJob, submitJsonJob } from './api/client';
import { isJsonFile, parseModule1Json } from './api/module1Json';
import type { Module1JsonPreview, PatientParams, UploadedFile } from './api/types';
import styles from './App.module.css';

const NO_FILES: UploadedFile[] = [];
const ACTIVITY_VALUES: PatientParams['activityLevel'][] = ['elite', 'recreational', 'low'];

const BASE_TABS: Tab[] = [
  { key: 'analysis', label: 'Аналіз' },
  { key: 'recommendations', label: 'Клінічні рекомендації' },
];

function AppHeader({ isDark, onToggleTheme }: { isDark: boolean; onToggleTheme: () => void }) {
  return (
    <div className={styles.headerInner}>
      <span className={styles.appName}>Rehab CDSS</span>
      <div className={styles.headerActions}>
        <Button
          variant="ghost"
          size="sm"
          iconOnly
          aria-label={isDark ? 'Увімкнути світлу тему' : 'Увімкнути темну тему'}
          onClick={onToggleTheme}
        >
          {isDark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        </Button>
        <UserButton />
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState<string>('analysis');
  const [isDark, setIsDark] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  // JSON mode: a Module 1 export was uploaded, so Module 1 and file detection are skipped.
  const [jsonPreview, setJsonPreview] = useState<Module1JsonPreview | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

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
    jsonPreview ? NO_FILES : files,
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

  const handleFilesAdded = async (incoming: UploadedFile[]) => {
    clearJob();
    setSubmitError(null);
    setUploadError(null);

    const jsonUpload = incoming.find((f) => isJsonFile(f.file));
    if (!jsonUpload) {
      // Device files replace a previously loaded JSON export (the two modes don't mix).
      if (jsonPreview) {
        clearFiles();
        setJsonPreview(null);
      }
      addFiles(incoming);
      return;
    }

    let preview: Module1JsonPreview;
    try {
      preview = await parseModule1Json(jsonUpload.file);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Не вдалося прочитати JSON');
      return;
    }
    // A JSON export replaces everything else: one patient, no Module 1.
    clearFiles();
    addFiles([jsonUpload]);
    setJsonPreview(preview);

    const info = preview.patientInfo;
    setPatientParam('personName', info.name ?? '');
    setPatientParam('patientCode', info.patient_code ?? '');
    setPatientParam('age', typeof info.age === 'number' ? info.age : null);
    setPatientParam('gender', info.gender ?? null);
    const level = ACTIVITY_VALUES.find((v) => v === info.activity_level);
    if (level) setPatientParam('activityLevel', level);
    if (incoming.length > 1) {
      setUploadError('Завантажено лише JSON-файл; інші файли пропущено.');
    }
  };

  const handleClear = () => {
    clearFiles();
    clearJob();
    setJsonPreview(null);
    setUploadError(null);
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
      const result = jsonPreview
        ? await submitJsonJob({
            file: files[0].file,
            age: patientParams.age,
            gender: patientParams.gender,
            activityLevel: patientParams.activityLevel,
            manualPersonName: patientParams.personName,
            patientCode: patientParams.patientCode,
          })
        : await submitJob({
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

  // Stop processing when the job reaches a terminal state (state adjusted during render, not in an effect)
  const jobStatusKey = `${job?.status}:${job?.module2_status}`;
  const [prevJobStatusKey, setPrevJobStatusKey] = useState(jobStatusKey);
  if (jobStatusKey !== prevJobStatusKey) {
    setPrevJobStatusKey(jobStatusKey);
    const m2Done = job?.module2_status === 'completed' || job?.module2_status === 'failed';
    if (job?.status === 'failed' || (job?.status === 'completed' && m2Done)) {
      setIsProcessing(false);
    }
  }

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
            jsonPreview={jsonPreview}
            error={uploadError}
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
            showModule1Report={!jsonPreview}
          />
        </div>
      )}

      {activeTab === 'recommendations' && (
        <RecommendationsPanel job={effectiveJob} currentJobId={currentJobId} />
      )}
    </RehabLayout>
  );
}
