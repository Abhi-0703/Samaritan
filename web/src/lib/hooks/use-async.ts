"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  /** True until the first result (or error) for the current key arrives and there is nothing to show yet. */
  loading: boolean;
  /** True while a refetch is running and earlier data is still on screen. */
  refreshing: boolean;
  /** Refetch and show the refreshing state. */
  reload: () => void;
  /** Refetch quietly, for polling: no refreshing state, so nothing flickers. */
  poll: () => void;
  /** Replace the cached data locally, for example after a confirmed mutation. */
  setData: (updater: (prev: T) => T) => void;
}

const toError = (e: unknown): Error => (e instanceof Error ? e : new Error(String(e)));

/**
 * Fetches on mount and whenever `key` changes. Earlier data stays visible while a new request runs,
 * so polling and filter changes do not flash empty states. State is only set from promise callbacks.
 */
export function useAsync<T>(fetcher: () => Promise<T>, key: string): AsyncState<T> {
  const [version, setVersion] = useState(0);
  const [tick, setTick] = useState(0);
  const [result, setResult] = useState<{ key: string; data?: T; error?: Error } | null>(null);
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const fullKey = `${key}#${version}`;
  useEffect(() => {
    let cancelled = false;
    fetcherRef.current().then(
      (data) => {
        if (!cancelled) setResult({ key: fullKey, data });
      },
      (error) => {
        if (!cancelled) setResult((prev) => ({ key: fullKey, data: prev?.data, error: toError(error) }));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [fullKey, tick]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const poll = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((updater: (prev: T) => T) => {
    setResult((prev) => (prev && prev.data !== undefined ? { ...prev, data: updater(prev.data) } : prev));
  }, []);

  const settled = result?.key === fullKey;
  return {
    data: result?.data,
    error: settled ? result?.error : undefined,
    loading: !settled && result?.data === undefined && !result?.error,
    refreshing: !settled && (result?.data !== undefined || !!result?.error),
    reload,
    poll,
    setData,
  };
}
