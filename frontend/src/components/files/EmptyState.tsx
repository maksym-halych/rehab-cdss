import React from 'react';
import { Upload } from 'lucide-react';
import styles from './EmptyState.module.css';

export const EmptyState: React.FC = () => {
  return (
    <div className={styles.container}>
      <div className={styles.iconWrap}>
        <Upload size={32} aria-hidden="true" />
      </div>
      <p className={styles.title}>Файли не додано</p>
      <p className={styles.hint}>
        Перетягніть файли сюди або скористайтеся кнопкою «Додати файли»
      </p>
    </div>
  );
};
