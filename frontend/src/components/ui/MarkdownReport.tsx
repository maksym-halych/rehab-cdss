import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from './MarkdownReport.module.css';

interface MarkdownReportProps {
  markdown: string;
}

export const MarkdownReport: React.FC<MarkdownReportProps> = ({ markdown }) => {
  return (
    <article className={styles.report}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
    </article>
  );
};
