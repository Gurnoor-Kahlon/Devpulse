import type { MonitorAnalytics, CheckPage } from "@/lib/api/monitors";
import { dashboard } from "./dashboard";
import { monitor } from "./monitors";
export const analytics: MonitorAnalytics = {
  window: dashboard.window,
  start: dashboard.start,
  end: dashboard.end,
  bucket_seconds: dashboard.bucket_seconds,
  metrics: dashboard.metrics,
  buckets: dashboard.buckets,
  monitor,
  archived_at: null,
  status_distribution: [
    { http_status: 200, count: 2, percentage: 66.666 },
    { http_status: 503, count: 1, percentage: 33.333 },
  ],
};
export const checks: CheckPage = {
  start: analytics.start,
  end: analytics.end,
  next_cursor: null,
  items: [
    {
      id: "00000000-0000-0000-0000-000000000009",
      run_id: "00000000-0000-0000-0000-000000000008",
      scheduled_at: "2026-09-26T00:10:00Z",
      configuration_version: 1,
      trigger: "scheduled",
      run_state: "completed",
      final_outcome: "failure",
      attempt_number: 3,
      is_final_attempt: true,
      started_at: "2026-09-26T00:10:20Z",
      finished_at: "2026-09-26T00:10:21Z",
      outcome: "failure",
      http_status: 503,
      duration_ms: 20,
      error_code: "unexpected_status",
      error_message: "The HTTP status did not match the expected status.",
    },
  ],
};
