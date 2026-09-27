import { ApiError, clearCsrf, csrf, request } from "./client";
import type { components } from "./schema";
import { leaveWorkspace } from "@/lib/auth/redirect";

export type Monitor = components["schemas"]["MonitorResponse"];
export type MonitorCreate = components["schemas"]["MonitorCreate"];
export type MonitorUpdate = components["schemas"]["MonitorUpdate"];
type MonitorPage = components["schemas"]["MonitorPage"];
const base = "/api/v1/monitors";

async function monitorRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      const headers = options.method
        ? { "Content-Type": "application/json", "X-CSRF-Token": await csrf() }
        : undefined;
      return await request<T>(path, { ...options, headers });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearCsrf();
        leaveWorkspace("expired");
      }
      // Only a definite CSRF rejection is safe to retry. Network failures are uncertain writes.
      if (
        attempt === 0 &&
        options.method &&
        error instanceof ApiError &&
        error.code === "csrf_rejected"
      ) {
        clearCsrf();
        continue;
      }
      throw error;
    }
  }
}

export async function listMonitors(signal?: AbortSignal): Promise<Monitor[]> {
  const items: Monitor[] = [];
  let cursor: string | null = null;
  do {
    const params = new URLSearchParams({ limit: "100" });
    if (cursor) params.set("cursor", cursor);
    const page: MonitorPage = await monitorRequest(`${base}?${params}`, {
      signal,
    });
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}
export const getMonitor = (id: string, signal?: AbortSignal) =>
  monitorRequest<Monitor>(`${base}/${encodeURIComponent(id)}`, { signal });
export const createMonitor = (body: MonitorCreate) =>
  monitorRequest<Monitor>(base, { method: "POST", body: JSON.stringify(body) });
export const updateMonitor = (id: string, body: MonitorUpdate) =>
  monitorRequest<Monitor>(`${base}/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
export const archiveMonitor = (monitor: Monitor) =>
  monitorRequest<void>(
    `${base}/${encodeURIComponent(monitor.id)}?configuration_version=${monitor.configuration_version}`,
    { method: "DELETE" },
  );

export type MonitorAnalytics = components["schemas"]["MonitorAnalytics"];
export type CheckPage = components["schemas"]["CheckPage"];
export type HistoryWindow = MonitorAnalytics["window"];
export const getMonitorAnalytics = (
  id: string,
  window: HistoryWindow,
  signal?: AbortSignal,
) =>
  monitorRequest<MonitorAnalytics>(
    `${base}/${encodeURIComponent(id)}/analytics?${new URLSearchParams({ window })}`,
    { signal },
  );
export const getMonitorChecks = (
  id: string,
  window: HistoryWindow,
  cursor?: string,
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams({ window, limit: "25" });
  if (cursor) params.set("cursor", cursor);
  return monitorRequest<CheckPage>(
    `${base}/${encodeURIComponent(id)}/checks?${params}`,
    { signal },
  );
};

export type AssertionPage = components["schemas"]["AssertionPage"];
export type AssertionDefinition = components["schemas"]["AssertionDefinition"];
export type AssertionResult = components["schemas"]["AssertionResult"];
export const getAssertions = (id: string, signal?: AbortSignal) =>
  monitorRequest<AssertionPage>(
    `${base}/${encodeURIComponent(id)}/assertions`,
    { signal },
  );
export const replaceAssertions = (
  id: string,
  body: components["schemas"]["AssertionUpdate"],
) =>
  monitorRequest<AssertionPage>(
    `${base}/${encodeURIComponent(id)}/assertions`,
    {
      method: "PUT",
      body: JSON.stringify(body),
    },
  );
