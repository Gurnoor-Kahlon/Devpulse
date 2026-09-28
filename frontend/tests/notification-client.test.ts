import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearCsrf } from "@/lib/api/client";
import {
  getDeliveries,
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/lib/api/notifications";
import { leaveWorkspace, safeReturnPath } from "@/lib/auth/redirect";
vi.mock("@/lib/auth/redirect", async (original) => ({
  ...(await original<typeof import("@/lib/auth/redirect")>()),
  leaveWorkspace: vi.fn(),
}));
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => {
  clearCsrf();
  vi.mocked(leaveWorkspace).mockClear();
});
afterEach(() => vi.unstubAllGlobals());
it("sends versioned CSRF-protected preferences and scoped cursor reads", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "token" }))
    .mockResolvedValueOnce(json({}))
    .mockResolvedValueOnce(json({ items: [], next_cursor: null }));
  vi.stubGlobal("fetch", fetcher);
  const body = {
    configuration_version: 0,
    enabled: true,
    on_open: true,
    on_recovery: false,
  };
  await updateNotificationPreferences(body);
  await getDeliveries({ incidentId: "id", cursor: "cursor+value" });
  expect(fetcher.mock.calls[1][1]).toMatchObject({
    method: "PUT",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": "token" },
    body: JSON.stringify(body),
  });
  expect(fetcher.mock.calls[2][0]).toContain(
    "incident_id=id&cursor=cursor%2Bvalue",
  );
  expect(safeReturnPath("/notifications")).toBe("/notifications");
});
it("refreshes only definite CSRF rejection and does not replay uncertain saves", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "old" }))
    .mockResolvedValueOnce(json({ error: { code: "csrf_rejected" } }, 403))
    .mockResolvedValueOnce(json({ csrf_token: "new" }))
    .mockRejectedValueOnce(new Error("network"));
  vi.stubGlobal("fetch", fetcher);
  await expect(
    updateNotificationPreferences({
      configuration_version: 0,
      enabled: false,
      on_open: true,
      on_recovery: true,
    }),
  ).rejects.toMatchObject({ status: 0 });
  expect(fetcher).toHaveBeenCalledTimes(4);
});
it("redirects an expired notification session", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        json({ error: { code: "authentication_required" } }, 401),
      ),
  );
  await expect(getNotificationPreferences()).rejects.toMatchObject({
    status: 401,
  });
  expect(leaveWorkspace).toHaveBeenCalledWith("expired");
});
