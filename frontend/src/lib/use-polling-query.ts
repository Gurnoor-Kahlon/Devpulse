"use client";

import { useRef, useSyncExternalStore } from "react";
import { useQuery, type QueryKey } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

function subscribe(callback: () => void) {
  document.addEventListener("visibilitychange", callback);
  return () => document.removeEventListener("visibilitychange", callback);
}
const visible = () => document.visibilityState === "visible";
const serverVisible = () => false;

// Stored monitoring reads only: no probe execution or mutation uses this hook.
export function usePollingQuery<T>(
  queryKey: QueryKey,
  fetcher: (signal: AbortSignal) => Promise<T>,
) {
  const isVisible = useSyncExternalStore(subscribe, visible, serverVisible);
  const identity = JSON.stringify(queryKey);
  const failures = useRef(new Map<string, number>());
  return useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      try {
        const data = await fetcher(signal);
        failures.current.set(identity, 0);
        return data;
      } catch (error) {
        if (!signal.aborted)
          failures.current.set(
            identity,
            Math.min((failures.current.get(identity) ?? 0) + 1, 3),
          );
        throw error;
      }
    },
    enabled: isVisible,
    retry: false,
    staleTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchIntervalInBackground: false,
    refetchInterval: (query) =>
      !isVisible ||
      (query.state.error instanceof ApiError &&
        query.state.error.status === 401)
        ? false
        : Math.min(
            15_000 * 2 ** (failures.current.get(identity) ?? 0),
            120_000,
          ),
  });
}
