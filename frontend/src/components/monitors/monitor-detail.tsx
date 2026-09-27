"use client";

import Link from "next/link";
import { useState } from "react";
import { Trend } from "@/components/analytics/trend";
import { IncidentList } from "@/components/incidents/incident-list";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiError } from "@/lib/api/client";
import {
  getMonitorAnalytics,
  getMonitorChecks,
  type MonitorAnalytics,
  type HistoryWindow,
} from "@/lib/api/monitors";
import { usePollingQuery } from "@/lib/use-polling-query";

const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
const percent = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(2)}%`;
const latency = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(1)} ms`;

function Checks({ id, window }: { id: string; window: HistoryWindow }) {
  const [cursor, setCursor] = useState<string>();
  const query = usePollingQuery(
    ["monitor-checks", id, window, cursor],
    (signal) => getMonitorChecks(id, window, cursor, signal),
  );
  return (
    <section aria-label="Check history" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Check history</h2>
        <Button
          variant="secondary"
          loading={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh checks
        </Button>
      </div>
      <p className="text-sm text-muted">
        Individual attempts, including retries and manual diagnostics. These
        rows do not each count toward uptime. Expand an attempt for recorded
        evidence.
      </p>
      {query.isPending ? (
        <LoadingState label="Loading checks" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="text-danger">
              Check refresh failed. Showing the last loaded checks.
            </p>
          )}
          <p className="text-xs text-muted">
            Scheduled range: {utc(query.data.start)} – {utc(query.data.end)}.
            Older pages keep this window; use Newest checks to include new
            observations.
          </p>
          {query.data.items.length === 0 ? (
            <EmptyState
              title="No retained checks in this window"
              description="Checks may not have run yet, or raw history may have been removed. Incident evidence is retained separately."
            />
          ) : (
            <ul className="space-y-3" aria-label="Check attempts">
              {query.data.items.map((check) => (
                <li
                  key={check.id}
                  className="rounded-lg border border-border bg-surface p-4"
                >
                  <details>
                    <summary className="break-words font-medium">
                      {utc(check.started_at)} · Attempt {check.attempt_number} ·{" "}
                      {check.outcome.replaceAll("_", " ")} ·{" "}
                      {check.http_status === null
                        ? "No HTTP response"
                        : `HTTP ${check.http_status}`}
                    </summary>
                    <dl className="mt-4 grid min-w-0 gap-3 text-sm sm:grid-cols-2">
                      {[
                        [
                          "Origin",
                          check.trigger === "manual"
                            ? "Manual diagnostic"
                            : "Scheduled",
                        ],
                        ["Run state", check.run_state.replaceAll("_", " ")],
                        [
                          "Final outcome",
                          check.final_outcome ?? "Not completed",
                        ],
                        [
                          "Attempt role",
                          check.is_final_attempt
                            ? "Final stored attempt"
                            : "Retry or unfinished run",
                        ],
                        [
                          "Configuration version",
                          String(check.configuration_version),
                        ],
                        ["Scheduled", utc(check.scheduled_at)],
                        ["Started", utc(check.started_at)],
                        ["Finished", utc(check.finished_at)],
                        ["Probe duration", latency(check.duration_ms)],
                        ["Run ID", check.run_id],
                        ["Check ID", check.id],
                      ].map(([label, value]) => (
                        <div key={label} className="min-w-0">
                          <dt className="text-muted">{label}</dt>
                          <dd className="break-all">{value}</dd>
                        </div>
                      ))}
                    </dl>
                    {check.error_message && (
                      <p className="mt-4 text-sm text-muted">
                        {check.error_message}{" "}
                        <span className="font-mono">({check.error_code})</span>
                      </p>
                    )}
                  </details>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setCursor(undefined);
                if (!cursor) void query.refetch();
              }}
            >
              Newest checks
            </Button>
            {query.data.next_cursor && (
              <Button
                variant="secondary"
                onClick={() => setCursor(query.data!.next_cursor!)}
              >
                Older checks
              </Button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function Analytics({ data }: { data: MonitorAnalytics }) {
  const m = data.metrics;
  return (
    <div className="space-y-5">
      <p className="text-xs text-muted">
        {utc(data.start)} – {utc(data.end)} · sampled {utc(data.end)}
      </p>
      <dl className="grid gap-3 sm:grid-cols-3">
        {[
          ["Observed uptime", percent(m.uptime_percent)],
          ["Completed scheduled runs", String(m.observations)],
          ["Mean response latency", latency(m.mean_latency_ms)],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-lg border border-border bg-surface p-5"
          >
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="mt-2 font-mono text-2xl">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm text-muted">
        {m.successful_runs} successful, {m.failed_runs} failed; retries count
        once. {m.excluded_runs} incomplete, cancelled, blocked, or
        infrastructure-failed scheduled runs excluded. Manual runs excluded.
        Latency and status distribution use {m.response_count} final attempts
        with an HTTP response.
      </p>
      <p className="text-sm text-muted">
        Partial history: retained observations include earlier configurations.
        Gaps are not success or downtime; this ratio does not measure
        time-weighted availability or an SLA.
      </p>
      {m.first_observation_at && (
        <p className="text-xs text-muted">
          Observed range: {utc(m.first_observation_at)} –{" "}
          {utc(m.last_observation_at!)}
        </p>
      )}
      {m.response_count === 0 ? (
        <EmptyState
          title="No response latency data"
          description="No eligible final attempts received an HTTP response in this window."
        />
      ) : (
        <Trend
          data={data}
          metric="mean_latency_ms"
          title="Response latency history"
        />
      )}
      <details className="rounded-lg border border-border bg-surface p-5">
        <summary className="font-medium">View latency buckets</summary>
        <div
          tabIndex={0}
          role="region"
          aria-label="Latency bucket table"
          className="mt-4 overflow-x-auto"
        >
          <table className="w-full text-left text-xs">
            <caption className="mb-3 text-left text-muted">
              UTC bounds; empty latency values remain No data.
            </caption>
            <thead>
              <tr>
                {[
                  "Start",
                  "End",
                  "Coverage",
                  "Completed runs",
                  "Responses",
                  "Mean latency",
                ].map((label) => (
                  <th key={label} scope="col" className="p-2 whitespace-nowrap">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.buckets.map((b) => (
                <tr key={b.start} className="border-t border-border">
                  {[
                    utc(b.start),
                    utc(b.end),
                    b.partial ? "Partial bucket" : "Full bucket",
                    b.observations,
                    b.response_count,
                    latency(b.mean_latency_ms),
                  ].map((value, i) => (
                    <td key={i} className="p-2 whitespace-nowrap">
                      {value}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <section
        aria-label="HTTP status distribution"
        className="rounded-lg border border-border bg-surface p-5"
      >
        <h2 className="text-xl font-semibold">HTTP status distribution</h2>
        <p className="mt-2 text-sm text-muted">
          Final responses from completed scheduled runs. No-response failures
          and earlier retries are excluded.
        </p>
        {data.status_distribution.length === 0 ? (
          <p className="mt-4 text-muted">No HTTP response data</p>
        ) : (
          <ul className="mt-4 space-y-4">
            {data.status_distribution.map((row) => (
              <li key={row.http_status}>
                <div className="flex flex-wrap justify-between gap-3 text-sm">
                  <span className="font-mono">HTTP {row.http_status}</span>
                  <span>
                    {row.count} responses · {percent(row.percentage)}
                  </span>
                </div>
                <div
                  className="mt-2 h-2 rounded bg-elevated"
                  aria-hidden="true"
                >
                  <div
                    className="h-2 rounded bg-accent"
                    style={{ width: `${row.percentage}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function MonitorDetail({ id }: { id: string }) {
  const [window, setWindow] = useState<HistoryWindow>("24h");
  const query = usePollingQuery(["monitor-analytics", id, window], (signal) =>
    getMonitorAnalytics(id, window, signal),
  );
  if (query.isPending) return <LoadingState label="Loading monitor history" />;
  if (!query.data)
    return query.error instanceof ApiError && query.error.status === 404 ? (
      <EmptyState
        title="Monitor unavailable"
        description="This monitor could not be found in your account."
        action={
          <Link href="/monitors" className="button button--secondary">
            Back to monitors
          </Link>
        }
      />
    ) : (
      <ErrorState onRetry={() => void query.refetch()} />
    );
  const data = query.data;
  return (
    <div className="space-y-7">
      <Link href="/monitors" className="text-sm underline">
        Back to monitors
      </Link>
      <div>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="min-w-0 break-words text-3xl font-semibold">
            {data.monitor.name}
          </h1>
          {!data.archived_at && (
            <Link
              href={`/monitors/${id}/edit`}
              className="button button--secondary"
            >
              Edit settings
            </Link>
          )}
        </div>
        <p className="mt-3 break-all font-mono text-xs text-muted">
          {data.monitor.url}
        </p>
        <p className="mt-3 text-sm">
          {data.archived_at
            ? "Archived · read-only history"
            : !data.monitor.enabled
              ? "Paused"
              : `Saved health: ${data.monitor.current_state.replaceAll("_", " ")}`}{" "}
          · Observations: {data.monitor.observation_status.replaceAll("_", " ")}
        </p>
        <p className="mt-2 text-xs text-muted">
          Current configuration v{data.monitor.configuration_version}:{" "}
          {data.monitor.method}, expected HTTP {data.monitor.expected_status},
          every {data.monitor.interval_seconds}s. Check evidence retains its own
          version; current settings are not historical snapshots.
        </p>
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="monitor-history-window"
            className="mb-2 block text-sm font-medium"
          >
            History window
          </label>
          <select
            id="monitor-history-window"
            className="text-field"
            value={window}
            onChange={(event) => setWindow(event.target.value as HistoryWindow)}
          >
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
        </div>
        <Button
          variant="secondary"
          loading={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Refresh analytics
        </Button>
      </div>
      <p className="text-xs text-muted">
        Refreshes stored results every 15 seconds while visible, with error
        backoff. Stale observations do not prove downtime. No response bodies or
        headers are retained.
      </p>
      {query.isError && (
        <p role="alert" className="text-danger">
          Analytics refresh failed. Showing the last loaded history.
        </p>
      )}
      <Analytics data={data} />
      <Checks key={window} id={id} window={window} />
      <section
        aria-label="Monitor incident history"
        className="border-t border-border pt-7"
      >
        <p className="mb-4 text-sm text-muted">
          Retained incident history across all time, independent of the selected
          check window.
        </p>
        <IncidentList monitorId={id} embedded />
      </section>
    </div>
  );
}
