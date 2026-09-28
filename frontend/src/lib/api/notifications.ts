import { ApiError, clearCsrf, csrf, request } from "./client";
import type { components } from "./schema";
import { leaveWorkspace } from "@/lib/auth/redirect";

export type NotificationPreferences =
  components["schemas"]["NotificationPreferences"];
export type NotificationUpdate = components["schemas"]["NotificationUpdate"];
export type Delivery = components["schemas"]["DeliveryResponse"];
export type DeliveryPage = components["schemas"]["DeliveryPage"];

async function notificationRequest<T>(
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
export const getNotificationPreferences = (signal?: AbortSignal) =>
  notificationRequest<NotificationPreferences>(
    "/api/v1/notifications/preferences",
    { signal },
  );
export const updateNotificationPreferences = (body: NotificationUpdate) =>
  notificationRequest<NotificationPreferences>(
    "/api/v1/notifications/preferences",
    { method: "PUT", body: JSON.stringify(body) },
  );
export const getDeliveries = (
  options: { incidentId?: string; cursor?: string },
  signal?: AbortSignal,
) => {
  const params = new URLSearchParams({ limit: "25" });
  if (options.incidentId) params.set("incident_id", options.incidentId);
  if (options.cursor) params.set("cursor", options.cursor);
  return notificationRequest<DeliveryPage>(
    `/api/v1/notifications/deliveries?${params}`,
    { signal },
  );
};
