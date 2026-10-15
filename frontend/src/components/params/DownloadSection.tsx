import React from 'react';
import { Download } from 'lucide-react';
import { Button } from '../ui/Button';
import { downloadDocxReport } from '../../api/client';
import styles from './DownloadSection.module.css';

interface DownloadSectionProps {
  jobId: string;
}

export const DownloadSection: React.FC<DownloadSectionProps> = ({ jobId }) => {
  const handleDownload = () => {
    downloadDocxReport(jobId);
  };

  return (
    <div className={styles.section}>
      <p className={styles.label}>Звіт готовий до завантаження</p>
      <Button
        variant="primary"
        size="md"
        fullWidth
        onClick={handleDownload}
        type="button"
      >
        <Download size={16} aria-hidden="true" />
        Завантажити звіт (DOCX)
      </Button>
    </div>
  );
};
