"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiError } from "@/lib/api/client";
import { getIncident, type IncidentEvidence } from "@/lib/api/incidents";

function Evidence({
  title,
  value,
}: {
  title: string;
  value: IncidentEvidence;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-border bg-surface p-5"
    >
      <h2 className="font-semibold">{title}</h2>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">Attempt</dt>
          <dd>{value.attempt_number}</dd>
        </div>
        <div>
          <dt className="text-muted">Outcome</dt>
          <dd>{value.outcome === "success" ? "Successful" : "Failed"}</dd>
        </div>
        <div>
          <dt className="text-muted">Started</dt>
          <dd>{new Date(value.started_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-muted">Finished</dt>
          <dd>{new Date(value.finished_at).toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-muted">Request</dt>
          <dd className="font-mono">
            {value.method} · expected HTTP {value.expected_status}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Response</dt>
          <dd className="font-mono">
            {value.http_status === null
              ? "No HTTP response"
              : `HTTP ${value.http_status}`}
          </dd>
        </div>
        <div>
          <dt className="text-muted">Duration</dt>
          <dd>{value.duration_ms.toFixed(1)} ms</dd>
        </div>
        <div>
          <dt className="text-muted">Configuration version</dt>
          <dd>{value.configuration_version}</dd>
        </div>
      </dl>
      {value.error_message && (
        <p className="mt-4 text-sm text-muted">{value.error_message}</p>
      )}
    </section>
  );
}

export function IncidentDetailView({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["incident", id],
    queryFn: ({ signal }) => getIncident(id, signal),
  });
  return (
    <>
      <Link href="/incidents" className="mb-6 inline-block text-sm underline">
        Back to incidents
      </Link>
      {query.isPending ? (
        <LoadingState label="Loading incident" />
      ) : !query.data ? (
        query.error instanceof ApiError && query.error.status === 404 ? (
          <EmptyState
            title="Incident unavailable"
            description="This incident could not be found in your account."
          />
        ) : (
          <ErrorState onRetry={() => void query.refetch()} />
        )
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="break-words text-3xl font-semibold">
                {query.data.monitor_name}
              </h1>
              <p
                className={`mt-2 text-sm ${query.data.status === "open" ? "text-danger" : "text-success"}`}
              >
                {query.data.status === "open"
                  ? "Open incident · recovery not observed"
                  : "Resolved incident"}
              </p>
            </div>
            <Button
              variant="secondary"
              loading={query.isFetching}
              onClick={() => void query.refetch()}
            >
              Refresh incident
            </Button>
          </div>
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Refresh failed. Showing the last loaded incident.
            </p>
          )}
          <dl className="mb-6 flex flex-wrap gap-x-8 gap-y-3 text-sm">
            <div>
              <dt className="text-muted">First failure</dt>
              <dd>{new Date(query.data.started_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-muted">Confirmed</dt>
              <dd>{new Date(query.data.confirmed_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-muted">Recovered</dt>
              <dd>
                {query.data.resolved_at
                  ? new Date(query.data.resolved_at).toLocaleString()
                  : "Not observed"}
              </dd>
            </div>
          </dl>
          <p className="mb-6 max-w-xl text-sm text-muted">
            Evidence records the first failure, third failed attempt, and any
            observed recovery. It remains available after raw check history is
            removed. No response bodies or headers are retained.
          </p>
          <div className="space-y-4">
            <Evidence
              title="Opening evidence"
              value={query.data.opening_evidence}
            />
            <Evidence
              title="Confirmation evidence"
              value={query.data.confirmation_evidence}
            />
            {query.data.recovery_evidence && (
              <Evidence
                title="Recovery evidence"
                value={query.data.recovery_evidence}
              />
            )}
          </div>
        </>
      )}
    </>
  );
}
