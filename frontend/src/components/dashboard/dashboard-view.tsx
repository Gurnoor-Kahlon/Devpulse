"use client";

import Link from "next/link";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import {
  getDashboard,
  type Dashboard,
  type DashboardWindow,
} from "@/lib/api/dashboard";
import { usePollingQuery } from "@/lib/use-polling-query";

const percent = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(2)}%`;
const latency = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(1)} ms`;
const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
const tick = (value: string) =>
  new Date(value).toISOString().slice(5, 16).replace("T", " ");

function Trend({
  data,
  metric,
  title,
}: {
  data: Dashboard;
  metric: "uptime_percent" | "mean_latency_ms";
  title: string;
}) {
  return (
    <section
      aria-label={title}
      className="min-w-0 rounded-lg border border-border bg-surface p-4 sm:p-6"
    >
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-xs text-muted">
        {data.bucket_seconds / 3600}-hour buckets · UTC · gaps mean no
        observations
      </p>
      <div className="mt-5 h-60 min-w-0" data-testid={`chart-${metric}`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart
            data={data.buckets}
            accessibilityLayer
            margin={{ left: 0, right: 12, top: 8, bottom: 4 }}
          >
            <CartesianGrid
              stroke="var(--border)"
              strokeDasharray="3 3"
              vertical={false}
            />
            <XAxis
              dataKey="start"
              tickFormatter={tick}
              minTickGap={50}
              tick={{ fill: "var(--muted)", fontSize: 11 }}
            />
            <YAxis
              width={48}
              domain={metric === "uptime_percent" ? [0, 100] : [0, "auto"]}
              tick={{ fill: "var(--muted)", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{
                background: "var(--surface)",
                borderColor: "var(--border)",
                color: "var(--foreground)",
              }}
              labelFormatter={(value) => utc(String(value))}
              formatter={(value) =>
                metric === "uptime_percent"
                  ? percent(Number(value))
                  : latency(Number(value))
              }
            />
            <Line
              type="linear"
              dataKey={metric}
              name={title}
              stroke="var(--accent)"
              strokeWidth={2}
              dot={{ r: 3 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function DashboardData({ data }: { data: Dashboard }) {
  const m = data.metrics;
  return (
    <div className="space-y-6">
      <p className="text-xs text-muted">
        {utc(data.start)} – {utc(data.end)}. Latest response: {utc(data.end)}.
      </p>
      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Observed uptime", percent(m.uptime_percent)],
          ["Completed observations", String(m.observations)],
          ["Mean response latency", latency(m.mean_latency_ms)],
          ["Open incidents now", String(data.open_incidents)],
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
        {m.successful_runs} successful / {m.observations} completed scheduled
        runs; {m.failed_runs} failed. Retries count once. {m.excluded_runs}{" "}
        incomplete, cancelled, blocked, or infrastructure-failed scheduled runs
        excluded. Manual runs excluded. Latency uses {m.response_count} final
        attempts with an HTTP response.
      </p>
      <section
        aria-label="Current monitor states"
        className="rounded-lg border border-border bg-surface p-5"
      >
        <div className="flex flex-wrap justify-between gap-3">
          <h2 className="font-semibold">Current monitor states</h2>
          <Link href="/monitors" className="text-sm underline">
            Manage monitors
          </Link>
        </div>
        <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-4">
          {(
            [
              ["operational", "Operational"],
              ["down", "Down"],
              ["confirming_failure", "Confirming failure"],
              ["unknown", "Unknown"],
              ["paused", "Paused"],
            ] as const
          ).map(([key, label]) => (
            <div key={key}>
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-mono text-xl">{data.monitors[key]}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-sm text-muted">
          {data.monitors.total} unarchived monitors · {data.monitors.stale}{" "}
          stale observations · {data.monitors.awaiting_check} awaiting first
          check. Stale observations are separate from saved health and do not
          prove downtime.
        </p>
      </section>
      {m.observations === 0 ? (
        <EmptyState
          title="No observations in this window"
          description="No data is available for uptime or latency. Monitoring gaps are not evidence of success or failure."
        />
      ) : (
        <>
          <p className="text-xs text-muted">
            Observed range: {utc(m.first_observation_at!)} –{" "}
            {utc(m.last_observation_at!)}.
          </p>
          <div className="grid min-w-0 gap-4 xl:grid-cols-2">
            <Trend
              data={data}
              metric="uptime_percent"
              title="Observed uptime trend"
            />
            <Trend
              data={data}
              metric="mean_latency_ms"
              title="Mean response latency trend"
            />
          </div>
        </>
      )}
      <p className="text-sm text-muted">
        Partial history: only retained observations are shown, including
        archived monitors and earlier configurations. Empty buckets and periods
        between checks may contain gaps. This is a run-weighted success ratio,
        not time-weighted availability or an SLA.
      </p>
      <details className="rounded-lg border border-border bg-surface p-5">
        <summary className="font-medium">View bucket observations</summary>
        <div
          className="mt-4 overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label="Bucket observation table"
        >
          <table className="w-full text-left text-xs">
            <caption className="mb-3 text-left text-muted">
              UTC windows; first and last buckets may be partial. No data is
              never plotted as zero.
            </caption>
            <thead>
              <tr>
                {[
                  "Bucket start",
                  "Bucket end",
                  "Coverage",
                  "Successful",
                  "Failed",
                  "Excluded",
                  "Uptime",
                  "Responses",
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
              {data.buckets.map((b) => (
                <tr key={b.start} className="border-t border-border">
                  {[
                    utc(b.start),
                    utc(b.end),
                    b.partial ? "Partial bucket" : "Full bucket",
                    b.successful_runs,
                    b.failed_runs,
                    b.excluded_runs,
                    percent(b.uptime_percent),
                    b.response_count,
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
        aria-label="Recent incidents"
        className="rounded-lg border border-border bg-surface p-5"
      >
        <div className="flex flex-wrap justify-between gap-3">
          <h2 className="font-semibold">Recent incidents</h2>
          <Link href="/incidents" className="text-sm underline">
            All incidents
          </Link>
        </div>
        <p className="mt-2 text-xs text-muted">
          Latest five across retained history, independent of the selected
          window. Includes archived monitors.
        </p>
        {data.recent_incidents.length === 0 ? (
          <p className="mt-4 text-sm text-muted">
            No confirmed incidents. This does not imply uninterrupted
            availability.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-border">
            {data.recent_incidents.map((incident) => (
              <li
                key={incident.id}
                className="flex flex-wrap items-start justify-between gap-3 py-3"
              >
                <div className="min-w-0">
                  <Link
                    href={`/incidents/${incident.id}`}
                    className="break-words font-medium underline"
                  >
                    {incident.monitor_name}
                  </Link>
                  <p className="mt-1 text-xs text-muted">
                    First failure: {utc(incident.started_at)}
                  </p>
                </div>
                <span
                  className={
                    incident.status === "open" ? "text-danger" : "text-success"
                  }
                >
                  {incident.status === "open" ? "Open" : "Resolved"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export function DashboardView() {
  const [window, setWindow] = useState<DashboardWindow>("24h");
  const query = usePollingQuery(["dashboard", window], (signal) =>
    getDashboard(window, signal),
  );
  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-2 text-sm text-muted">
          Reliability from your stored monitoring observations.
        </p>
      </div>
      <div className="mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label
            htmlFor="dashboard-window"
            className="mb-2 block text-sm font-medium"
          >
            History window
          </label>
          <select
            id="dashboard-window"
            className="text-field"
            value={window}
            onChange={(event) =>
              setWindow(event.target.value as DashboardWindow)
            }
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
          Refresh overview
        </Button>
      </div>
      <p className="mb-6 text-xs text-muted">
        Refreshes every 15 seconds while visible; slows down after errors.
        Refreshing reads stored results.
      </p>
      {query.isPending ? (
        <LoadingState label="Loading overview" />
      ) : !query.data ? (
        <ErrorState onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.isError && (
            <p role="alert" className="mb-4 text-danger">
              Refresh failed. Showing the last loaded overview; automatic
              refresh will retry.
            </p>
          )}
          <DashboardData data={query.data} />
        </>
      )}
    </>
  );
}
