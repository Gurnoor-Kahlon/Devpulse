import { ApiError, clearCsrf, request } from "./client";
import type { components } from "./schema";
import { leaveWorkspace } from "@/lib/auth/redirect";

export type Dashboard = components["schemas"]["DashboardResponse"];
export type DashboardWindow = Dashboard["window"];
export async function getDashboard(
  window: DashboardWindow,
  signal?: AbortSignal,
): Promise<Dashboard> {
  try {
    return await request<Dashboard>(
      `/api/v1/dashboard?${new URLSearchParams({ window })}`,
      { signal },
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearCsrf();
      leaveWorkspace("expired");
    }
    throw error;
  }
}
