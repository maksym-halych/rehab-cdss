import React, { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import { Button } from '../ui/Button';
import type { UploadedFile } from '../../api/types';
import styles from './FileUploadTrigger.module.css';

interface FileUploadTriggerProps {
  onFilesAdded: (files: UploadedFile[]) => void;
  variant?: 'default' | 'inline';
}

export const FileUploadTrigger: React.FC<FileUploadTriggerProps> = ({
  onFilesAdded,
  variant = 'default',
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const processFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const uploaded: UploadedFile[] = Array.from(fileList).map((f) => ({
      clientId: crypto.randomUUID(),
      file: f,
      originalName: f.name,
    }));
    onFilesAdded(uploaded);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    processFiles(e.dataTransfer.files);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(e.target.files);
    e.target.value = '';
  };

  const button = (
    <Button
      variant="secondary"
      size={variant === 'inline' ? 'sm' : 'md'}
      fullWidth={variant === 'default'}
      onClick={() => inputRef.current?.click()}
      type="button"
    >
      <Upload size={variant === 'inline' ? 14 : 16} aria-hidden="true" />
      Додати файли
    </Button>
  );

  if (variant === 'inline') {
    return (
      <div
        className={styles.inlineWrap}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        role="region"
        aria-label="Додати файли"
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          className={styles.hiddenInput}
          accept=".pdf,.csv"
          onChange={handleChange}
          aria-label="Оберіть файли для завантаження"
          tabIndex={-1}
        />
        {button}
      </div>
    );
  }

  return (
    <div
      className={[styles.dropZone, isDragging ? styles.dropZoneDragging : '']
        .filter(Boolean)
        .join(' ')}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      role="region"
      aria-label="Зона завантаження файлів"
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        className={styles.hiddenInput}
        accept=".pdf,.csv"
        onChange={handleChange}
        aria-label="Оберіть файли для завантаження"
        tabIndex={-1}
      />
      {button}
      <p className={styles.hint}>або перетягніть файли сюди</p>
    </div>
  );
};
