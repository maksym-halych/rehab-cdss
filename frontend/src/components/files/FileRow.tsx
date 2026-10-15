import React from 'react';
import { FileText, X } from 'lucide-react';
import { Button } from '../ui/Button';
import type { VariantFamily } from '../../api/types';
import styles from './FileRow.module.css';

interface FileRowProps {
  fileName: string;
  variantFamily?: VariantFamily | null;
  variantValue?: string;
  onVariantChange?: (value: string) => void;
  onRemove: () => void;
}

export const FileRow: React.FC<FileRowProps> = ({
  fileName,
  variantFamily,
  variantValue,
  onVariantChange,
  onRemove,
}) => {
  return (
    <div className={styles.row}>
      <FileText size={14} className={styles.fileIcon} aria-hidden="true" />
      <span className={styles.fileName} title={fileName}>
        {fileName}
      </span>
      {variantFamily && onVariantChange && (
        <select
          className={styles.variantSelect}
          value={variantValue ?? variantFamily.default}
          onChange={(e) => onVariantChange(e.target.value)}
          aria-label={`Варіант для ${fileName}`}
        >
          {variantFamily.choices.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      )}
      <Button
        variant="ghost"
        size="sm"
        iconOnly
        aria-label="Видалити файл"
        onClick={onRemove}
        className={styles.removeBtn}
      >
        <X size={14} aria-hidden="true" />
      </Button>
    </div>
  );
};
