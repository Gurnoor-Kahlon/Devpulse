"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { getMonitor } from "@/lib/api/monitors";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { MonitorForm } from "./monitor-form";
import { MonitorHeading } from "./monitor-heading";

export function MonitorEditor({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["monitor", id],
    queryFn: ({ signal }) => getMonitor(id, signal),
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  return (
    <>
      <MonitorHeading title="Edit monitor">
        <Link href="/monitors" className="button button--secondary">
          Back to monitors
        </Link>
      </MonitorHeading>
      {query.isPending ? (
        <LoadingState label="Loading monitor settings" />
      ) : query.error instanceof ApiError && query.error.status === 404 ? (
        <p role="alert" className="text-muted">
          This monitor is unavailable. It may have been archived.
        </p>
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Could not reload settings. Your edits are preserved. Try reloading
              again.
            </p>
          )}
          <MonitorForm
            key={query.dataUpdatedAt}
            monitor={query.data}
            onReload={() => void query.refetch()}
            reloading={query.isFetching}
          />
        </>
      )}
    </>
  );
}
