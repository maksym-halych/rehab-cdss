import type { DetectFilesResponse, Job, ConfigResponse } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
// Set by AuthGate: the Clerk session token getter and the handler for 401/403 responses
let getToken: () => Promise<string | null> = async () => null;
let onAuthError: (status: 401 | 403) => void = () => {};

export function configureAuth(options: {
  getToken: () => Promise<string | null>;
  onAuthError: (status: 401 | 403) => void;
}): void {
  getToken = options.getToken;
  onAuthError = options.onAuthError;
}

async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  // Clerk tokens live 60 s; getToken returns a cached token or refreshes it
  const token = await getToken();
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401 || res.status === 403) onAuthError(res.status);
  return res;
}

export async function detectFiles(files: File[], manualPersonName?: string): Promise<DetectFilesResponse> {
  const fd = new FormData();
  files.forEach(f => fd.append('files', f, f.name));
  if (manualPersonName) fd.append('manual_person_name', manualPersonName);
  const res = await apiFetch(`${BASE}/api/v1/files/detect`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitJob(params: {
  files: File[];
  age: number | null;
  gender: string | null;
  activityLevel: string;
  manualPersonName: string;
  selectedPersonKey: string;
  patientCode: string;
  pushupTypeOverrides: Record<string, string>;
  manualTestOverrides: Record<string, string>;
}): Promise<{ job_id: string; status: string; status_url: string; created_at: string }> {
  const fd = new FormData();
  params.files.forEach(f => fd.append('files', f, f.name));
  if (params.age !== null) fd.append('age', String(params.age));
  if (params.gender) fd.append('gender', params.gender);
  fd.append('activity_level', params.activityLevel);
  fd.append('manual_person_name', params.manualPersonName);
  fd.append('selected_person_key', params.selectedPersonKey);
  fd.append('patient_code', params.patientCode);
  fd.append('pushup_type_overrides', JSON.stringify(params.pushupTypeOverrides));
  fd.append('manual_test_overrides', JSON.stringify(params.manualTestOverrides));
  const res = await apiFetch(`${BASE}/api/v1/jobs`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitJsonJob(params: {
  file: File;
  age: number | null;
  gender: string | null;
  activityLevel: string;
  manualPersonName: string;
  patientCode: string;
}): Promise<{ job_id: string; status: string; status_url: string; created_at: string }> {
  const fd = new FormData();
  fd.append('file', params.file, params.file.name);
  if (params.age !== null) fd.append('age', String(params.age));
  if (params.gender) fd.append('gender', params.gender);
  fd.append('activity_level', params.activityLevel);
  fd.append('manual_person_name', params.manualPersonName);
  fd.append('patient_code', params.patientCode);
  const res = await apiFetch(`${BASE}/api/v1/jobs/from-json`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await apiFetch(`${BASE}/api/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getConfig(): Promise<ConfigResponse> {
  const res = await apiFetch(`${BASE}/api/v1/config/test-types`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// A plain link cannot send the Bearer token, so the file is fetched and saved as a blob
async function downloadFile(url: string, fileName: string): Promise<void> {
  try {
    const res = await apiFetch(url);
    if (!res.ok) throw new Error('Download failed');
    const objectUrl = URL.createObjectURL(await res.blob());
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(objectUrl);
  } catch {
    window.alert('Не вдалося завантажити звіт');
  }
}

export function downloadDocxReport(jobId: string): Promise<void> {
  return downloadFile(`${BASE}/api/v1/reports/${jobId}/docx`, `report_${jobId.slice(0, 8)}.docx`);
}

export async function getRehabReport(jobId: string): Promise<string> {
  const res = await apiFetch(`${BASE}/api/v1/reports/${jobId}/rehab-report`);
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}

export function downloadRehabDocx(jobId: string): Promise<void> {
  return downloadFile(
    `${BASE}/api/v1/reports/${jobId}/rehab-report/docx`,
    `rehabilitation_report_${jobId.slice(0, 8)}.docx`,
  );
}
