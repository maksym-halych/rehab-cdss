import React from 'react';
import styles from './RehabLayout.module.css';

interface RehabLayoutProps {
  header: React.ReactNode;
  tabNav: React.ReactNode;
  children: React.ReactNode;
}

export const RehabLayout: React.FC<RehabLayoutProps> = ({ header, tabNav, children }) => {
  return (
    <div className={styles.layout}>
      <header className={styles.header}>{header}</header>
      <div className={styles.tabBarWrap}>
        <div className={styles.tabBarInner}>{tabNav}</div>
      </div>
      <main className={styles.main}>{children}</main>
    </div>
  );
};
