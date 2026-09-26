import { ApiError, clearCsrf, request } from "./client";
import type { components } from "./schema";
import { leaveWorkspace } from "@/lib/auth/redirect";

export type Incident = components["schemas"]["IncidentResponse"];
export type IncidentDetail = components["schemas"]["IncidentDetail"];
export type IncidentEvidence = components["schemas"]["IncidentEvidence"];
export type IncidentPage = components["schemas"]["IncidentPage"];

async function incidentRequest<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  try {
    return await request<T>(path, { signal });
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      clearCsrf();
      leaveWorkspace("expired");
    }
    throw error;
  }
}

export function listIncidents(
  options: {
    status?: "open" | "resolved";
    monitorId?: string;
    cursor?: string;
  },
  signal?: AbortSignal,
): Promise<IncidentPage> {
  const params = new URLSearchParams({ limit: "25" });
  if (options.status) params.set("status", options.status);
  if (options.monitorId) params.set("monitor_id", options.monitorId);
  if (options.cursor) params.set("cursor", options.cursor);
  return incidentRequest(`/api/v1/incidents?${params}`, signal);
}

export const getIncident = (id: string, signal?: AbortSignal) =>
  incidentRequest<IncidentDetail>(
    `/api/v1/incidents/${encodeURIComponent(id)}`,
    signal,
  );
