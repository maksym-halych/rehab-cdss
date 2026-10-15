import React from 'react';
import { FileJson, X } from 'lucide-react';
import { Button } from '../ui/Button';
import type { Module1JsonPreview } from '../../api/types';
import styles from './JsonPreview.module.css';

interface JsonPreviewProps {
  preview: Module1JsonPreview;
  onRemove: () => void;
}

export const JsonPreview: React.FC<JsonPreviewProps> = ({ preview, onRemove }) => {
  const { patientInfo, tests } = preview;
  const totalOut = tests.reduce((n, t) => n + t.outOfNorm, 0);

  return (
    <div className={styles.container}>
      <div className={styles.fileRow}>
        <FileJson size={16} className={styles.fileIcon} aria-hidden="true" />
        <span className={styles.fileName} title={preview.fileName}>
          {preview.fileName}
        </span>
        {preview.synthetic && <span className={styles.badge}>демо-дані</span>}
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

      <p className={styles.note}>
        Експорт Модуля 1 — розпізнавання файлів пропущено, дані одразу передаються в Модуль 2.
        {preview.scenario && <> Сценарій: <code>{preview.scenario}</code>.</>}
      </p>

      <dl className={styles.patient}>
        <dt>Пацієнт</dt>
        <dd>{patientInfo.name || '—'}</dd>
        <dt>Код</dt>
        <dd>{patientInfo.patient_code || '—'}</dd>
        <dt>Вік / стать</dt>
        <dd>
          {patientInfo.age ?? '—'} / {patientInfo.gender || '—'}
        </dd>
      </dl>

      <div className={styles.testsHeader}>
        <span>Тести ({tests.length})</span>
        <span>{totalOut} поза нормою</span>
      </div>
      <ul className={styles.tests}>
        {tests.map((t, i) => (
          <li key={`${t.name}-${i}`} className={styles.test}>
            <span className={styles.testName}>{t.name}</span>
            {t.rows > 0 ? (
              <span className={t.outOfNorm > 0 ? styles.countBad : styles.countOk}>
                {t.outOfNorm} / {t.rows}
              </span>
            ) : (
              <span className={styles.countText}>{t.hasText ? 'висновок' : '—'}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};
