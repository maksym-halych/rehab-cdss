import React from 'react';
import { Loader2 } from 'lucide-react';
import { PersonAccordion } from './PersonAccordion';
import { EmptyState } from './EmptyState';
import type { DetectFilesResponse, ConfigResponse } from '../../api/types';
import styles from './FileListScroller.module.css';

interface FileListScrollerProps {
  detectedPeople: DetectFilesResponse['detected_people'];
  fileGroups: DetectFilesResponse['file_groups'] | null;
  fileAssignments: Record<string, string>;
  isLoading: boolean;
  selectedPersonKey: string;
  onSelectPerson: (key: string) => void;
  pushupTypeOverrides: Record<string, string>;
  onPushupVariantChange: (fileName: string, value: string) => void;
  onRemoveFile: (fileName: string) => void;
  config: ConfigResponse | null;
  hasFiles: boolean;
}

type FileGroups = NonNullable<DetectFilesResponse['file_groups']>;

function filterFileGroupsForPerson(
  fileGroups: FileGroups,
  personKey: string,
  assignments: Record<string, string>
): FileGroups {
  const belongs = (f: string) => !assignments[f] || assignments[f] === personKey;
  return {
    pdf: Object.fromEntries(
      Object.entries(fileGroups.pdf).map(([k, files]) => [k, (files as string[]).filter(belongs)])
    ) as FileGroups['pdf'],
    csv: Object.fromEntries(
      Object.entries(fileGroups.csv).map(([k, files]) => [k, (files as string[]).filter(belongs)])
    ) as FileGroups['csv'],
    unknown: fileGroups.unknown.filter(belongs),
  };
}

export const FileListScroller: React.FC<FileListScrollerProps> = ({
  detectedPeople,
  fileGroups,
  fileAssignments,
  isLoading,
  selectedPersonKey,
  onSelectPerson,
  pushupTypeOverrides,
  onPushupVariantChange,
  onRemoveFile,
  config,
  hasFiles,
}) => {
  if (!hasFiles) {
    return (
      <div className={styles.container}>
        <EmptyState />
      </div>
    );
  }

  if (isLoading && !fileGroups) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingState}>
          <Loader2 size={24} className={styles.spinner} aria-hidden="true" />
          <span>Розпізнавання файлів…</span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {fileGroups && detectedPeople.length > 0 ? (
        <div className={styles.persons}>
          {detectedPeople.map((person) => (
            <PersonAccordion
              key={person.key}
              personKey={person.key}
              displayName={person.display}
              isOpen={selectedPersonKey === person.key}
              onToggle={() => {
                onSelectPerson(selectedPersonKey === person.key ? '' : person.key);
              }}
              fileGroups={filterFileGroupsForPerson(fileGroups, person.key, fileAssignments)}
              pushupTypeOverrides={pushupTypeOverrides}
              onPushupVariantChange={onPushupVariantChange}
              onRemoveFile={onRemoveFile}
              config={config}
            />
          ))}
        </div>
      ) : fileGroups ? (
        <div className={styles.persons}>
          <PersonAccordion
            personKey="__undetected__"
            displayName="Невідомий пацієнт"
            isOpen
            onToggle={() => {}}
            fileGroups={fileGroups}
            pushupTypeOverrides={pushupTypeOverrides}
            onPushupVariantChange={onPushupVariantChange}
            onRemoveFile={onRemoveFile}
            config={config}
          />
        </div>
      ) : null}
    </div>
  );
};
