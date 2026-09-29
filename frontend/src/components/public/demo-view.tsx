"use client";

import { useState } from "react";
import { Trend } from "@/components/analytics/trend";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingState } from "@/components/ui/loading-state";
import { getDemo, type Demo, type DemoWindow } from "@/lib/api/demo";
import { usePollingQuery } from "@/lib/use-polling-query";

const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
const percent = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(2)}%`;
const latency = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(1)} ms`;
const states = {
  operational: "Operational",
  down: "Down",
  confirming_failure: "Confirming failure",
  unknown: "Health not evaluated",
  paused: "Paused",
};

function PublishedMonitor({ monitor }: { monitor: Demo["monitors"][number] }) {
  const { history, recent_incidents: incidents } = monitor;
  const m = history.metrics;
  return (
    <article
      aria-labelledby={`monitor-${monitor.slug}`}
      className="min-w-0 rounded-lg border border-border bg-surface p-5 sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id={`monitor-${monitor.slug}`}
            className="text-xl font-semibold break-words"
          >
            {monitor.label}
          </h2>
          {monitor.controlled_failure && (
            <p className="mt-2 text-sm text-warning">
              Controlled failure exercise · intentionally induced failures
            </p>
          )}
        </div>
        <p
          className={
            monitor.state === "down" ? "text-danger" : "text-foreground"
          }
        >
          Saved health: {states[monitor.state]}
        </p>
      </div>
      <p className="mt-4 text-xs text-muted">
        Last scheduled observation:{" "}
        {monitor.last_checked_at
          ? utc(monitor.last_checked_at)
          : "Awaiting first check"}
        .
      </p>
      {monitor.stale && (
        <p className="mt-2 text-sm text-warning">
          Stale observations. Saved health does not establish current
          availability.
        </p>
      )}
      <dl className="mt-6 grid gap-3 sm:grid-cols-3">
        {[
          ["Observed uptime", percent(m.uptime_percent)],
          ["Completed observations", String(m.observations)],
          ["Mean response latency", latency(m.mean_latency_ms)],
        ].map(([label, value]) => (
          <div
            key={label}
            className="rounded-md border border-border bg-background p-4"
          >
            <dt className="text-xs text-muted">{label}</dt>
            <dd className="mt-2 font-mono text-2xl">{value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-sm text-muted">
        {m.successful_runs} successful / {m.observations} completed scheduled
        runs; {m.failed_runs} failed. Retries count once. {m.excluded_runs}{" "}
        incomplete, cancelled, blocked, or infrastructure-failed scheduled runs
        excluded. Manual runs excluded. Latency uses {m.response_count} final
        HTTP responses.
      </p>
      <p className="mt-3 text-xs text-muted">
        Window: {utc(history.start)} – {utc(history.end)}. Observed range:{" "}
        {m.first_observation_at && m.last_observation_at
          ? `${utc(m.first_observation_at)} – ${utc(m.last_observation_at)}`
          : "No observations"}
        .
      </p>
      {m.observations ? (
        <div className="mt-6 grid min-w-0 gap-4 lg:grid-cols-2">
          <Trend
            data={history}
            metric="uptime_percent"
            title="Observed uptime trend"
          />
          <Trend
            data={history}
            metric="mean_latency_ms"
            title="Mean response latency trend"
          />
        </div>
      ) : (
        <p className="mt-6 text-muted">
          No observations in this window. No data does not mean 100% uptime.
        </p>
      )}
      <details className="mt-5 rounded-md border border-border p-4">
        <summary className="min-h-6 font-medium">
          View accessible observation table
        </summary>
        <div
          tabIndex={0}
          role="region"
          aria-label={`${monitor.label} observation table`}
          className="mt-4 overflow-x-auto"
        >
          <table className="w-full text-left text-xs">
            <caption className="mb-3 text-left text-muted">
              UTC bucket starts. First and last buckets may be partial; empty
              buckets indicate gaps.
            </caption>
            <thead>
              <tr>
                {[
                  "Bucket start",
                  "Coverage",
                  "Observations",
                  "Uptime",
                  "Mean latency",
                ].map((label) => (
                  <th
                    key={label}
                    scope="col"
                    className="px-3 py-2 whitespace-nowrap"
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.buckets.map((b) => (
                <tr key={b.start} className="border-t border-border">
                  {[
                    utc(b.start),
                    b.partial ? "Partial" : "Full",
                    b.observations,
                    percent(b.uptime_percent),
                    latency(b.mean_latency_ms),
                  ].map((value, i) => (
                    <td key={i} className="px-3 py-2 whitespace-nowrap">
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
        aria-label={`${monitor.label} recent incidents`}
        className="mt-6 border-t border-border pt-5"
      >
        <h3 className="font-semibold">Recent incidents</h3>
        <p className="mt-2 text-xs text-muted">
          Latest five retained incidents, independent of the selected window.
        </p>
        {incidents.length ? (
          <ul className="mt-3 divide-y divide-border">
            {incidents.map((incident, i) => (
              <li key={i} className="py-3 text-sm">
                <p
                  className={
                    incident.resolved_at ? "text-success" : "text-danger"
                  }
                >
                  {incident.resolved_at ? "Resolved" : "Open"}
                </p>
                <p className="text-muted">
                  First failure: {utc(incident.started_at)} · Confirmed:{" "}
                  {utc(incident.confirmed_at)}
                </p>
                {incident.resolved_at && (
                  <p className="text-muted">
                    Recovery observed: {utc(incident.resolved_at)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted">
            No confirmed incidents recorded. This does not imply uninterrupted
            availability.
          </p>
        )}
      </section>
    </article>
  );
}

export function DemoView() {
  const [window, setWindow] = useState<DemoWindow>("24h");
  const query = usePollingQuery(["public-demo", window], (signal) =>
    getDemo(window, signal),
  );
  return (
    <>
      <div className="mb-5 flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="demo-window"
            className="mb-2 block text-sm font-medium"
          >
            History window
          </label>
          <select
            id="demo-window"
            className="text-field"
            value={window}
            onChange={(event) => setWindow(event.target.value as DemoWindow)}
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
          Refresh demo
        </Button>
      </div>
      <p className="mb-6 text-xs text-muted">
        Reads stored results every 15 seconds while visible; pauses in hidden
        tabs and slows after errors. Refreshing never runs a check.
      </p>
      {query.isPending ? (
        <LoadingState label="Loading published observations" />
      ) : query.isError ? (
        <ErrorState
          title="The demo is temporarily unavailable"
          description="Published observations could not be refreshed. Try again to load the current publication."
          onRetry={() => void query.refetch()}
        />
      ) : (
        query.data && (
          <>
            <p className="mb-5 text-xs text-muted">
              Retrieved: {utc(query.data.generated_at)}.
            </p>
            {query.data.monitors.length ? (
              <div className="space-y-6">
                {query.data.monitors.map((m) => (
                  <PublishedMonitor key={m.slug} monitor={m} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No monitors are published yet"
                description="This demo will show real observations when its owner explicitly publishes a monitor. No monitoring history is invented."
              />
            )}
          </>
        )
      )}
      <p className="mt-6 text-sm text-muted">
        Partial history: only retained scheduled observations are shown,
        including earlier configurations. Gaps between checks remain unknown.
        Observed uptime is a run-weighted success ratio, not time-weighted
        availability or an SLA.
      </p>
    </>
  );
}
