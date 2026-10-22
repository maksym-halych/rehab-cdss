import { useState, useEffect, useRef } from 'react';
import { detectFiles } from '../api/client';
import type { DetectFilesResponse, UploadedFile } from '../api/types';

interface UseDetectFilesResult {
  detectedPeople: DetectFilesResponse['detected_people'];
  fileGroups: DetectFilesResponse['file_groups'] | null;
  fileAssignments: Record<string, string>;
  isLoading: boolean;
  error: string | null;
}

const emptyGroups: DetectFilesResponse['file_groups'] = {
  pdf: {
    dental: [],
    postural: [],
    baropodometry: [],
    dynamic_baropodometry: [],
    spine3d: [],
  },
  csv: {
    cervical_goniometry: [],
    leg_dynamometry: [],
    leg_goniometry: [],
    arm_goniometry: [],
    arm_dynamometry: [],
    single_leg_balance: [],
    single_leg_landing: [],
    mccall_hamstrings: [],
    shoulder_test: [],
    push_up: [],
    handstand_push_up: [],
    counter_movement_jump: [],
    single_leg_counter_movement_jump: [],
    drop_jump: [],
    imtp: [],
    bipodal_stance: [],
    bipodal_landing: [],
    skipping: [],
    squats_advanced_analysis: [],
  },
  unknown: [],
};

export function useDetectFiles(files: UploadedFile[], personName: string): UseDetectFilesResult {
  const [detectedPeople, setDetectedPeople] = useState<DetectFilesResponse['detected_people']>([]);
  const [fileGroups, setFileGroups] = useState<DetectFilesResponse['file_groups'] | null>(null);
  const [fileAssignments, setFileAssignments] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const prevFilesRef = useRef<UploadedFile[]>(files);

  useEffect(() => {
    if (files.length === 0) {
      prevFilesRef.current = files;
      setDetectedPeople([]);
      setFileGroups(emptyGroups);
      setFileAssignments({});
      setError(null);
      setIsLoading(false);
      return;
    }

    const filesChanged = files !== prevFilesRef.current;
    prevFilesRef.current = files;

    // Skip if only personName changed and it matches a detected person (sync from selection)
    if (!filesChanged && detectedPeople.some((p) => p.display === personName)) {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = null;
      return;
    }

    if (timerRef.current) clearTimeout(timerRef.current);

    timerRef.current = setTimeout(async () => {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();

      setIsLoading(true);
      setError(null);
      try {
        const result = await detectFiles(files.map((f) => f.file), personName || undefined);
        setDetectedPeople(result.detected_people);
        setFileGroups(result.file_groups);
        setFileAssignments(result.file_assignments ?? {});
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // detectedPeople intentionally omitted: used for skip-check only; including would re-run on every detection complete
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, personName]);

  return { detectedPeople, fileGroups, fileAssignments, isLoading, error };
}
