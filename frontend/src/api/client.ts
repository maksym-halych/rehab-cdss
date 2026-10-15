import type { DetectFilesResponse, Job, ConfigResponse } from './types';

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY ?? '';

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { ...extra };
  if (API_KEY) h['X-API-Key'] = API_KEY;
  return h;
}

export async function detectFiles(files: File[], manualPersonName?: string): Promise<DetectFilesResponse> {
  const fd = new FormData();
  files.forEach(f => fd.append('files', f, f.name));
  if (manualPersonName) fd.append('manual_person_name', manualPersonName);
  const res = await fetch(`${BASE}/api/v1/files/detect`, { method: 'POST', headers: headers(), body: fd });
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
  const res = await fetch(`${BASE}/api/v1/jobs`, { method: 'POST', headers: headers(), body: fd });
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
  const res = await fetch(`${BASE}/api/v1/jobs/from-json`, { method: 'POST', headers: headers(), body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE}/api/v1/jobs/${jobId}`, { headers: headers() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${BASE}/api/v1/config/test-types`, { headers: headers() });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function getDocxUrl(jobId: string): string {
  return `${BASE}/api/v1/reports/${jobId}/docx`;
}

export async function downloadDocxReport(jobId: string): Promise<void> {
  const url = getDocxUrl(jobId);
  try {
    const res = await fetch(url, { headers: headers() });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = `report_${jobId.slice(0, 8)}.docx`;
    a.click();
    URL.revokeObjectURL(objectUrl);
  } catch {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

export async function getRehabReport(jobId: string): Promise<string> {
  const res = await fetch(`${BASE}/api/v1/reports/${jobId}/rehab-report`, { headers: headers() });
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}

export function getRehabDocxUrl(jobId: string): string {
  return `${BASE}/api/v1/reports/${jobId}/rehab-report/docx`;
}

export async function downloadRehabDocx(jobId: string): Promise<void> {
  const url = getRehabDocxUrl(jobId);
  try {
    const res = await fetch(url, { headers: headers() });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = `rehabilitation_report_${jobId.slice(0, 8)}.docx`;
    a.click();
    URL.revokeObjectURL(objectUrl);
  } catch {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}
