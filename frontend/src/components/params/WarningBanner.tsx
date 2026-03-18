import React from 'react';
import { AlertTriangle } from 'lucide-react';
import styles from './WarningBanner.module.css';

interface WarningBannerProps {
  messages: string[];
}

export const WarningBanner: React.FC<WarningBannerProps> = ({ messages }) => {
  if (messages.length === 0) return null;

  return (
    <div className={styles.banner} role="alert">
      <AlertTriangle size={16} className={styles.icon} aria-hidden="true" />
      <div className={styles.content}>
        <p className={styles.title}>Попередження</p>
        {messages.length === 1 ? (
          <p className={styles.message}>{messages[0]}</p>
        ) : (
          <ul className={styles.list}>
            {messages.map((msg, i) => (
              <li key={i}>{msg}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
