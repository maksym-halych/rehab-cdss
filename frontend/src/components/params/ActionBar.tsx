import React from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '../ui/Button';
import styles from './ActionBar.module.css';

interface ActionBarProps {
  onProcess: () => void;
  isProcessing: boolean;
  hasFiles: boolean;
}

export const ActionBar: React.FC<ActionBarProps> = ({
  onProcess,
  isProcessing,
  hasFiles,
}) => {
  return (
    <div className={styles.actionBar}>
      <Button
        variant="primary"
        size="lg"
        fullWidth
        onClick={onProcess}
        disabled={!hasFiles || isProcessing}
        loading={isProcessing}
        type="button"
      >
        {isProcessing ? (
          <>
            <Loader2 size={16} className={styles.spinner} aria-hidden="true" />
            Обробка…
          </>
        ) : (
          'Проаналізувати'
        )}
      </Button>
    </div>
  );
};
