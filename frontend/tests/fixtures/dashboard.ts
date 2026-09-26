import type { Dashboard } from "@/lib/api/dashboard";
import { incident } from "./incidents";
const metrics = {
  successful_runs: 3,
  failed_runs: 1,
  observations: 4,
  excluded_runs: 2,
  uptime_percent: 75,
  response_count: 3,
  mean_latency_ms: 123.4,
  first_observation_at: "2026-09-26T00:10:00Z",
  last_observation_at: "2026-09-26T00:50:00Z",
};
export const dashboard: Dashboard = {
  window: "24h",
  start: "2026-09-25T01:00:00Z",
  end: "2026-09-26T01:00:00Z",
  bucket_seconds: 3600,
  metrics,
  buckets: [
    {
      ...metrics,
      start: "2026-09-26T00:00:00Z",
      end: "2026-09-26T01:00:00Z",
      partial: false,
    },
  ],
  monitors: {
    total: 3,
    operational: 1,
    down: 1,
    confirming_failure: 0,
    unknown: 0,
    paused: 1,
    stale: 1,
    awaiting_check: 0,
  },
  open_incidents: 0,
  recent_incidents: [incident],
};
