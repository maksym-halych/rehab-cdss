export interface Person {
  key: string;
  display: string;
  surname: string | null;
  name: string | null;
  source: string | null;
}

export interface FileGroups {
  pdf: {
    dental: string[];
    postural: string[];
    baropodometry: string[];
    dynamic_baropodometry: string[];
    spine3d: string[];
  };
  csv: {
    cervical_goniometry: string[];
    leg_dynamometry: string[];
    leg_goniometry: string[];
    arm_goniometry: string[];
    arm_dynamometry: string[];
    single_leg_balance: string[];
    single_leg_landing: string[];
    mccall_hamstrings: string[];
    shoulder_test: string[];
    push_up: string[];
    handstand_push_up: string[];
    counter_movement_jump: string[];
    single_leg_counter_movement_jump: string[];
    drop_jump: string[];
    imtp: string[];
    bipodal_stance: string[];
    bipodal_landing: string[];
    skipping: string[];
    squats_advanced_analysis: string[];
  };
  unknown: string[];
}

export interface DetectFilesResponse {
  detected_people: Person[];
  file_groups: FileGroups;
  file_assignments: Record<string, string>;
  total_files: number;
  recognized_files: number;
  unrecognized_files: number;
}

export interface VariantChoice { label: string; value: string; }
export interface VariantFamily { choices: VariantChoice[]; default: string; }
export interface TestTypeInfo {
  key: string;
  label: string;
  accepts: Array<'pdf' | 'csv'>;
  category: 'pdf' | 'csv';
  variant_family: string | null;
}
export interface ConfigResponse {
  test_types: TestTypeInfo[];
  variant_families: Record<string, VariantFamily>;
  activity_levels: Array<{ value: string; label: string }>;
  gender_choices: string[];
}

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';
export type Module2Status = 'idle' | 'running' | 'completed' | 'failed';
export interface JobResult {
  report_json_url: string;
  report_docx_url: string;
  rehab_report_md_url: string | null;
  rehab_report_docx_url: string | null;
}
export interface Job {
  job_id: string;
  status: JobStatus;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  warnings: string[];
  result: JobResult | null;
  module2_status: Module2Status;
  module2_step: string | null;
  module2_step_index: number;
  module2_total_steps: number;
  module2_step_label: string | null;
  module2_error: string | null;
}

/** One row of "Мої аналізи": no names or patient IDs. */
export interface JobSummary {
  job_id: string;
  status: JobStatus;
  module2_status: Module2Status;
  created_at: string;
  completed_at: string | null;
  age: number | null;
  gender: string | null;
  activity_level: string | null;
}
export interface JobListResponse {
  jobs: JobSummary[];
  total: number;
}

export interface PatientParams {
  age: number | null;
  gender: string | null;
  personName: string;
  patientCode: string;
  activityLevel: 'elite' | 'recreational' | 'low';
}

/** Client-side summary of an uploaded Module 1 JSON export (demo mode). */
export interface Module1JsonPreview {
  fileName: string;
  patientInfo: {
    name?: string;
    patient_code?: string;
    age?: number;
    gender?: string;
    activity_level?: string;
  };
  synthetic: boolean;
  scenario: string | null;
  tests: Array<{ name: string; rows: number; outOfNorm: number; hasText: boolean }>;
}

export interface UploadedFile {
  clientId: string;
  file: File;
  originalName: string;
}
