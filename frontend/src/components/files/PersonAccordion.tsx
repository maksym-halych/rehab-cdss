import React from 'react';
import { Accordion } from '../ui/Accordion';
import { TestGroupAccordion } from './TestGroupAccordion';
import type { FileGroups, ConfigResponse } from '../../api/types';
import styles from './PersonAccordion.module.css';

interface PersonAccordionProps {
  personKey: string;
  displayName: string;
  isOpen: boolean;
  onToggle: () => void;
  fileGroups: FileGroups;
  pushupTypeOverrides: Record<string, string>;
  onPushupVariantChange: (fileName: string, value: string) => void;
  onRemoveFile: (fileName: string) => void;
  config: ConfigResponse | null;
}

export const PersonAccordion: React.FC<PersonAccordionProps> = ({
  personKey: _personKey,
  displayName,
  isOpen,
  onToggle,
  fileGroups,
  pushupTypeOverrides,
  onPushupVariantChange,
  onRemoveFile,
  config,
}) => {
  const variantFamilies = config?.variant_families ?? {};
  const testTypes = config?.test_types ?? [];

  const getVariantFamily = (groupKey: string) => {
    const testType = testTypes.find((t) => t.key === groupKey);
    if (!testType?.variant_family) return null;
    return variantFamilies[testType.variant_family] ?? null;
  };

  const getConfigLabel = (groupKey: string): string | undefined => {
    return testTypes.find((t) => t.key === groupKey)?.label;
  };

  const summary = (
    <span className={styles.personName}>{displayName}</span>
  );

  const pdfGroups = Object.entries(fileGroups.pdf) as [keyof FileGroups['pdf'], string[]][];
  const csvGroups = Object.entries(fileGroups.csv) as [keyof FileGroups['csv'], string[]][];
  const unknownFiles = fileGroups.unknown;

  const hasFiles =
    pdfGroups.some(([, files]) => files.length > 0) ||
    csvGroups.some(([, files]) => files.length > 0) ||
    unknownFiles.length > 0;

  return (
    <Accordion
      open={isOpen}
      onToggle={onToggle}
      summary={summary}
      summaryClassName={styles.personSummary}
    >
      <div className={styles.groups}>
        {!hasFiles && (
          <p className={styles.noFiles}>Файли для цього пацієнта не визначено</p>
        )}
        {pdfGroups.map(([key, files]) =>
          files.length > 0 ? (
            <TestGroupAccordion
              key={key}
              groupKey={key}
              fileNames={files}
              variantFamily={getVariantFamily(key)}
              overrides={pushupTypeOverrides}
              onVariantChange={
                getVariantFamily(key) ? onPushupVariantChange : undefined
              }
              onRemoveFile={onRemoveFile}
              configLabel={getConfigLabel(key)}
            />
          ) : null
        )}
        {csvGroups.map(([key, files]) =>
          files.length > 0 ? (
            <TestGroupAccordion
              key={key}
              groupKey={key}
              fileNames={files}
              variantFamily={getVariantFamily(key)}
              overrides={pushupTypeOverrides}
              onVariantChange={
                getVariantFamily(key) ? onPushupVariantChange : undefined
              }
              onRemoveFile={onRemoveFile}
              configLabel={getConfigLabel(key)}
            />
          ) : null
        )}
        {unknownFiles.length > 0 && (
          <TestGroupAccordion
            groupKey="unknown"
            fileNames={unknownFiles}
            isUnknown
            overrides={{}}
            onRemoveFile={onRemoveFile}
          />
        )}
      </div>
    </Accordion>
  );
};

