"use client";

import Link from "next/link";
import { useState } from "react";
import { usePollingQuery } from "@/lib/use-polling-query";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { listIncidents } from "@/lib/api/incidents";

export function IncidentList({ monitorId }: { monitorId?: string }) {
  const [status, setStatus] = useState<"all" | "open" | "resolved">("all");
  const [cursor, setCursor] = useState<string>();
  const query = usePollingQuery(
    ["incidents", monitorId, status, cursor],
    (signal) =>
      listIncidents(
        { monitorId, status: status === "all" ? undefined : status, cursor },
        signal,
      ),
  );
  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Incidents</h1>
        <p className="mt-2 max-w-xl text-sm text-muted">
          Three failed attempts confirm an incident. One successful scheduled
          check resolves it. Pausing a monitor leaves its incident open.
        </p>
        {monitorId && (
          <p className="mt-3 text-sm text-muted">
            Showing incidents for this monitor.{" "}
            <Link href="/incidents" className="text-foreground underline">
              Show all incidents
            </Link>
          </p>
        )}
      </div>
      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <label
            htmlFor="incident-status"
            className="block text-sm font-medium"
          >
            Incident status
          </label>
          <select
            id="incident-status"
            className="text-field"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as "all" | "open" | "resolved");
              setCursor(undefined);
            }}
          >
            <option value="all">All incidents</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
        <Button
          variant="secondary"
          loading={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh incidents
        </Button>
      </div>
      {query.isPending ? (
        <LoadingState label="Loading incidents" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Refresh failed. Showing the last loaded incidents.
            </p>
          )}
          {query.data.items.length === 0 ? (
            <EmptyState
              title="No incidents found"
              description="No confirmed incidents match this view. This does not imply uninterrupted availability."
            />
          ) : (
            <ul aria-label="Incidents" className="space-y-3">
              {query.data.items.map((incident) => (
                <li
                  key={incident.id}
                  className="rounded-lg border border-border bg-surface p-5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="min-w-0 break-words font-semibold">
                      <Link
                        className="underline underline-offset-4"
                        href={`/incidents/${incident.id}`}
                      >
                        {incident.monitor_name}
                      </Link>
                    </h2>
                    <span
                      className={`text-xs font-medium ${incident.status === "open" ? "text-danger" : "text-success"}`}
                    >
                      {incident.status === "open" ? "Open" : "Resolved"}
                    </span>
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted">
                    <div>
                      <dt>First failure</dt>
                      <dd>{new Date(incident.started_at).toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>Confirmed</dt>
                      <dd>
                        {new Date(incident.confirmed_at).toLocaleString()}
                      </dd>
                    </div>
                    <div>
                      <dt>Recovery</dt>
                      <dd>
                        {incident.resolved_at
                          ? new Date(incident.resolved_at).toLocaleString()
                          : "Not observed"}
                      </dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            {cursor && (
              <Button variant="secondary" onClick={() => setCursor(undefined)}>
                Newest incidents
              </Button>
            )}
            {query.data.next_cursor && (
              <Button
                variant="secondary"
                onClick={() => setCursor(query.data!.next_cursor!)}
              >
                Older incidents
              </Button>
            )}
          </div>
        </>
      )}
    </>
  );
}
