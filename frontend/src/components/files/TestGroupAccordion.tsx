import React, { useState } from 'react';
import { Accordion } from '../ui/Accordion';
import { FileRow } from './FileRow';
import { UnknownFileRow } from './UnknownFileRow';
import type { VariantFamily } from '../../api/types';
import styles from './TestGroupAccordion.module.css';

const GROUP_LABELS: Record<string, string> = {
  dental: 'Стоматологія',
  postural: 'Постуральний аналіз',
  baropodometry: 'Баропідометрія (статична)',
  dynamic_baropodometry: 'Баропідометрія (динамічна)',
  spine3d: 'Хребет 3D',
  cervical_goniometry: 'Гоніометрія шийного відділу',
  leg_dynamometry: 'Динамометрія ніг',
  leg_goniometry: 'Гоніометрія ніг',
  arm_goniometry: 'Гоніометрія рук',
  arm_dynamometry: 'Динамометрія рук',
  single_leg_balance: 'Баланс на одній нозі',
  single_leg_landing: 'Приземлення на одній нозі',
  mccall_hamstrings: 'Тест McCall (задня поверхня стегна)',
  shoulder_test: 'Тест плеча',
  push_up: 'Віджимання',
  handstand_push_up: 'Віджимання в стійці',
  counter_movement_jump: 'CMJ (стрибок з підготовки)',
  single_leg_counter_movement_jump: 'CMJ (одна нога)',
  drop_jump: 'Drop Jump',
  imtp: 'IMTP',
  bipodal_stance: 'Стійка (двоопорна)',
  bipodal_landing: 'Приземлення (двоопорне)',
  skipping: 'Скіпінг',
  squats_advanced_analysis: 'Присідання (поглиблений аналіз)',
};

interface TestGroupAccordionProps {
  groupKey: string;
  fileNames: string[];
  isUnknown?: boolean;
  variantFamily?: VariantFamily | null;
  overrides: Record<string, string>;
  onVariantChange?: (fileName: string, value: string) => void;
  onRemoveFile: (fileName: string) => void;
  configLabel?: string;
}

export const TestGroupAccordion: React.FC<TestGroupAccordionProps> = ({
  groupKey,
  fileNames,
  isUnknown = false,
  variantFamily,
  overrides,
  onVariantChange,
  onRemoveFile,
  configLabel,
}) => {
  const [open, setOpen] = useState(true);

  if (fileNames.length === 0) return null;

  const label = isUnknown
    ? 'Невідомі / не розпізнані файли'
    : configLabel ?? GROUP_LABELS[groupKey] ?? groupKey;

  const summary = (
    <span className={styles.summaryInner}>
      <span className={styles.groupLabel}>{label}</span>
      <span className={styles.badge}>{fileNames.length}</span>
    </span>
  );

  return (
    <Accordion open={open} onToggle={() => setOpen((v) => !v)} summary={summary}>
      <div className={styles.fileList}>
        {isUnknown
          ? fileNames.map((fname) => (
              <UnknownFileRow
                key={fname}
                fileName={fname}
                onRemove={() => onRemoveFile(fname)}
              />
            ))
          : fileNames.map((fname) => (
              <FileRow
                key={fname}
                fileName={fname}
                variantFamily={variantFamily}
                variantValue={overrides[fname]}
                onVariantChange={
                  variantFamily && onVariantChange
                    ? (v) => onVariantChange(fname, v)
                    : undefined
                }
                onRemove={() => onRemoveFile(fname)}
              />
            ))}
      </div>
    </Accordion>
  );
};
