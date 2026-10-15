import React from 'react';
import { Trash2 } from 'lucide-react';
import { FileListScroller } from '../files/FileListScroller';
import { FileUploadTrigger } from '../files/FileUploadTrigger';
import { PersonSelector } from '../files/PersonSelector';
import { Button } from '../ui/Button';
import type { DetectFilesResponse, ConfigResponse, UploadedFile } from '../../api/types';
import styles from './FilesPanel.module.css';

interface FilesPanelProps {
  detectedPeople: DetectFilesResponse['detected_people'];
  fileGroups: DetectFilesResponse['file_groups'] | null;
  fileAssignments: Record<string, string>;
  isLoadingDetect: boolean;
  selectedPersonKey: string;
  onSelectPerson: (key: string) => void;
  pushupTypeOverrides: Record<string, string>;
  onPushupVariantChange: (fileName: string, value: string) => void;
  onRemoveFile: (fileName: string) => void;
  onFilesAdded: (files: UploadedFile[]) => void;
  onClear: () => void;
  isProcessing: boolean;
  config: ConfigResponse | null;
  hasFiles: boolean;
  totalFiles: number;
  recognizedFiles: number;
}

export const FilesPanel: React.FC<FilesPanelProps> = ({
  detectedPeople,
  fileGroups,
  fileAssignments,
  isLoadingDetect,
  selectedPersonKey,
  onSelectPerson,
  pushupTypeOverrides,
  onPushupVariantChange,
  onRemoveFile,
  onFilesAdded,
  onClear,
  isProcessing,
  config,
  hasFiles,
  totalFiles,
  recognizedFiles,
}) => {
  const multiplePeople = detectedPeople.length > 1;
  return (
    <section
      className={styles.panel}
      aria-label="Список файлів"
      style={
        multiplePeople
          ? { ['--file-list-max-height' as string]: 'calc(100vh - 300px)' }
          : undefined
      }
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title}>Файли</h2>
          {hasFiles && (
            <span className={styles.stats}>
              {recognizedFiles} / {totalFiles} розпізнано
            </span>
          )}
        </div>
        <div className={styles.headerActions}>
          <FileUploadTrigger onFilesAdded={onFilesAdded} variant="inline" />
          <Button
            variant="ghost"
            size="sm"
            onClick={onClear}
            disabled={!hasFiles || isProcessing}
            type="button"
            className={styles.clearBtn}
          >
            <Trash2 size={14} aria-hidden="true" />
            Очистити список
          </Button>
        </div>
      </div>

      {detectedPeople.length > 1 && (
        <div className={styles.selectorWrap}>
          <PersonSelector
            people={detectedPeople}
            selectedKey={selectedPersonKey}
            onSelect={onSelectPerson}
          />
        </div>
      )}

      <FileListScroller
        detectedPeople={detectedPeople}
        fileGroups={fileGroups}
        fileAssignments={fileAssignments}
        isLoading={isLoadingDetect}
        selectedPersonKey={selectedPersonKey}
        onSelectPerson={onSelectPerson}
        pushupTypeOverrides={pushupTypeOverrides}
        onPushupVariantChange={onPushupVariantChange}
        onRemoveFile={onRemoveFile}
        config={config}
        hasFiles={hasFiles}
      />
    </section>
  );
};
