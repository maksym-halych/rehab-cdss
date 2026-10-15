import { create } from 'zustand';
import type { UploadedFile, PatientParams } from '../api/types';

interface RehabStore {
  files: UploadedFile[];
  addFiles: (files: UploadedFile[]) => void;
  removeFile: (clientId: string) => void;
  clearFiles: () => void;

  pushupTypeOverrides: Record<string, string>;
  manualTestOverrides: Record<string, string>;
  setPushupVariant: (name: string, variant: string) => void;
  setManualTestOverride: (name: string, testType: string) => void;

  selectedPersonKey: string;
  setSelectedPersonKey: (key: string) => void;

  patientParams: PatientParams;
  setPatientParam: <K extends keyof PatientParams>(key: K, value: PatientParams[K]) => void;

  currentJobId: string | null;
  setCurrentJobId: (id: string | null) => void;
  clearJob: () => void;
}

export const useRehabStore = create<RehabStore>((set) => ({
  files: [],
  addFiles: (incoming) => set((s) => ({ files: [...s.files, ...incoming] })),
  removeFile: (clientId) => set((s) => ({ files: s.files.filter(f => f.clientId !== clientId) })),
  clearFiles: () => set({ files: [], pushupTypeOverrides: {}, manualTestOverrides: {} }),

  pushupTypeOverrides: {},
  manualTestOverrides: {},
  setPushupVariant: (name, variant) => set((s) => ({ pushupTypeOverrides: { ...s.pushupTypeOverrides, [name]: variant } })),
  setManualTestOverride: (name, testType) => set((s) => ({ manualTestOverrides: { ...s.manualTestOverrides, [name]: testType } })),

  selectedPersonKey: '',
  setSelectedPersonKey: (key) => set({ selectedPersonKey: key }),

  patientParams: { age: null, gender: null, personName: '', patientCode: '', activityLevel: 'recreational' },
  setPatientParam: (key, value) => set((s) => ({ patientParams: { ...s.patientParams, [key]: value } })),

  currentJobId: null,
  setCurrentJobId: (id) => set({ currentJobId: id }),
  clearJob: () => set({ currentJobId: null }),
}));
