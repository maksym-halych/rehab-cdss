import React from 'react';
import { FormField } from '../ui/FormField';
import { RadioGroup } from '../ui/RadioGroup';
import type { PatientParams, ConfigResponse } from '../../api/types';
import styles from './PatientParamsForm.module.css';

interface PatientParamsFormProps {
  params: PatientParams;
  onParamChange: <K extends keyof PatientParams>(key: K, value: PatientParams[K]) => void;
  config: ConfigResponse | null;
}

const DEFAULT_ACTIVITY_LEVELS = [
  { value: 'elite', label: 'Елітний' },
  { value: 'recreational', label: 'Рекреаційний' },
  { value: 'low', label: 'Низький' },
];

const DEFAULT_GENDER_CHOICES = ['Чоловіча', 'Жіноча'];

export const PatientParamsForm: React.FC<PatientParamsFormProps> = ({
  params,
  onParamChange,
  config,
}) => {
  const activityLevels = config?.activity_levels ?? DEFAULT_ACTIVITY_LEVELS;
  const genderChoices = config?.gender_choices ?? DEFAULT_GENDER_CHOICES;

  return (
    <div className={styles.form}>
      <FormField label="ПІБ пацієнта" htmlFor="patient-name">
        <input
          id="patient-name"
          type="text"
          value={params.personName}
          placeholder="Прізвище Ім'я"
          onChange={(e) => onParamChange('personName', e.target.value)}
          autoComplete="off"
        />
      </FormField>

      <FormField label="Код пацієнта" htmlFor="patient-code">
        <input
          id="patient-code"
          type="text"
          value={params.patientCode}
          placeholder="Напр., 202401"
          onChange={(e) => onParamChange('patientCode', e.target.value)}
          autoComplete="off"
        />
      </FormField>

      <FormField label="Вік" htmlFor="patient-age">
        <input
          id="patient-age"
          type="number"
          min={1}
          max={120}
          value={params.age ?? ''}
          placeholder="Роки"
          onChange={(e) => {
            const val = e.target.value;
            onParamChange('age', val === '' ? null : parseInt(val, 10));
          }}
        />
      </FormField>

      <RadioGroup
        name="gender"
        label="Стать"
        options={genderChoices.map((g) => ({ value: g, label: g }))}
        value={params.gender}
        onChange={(v) => onParamChange('gender', v)}
      />

      <RadioGroup
        name="activityLevel"
        label="Рівень активності"
        options={activityLevels.map((a) => ({ value: a.value, label: a.label }))}
        value={params.activityLevel}
        onChange={(v) =>
          onParamChange('activityLevel', v as PatientParams['activityLevel'])
        }
      />
    </div>
  );
};
