'use client';

// React hook over the shared telemetry stream.
//
// Usage:
//   const race = useStream((s) => s?.race);
//   const phase = useStream((s) => s?.phase ?? 'idle');
//
// `selector` runs on every snapshot; the component re-renders only when the
// selected slice changes by reference equality. Selectors that build fresh
// objects/arrays on every call will cause re-renders every tick — keep them
// simple ("pick a field") or memoize upstream.

import { useSyncExternalStore } from 'react';
import { subscribe, getSnapshot } from './stream';
import type { SimSnapshot } from './api';

export function useStream<T>(selector: (s: SimSnapshot | null) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(getSnapshot()),
    () => selector(null),
  );
}

// Convenience hooks for the most common slices.
export const usePhase = () => useStream((s) => s?.phase ?? 'idle');
export const useRace = () => useStream((s) => s?.race ?? null);
export const useHand = () => useStream((s) => s?.hand ?? null);
export const useTraining = () => useStream((s) => s?.training ?? null);
export const useCapture = () => useStream((s) => s?.capture ?? null);
