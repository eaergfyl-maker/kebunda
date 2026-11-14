import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/services/apiClient";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  /** True while a newer request is in flight but older data is still shown. */
  refreshing: boolean;
  error: ApiError | null;
}

const cache = new Map<string, unknown>();

/**
 * Run an async call whenever `key` changes.
 *  - key = null skips the call.
 *  - Results are cached by key for the session, so switching tabs or farms is instant.
 *  - The previous result stays on screen while the next one loads (no flicker on slider moves).
 *  - Stale responses are discarded and the in-flight request is aborted.
 */
export function useAsync<T>(key: string | null, fn: (signal: AbortSignal) => Promise<T>, opts: { cache?: boolean; debounceMs?: number } = {}): AsyncState<T> {
  const useCache = opts.cache ?? true;
  const [state, setState] = useState<AsyncState<T>>(() => ({
    data: key && useCache && cache.has(key) ? (cache.get(key) as T) : null,
    loading: key !== null && !(useCache && cache.has(key)),
    refreshing: false,
    error: null,
  }));
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (key === null) {
      setState({ data: null, loading: false, refreshing: false, error: null });
      return;
    }
    if (useCache && cache.has(key)) {
      setState({ data: cache.get(key) as T, loading: false, refreshing: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((s) => ({ data: s.data, loading: s.data === null, refreshing: s.data !== null, error: null }));
    const timer = window.setTimeout(() => {
      fnRef.current(controller.signal)
        .then((data) => {
          if (controller.signal.aborted) return;
          if (useCache) cache.set(key, data);
          setState({ data, loading: false, refreshing: false, error: null });
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          const error = err instanceof ApiError ? err : new ApiError(0, "unexpected", err instanceof Error ? err.message : "Something went wrong.");
          setState((s) => ({ data: s.data, loading: false, refreshing: false, error }));
        });
    }, opts.debounceMs ?? 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [key, useCache, opts.debounceMs]);

  return state;
}

/** Seed the cache (used after creating a custom field so its overview is not fetched twice). */
export function primeCache<T>(key: string, data: T): void {
  cache.set(key, data);
}
