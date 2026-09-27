"use client";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { components } from "@/lib/api/schema";
const percent = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(2)}%`;
const latency = (value: number | null) =>
  value === null ? "No data" : `${value.toFixed(1)} ms`;
const utc = (value: string) =>
  new Date(value).toISOString().replace("T", " ").slice(0, 19) + " UTC";
const tick = (value: string) =>
  new Date(value).toISOString().slice(5, 16).replace("T", " ");

export function Trend({
  data,
  metric,
  title,
}: {
  data: Pick<
    components["schemas"]["DashboardResponse"],
    "buckets" | "bucket_seconds"
  >;
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
