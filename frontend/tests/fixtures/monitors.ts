import type { Monitor } from "@/lib/api/monitors";
export const monitor: Monitor = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Payments API",
  url: "https://example.com/health",
  method: "GET",
  expected_status: 200,
  interval_seconds: 60,
  timeout_seconds: 5,
  enabled: true,
  configuration_version: 1,
  next_due_at: "2026-01-01T00:00:00Z",
  current_state: "unknown",
  last_completed_check_at: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
export const account = {
  id: "account",
  email: "person@example.com",
  email_verified_at: "2026-01-01T00:00:00Z",
};
