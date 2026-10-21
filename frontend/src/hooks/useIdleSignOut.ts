import { useEffect, useRef } from 'react';

const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const CHECK_INTERVAL_MS = 30 * 1000;
const ACTIVITY_EVENTS = ['pointerdown', 'pointermove', 'keydown', 'scroll', 'touchstart'] as const;

// Signs the user out after 30 min without input (NFR: session timeout).
// Clerk's own inactivity timeout is a paid feature, so the frontend enforces it.
export function useIdleSignOut(enabled: boolean, onIdle: () => void, timeoutMs = IDLE_TIMEOUT_MS): void {
  const onIdleRef = useRef(onIdle);
  useEffect(() => {
    onIdleRef.current = onIdle;
  });

  useEffect(() => {
    if (!enabled) return;
    let lastActivity = Date.now();
    const markActive = () => {
      lastActivity = Date.now();
    };
    // Compare timestamps instead of one long timer: timers pause in background tabs and during sleep
    const check = () => {
      if (Date.now() - lastActivity >= timeoutMs) onIdleRef.current();
    };

    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, markActive, { passive: true }));
    document.addEventListener('visibilitychange', check);
    const interval = setInterval(check, CHECK_INTERVAL_MS);
    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, markActive));
      document.removeEventListener('visibilitychange', check);
      clearInterval(interval);
    };
  }, [enabled, timeoutMs]);
}
