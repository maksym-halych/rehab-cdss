import React from 'react';
import styles from './TabNav.module.css';

export interface Tab {
  key: string;
  label: string;
  badge?: 'pulse' | 'dot' | null;
}

interface TabNavProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (key: string) => void;
}

export const TabNav: React.FC<TabNavProps> = ({ tabs, activeTab, onTabChange }) => {
  return (
    <nav className={styles.tabNav} role="tablist" aria-label="Навігація розділами">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          role="tab"
          aria-selected={activeTab === tab.key}
          className={[styles.tab, activeTab === tab.key ? styles.tabActive : '']
            .filter(Boolean)
            .join(' ')}
          onClick={() => onTabChange(tab.key)}
          type="button"
        >
          {tab.label}
          {tab.badge === 'pulse' && <span className={styles.pulseBadge} aria-label="В процесi" />}
          {tab.badge === 'dot' && <span className={styles.dotBadge} />}
        </button>
      ))}
    </nav>
  );
};
