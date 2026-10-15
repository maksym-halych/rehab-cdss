import React from 'react';
import { Check, X, Loader2 } from 'lucide-react';
import type { Module2Status } from '../../api/types';
import styles from './Module2Timeline.module.css';

// query_rewriter (index 5) is conditional — only runs when grader rejects all protocols.
// We track its backend index so we can detect whether it was skipped.
const QUERY_REWRITER_INDEX = 5;

const STEPS = [
  { key: 'filter', label: 'Фiльтрацiя даних', description: 'Аналiзуємо результати тестiв...', backendIndex: 0 },
  { key: 'summarize', label: 'Клiнiчне резюме', description: 'Формуємо клiнiчне резюме...', backendIndex: 1 },
  { key: 'query_generator', label: 'Генерацiя запитiв', description: 'Генеруємо пошуковi запити...', backendIndex: 2 },
  { key: 'protocol_retriever', label: 'Пошук протоколiв', description: 'Шукаємо релевантнi протоколи реабiлiтацiї...', backendIndex: 3 },
  { key: 'grader', label: 'Оцiнка релевантностi', description: 'Оцiнюємо вiдповiднiсть протоколiв...', backendIndex: 4 },
  { key: 'query_rewriter', label: 'Перезапис запитiв', description: 'Уточнюємо пошуковi запити...', backendIndex: 5 },
  { key: 'reasoner', label: 'Планування лiкування', description: 'Складаємо план лiкування...', backendIndex: 6 },
  { key: 'exercise_mapper', label: 'Зiставлення вправ', description: 'Зiставляємо вправи з базою знань...', backendIndex: 7 },
  { key: 'report_formatter', label: 'Формування звiту', description: 'Формуємо фiнальний звiт...', backendIndex: 8 },
] as const;

interface Module2TimelineProps {
  stepIndex: number;
  status: Module2Status;
  error: string | null;
}

export const Module2Timeline: React.FC<Module2TimelineProps> = ({
  stepIndex,
  status,
  error,
}) => {
  // Hide query_rewriter step if it was skipped (stepIndex jumped past it without visiting)
  const queryRewriterRan = stepIndex === QUERY_REWRITER_INDEX ||
    (status === 'failed' && stepIndex === QUERY_REWRITER_INDEX);
  const displaySteps = STEPS.filter(
    step => step.key !== 'query_rewriter' || queryRewriterRan
  );

  const getStepState = (backendIdx: number): 'completed' | 'active' | 'error' | 'pending' => {
    if (status === 'failed') {
      if (backendIdx < stepIndex) return 'completed';
      if (backendIdx === stepIndex) return 'error';
      return 'pending';
    }
    if (status === 'completed') return 'completed';
    if (backendIdx < stepIndex) return 'completed';
    if (backendIdx === stepIndex) return 'active';
    return 'pending';
  };

  return (
    <div className={styles.timeline} role="list" aria-label="Прогрес генерацiї рекомендацiй">
      {displaySteps.map((step, index) => {
        const state = getStepState(step.backendIndex);
        return (
          <div
            key={step.key}
            className={[styles.step, styles[`step--${state}`]].join(' ')}
            role="listitem"
            aria-current={state === 'active' ? 'step' : undefined}
          >
            <div className={styles.indicator}>
              <div className={styles.dot}>
                {state === 'completed' && <Check size={14} aria-hidden="true" />}
                {state === 'error' && <X size={14} aria-hidden="true" />}
                {state === 'active' && <Loader2 size={14} className={styles.spinner} aria-hidden="true" />}
              </div>
              {index < displaySteps.length - 1 && <div className={styles.line} />}
            </div>
            <div className={styles.content}>
              <span className={styles.label}>{step.label}</span>
              {state === 'active' && (
                <span className={styles.description}>{step.description}</span>
              )}
              {state === 'error' && error && (
                <span className={styles.errorMessage}>{error}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
