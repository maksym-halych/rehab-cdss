import type { Module1JsonPreview } from './types';

export function isJsonFile(file: File): boolean {
  return file.name.toLowerCase().endsWith('.json');
}

type Row = Record<string, unknown>;

function rowOutOfNorm(row: Row): boolean {
  const norm = row.norm;
  const values = ['value', 'left', 'right']
    .map((k) => row[k])
    .filter((v): v is number => typeof v === 'number');
  if (Array.isArray(norm) && norm.length > 0) {
    const lo = norm[0] as number;
    const hi = norm[norm.length - 1] as number;
    if (values.some((v) => v < lo || v > hi)) return true;
  }
  const asym = row.asymmetry_percent;
  const asymMax = row.asymmetry_norm_max;
  return typeof asym === 'number' && typeof asymMax === 'number' && asym > asymMax;
}

/** Parse and validate a Module 1 JSON export. Throws an Error with a user-facing message. */
export async function parseModule1Json(file: File): Promise<Module1JsonPreview> {
  let data: unknown;
  try {
    data = JSON.parse(await file.text());
  } catch {
    throw new Error(`«${file.name}» не є коректним JSON-файлом`);
  }
  if (!data || typeof data !== 'object' || !Array.isArray((data as Row).test_results)) {
    throw new Error(`«${file.name}» не схожий на експорт Модуля 1 (немає поля test_results)`);
  }
  const d = data as Row;
  const testResults = d.test_results as Row[];

  const tests = testResults.map((tr) => {
    const tables = ((tr.results as Row | undefined)?.tables as Row[] | undefined) ?? [];
    const rows = tables.flatMap((t) => (t.rows as Row[] | undefined) ?? []);
    return {
      name: String(tr.test_name ?? 'Невідомий тест'),
      rows: rows.length,
      outOfNorm: rows.filter(rowOutOfNorm).length,
      hasText: Boolean(tr.interpretation),
    };
  });

  return {
    fileName: file.name,
    patientInfo: (d.patient_info as Module1JsonPreview['patientInfo']) ?? {},
    synthetic: d.synthetic === true,
    scenario: typeof d.scenario === 'string' ? d.scenario : null,
    tests,
  };
}
