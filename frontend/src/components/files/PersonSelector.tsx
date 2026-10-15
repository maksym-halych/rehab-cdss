import React from 'react';
import type { Person } from '../../api/types';
import styles from './PersonSelector.module.css';

interface PersonSelectorProps {
  people: Person[];
  selectedKey: string;
  onSelect: (key: string) => void;
}

export const PersonSelector: React.FC<PersonSelectorProps> = ({
  people,
  selectedKey,
  onSelect,
}) => {
  if (people.length <= 1) return null;

  return (
    <div className={styles.container}>
      <label className={styles.label} htmlFor="person-select">
        Обраний пацієнт:
      </label>
      <select
        id="person-select"
        className={styles.select}
        value={selectedKey}
        onChange={(e) => onSelect(e.target.value)}
      >
        {people.map((p) => (
          <option key={p.key} value={p.key}>
            {p.display}
          </option>
        ))}
      </select>
    </div>
  );
};
