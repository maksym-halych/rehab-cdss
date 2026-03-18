import React from 'react';
import { FileText, X } from 'lucide-react';
import { Button } from '../ui/Button';
import styles from './UnknownFileRow.module.css';

interface UnknownFileRowProps {
  fileName: string;
  onRemove: () => void;
}

export const UnknownFileRow: React.FC<UnknownFileRowProps> = ({ fileName, onRemove }) => {
  return (
    <div className={styles.row}>
      <FileText size={14} className={styles.fileIcon} aria-hidden="true" />
      <span className={styles.fileName} title={fileName}>
        {fileName}
      </span>
      <span className={styles.badge}>невідомий</span>
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
