import { useState, useEffect } from 'react';
import { getConfig } from '../api/client';
import type { ConfigResponse } from '../api/types';

interface UseConfigResult {
  config: ConfigResponse | null;
  isLoading: boolean;
}

export function useConfig(): UseConfigResult {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((data) => {
        if (!cancelled) setConfig(data);
      })
      .catch(() => {
        // config is optional; app works without it
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  return { config, isLoading };
}
