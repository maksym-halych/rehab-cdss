import React from 'react';
import { ChevronDown } from 'lucide-react';
import styles from './Accordion.module.css';

interface AccordionProps {
  open: boolean;
  onToggle: () => void;
  summary: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  summaryClassName?: string;
}

export const Accordion: React.FC<AccordionProps> = ({
  open,
  onToggle,
  summary,
  children,
  className,
  summaryClassName,
}) => {
  return (
    <div className={[styles.accordion, className ?? ''].filter(Boolean).join(' ')}>
      <button
        type="button"
        className={[styles.summary, summaryClassName ?? ''].filter(Boolean).join(' ')}
        onClick={onToggle}
        aria-expanded={open}
      >
        <span className={styles.summaryContent}>{summary}</span>
        <ChevronDown
          size={16}
          className={[styles.chevron, open ? styles.chevronOpen : ''].filter(Boolean).join(' ')}
          aria-hidden="true"
        />
      </button>
      <div className={[styles.content, open ? styles.contentOpen : ''].filter(Boolean).join(' ')}>
        <div className={styles.contentInner}>{children}</div>
      </div>
    </div>
  );
};
