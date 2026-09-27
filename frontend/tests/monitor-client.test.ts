import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { clearCsrf } from "@/lib/api/client";
import {
  archiveMonitor,
  createMonitor,
  listMonitors,
  updateMonitor,
} from "@/lib/api/monitors";
import { leaveWorkspace, safeReturnPath } from "@/lib/auth/redirect";
import { monitor } from "./fixtures/monitors";
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

it("loads every cursor page so search never silently omits monitors", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      json({ items: [monitor], next_cursor: "opaque+cursor" }),
    )
    .mockResolvedValueOnce(json({ items: [], next_cursor: null }));
  vi.stubGlobal("fetch", fetcher);
  expect(await listMonitors()).toEqual([monitor]);
  expect(fetcher.mock.calls[1][0]).toContain("cursor=opaque%2Bcursor");
});
it("sends versioned cookie/CSRF mutations and accepts an empty archive response", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "token" }))
    .mockResolvedValueOnce(json(monitor))
    .mockResolvedValueOnce(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetcher);
  await updateMonitor(monitor.id, { configuration_version: 1, enabled: false });
  await expect(archiveMonitor(monitor)).resolves.toBeUndefined();
  expect(fetcher.mock.calls[1][1]).toMatchObject({
    method: "PATCH",
    credentials: "same-origin",
    headers: { "X-CSRF-Token": "token" },
  });
  expect(fetcher.mock.calls[2][0]).toContain("configuration_version=1");
});
it("refreshes rejected CSRF once but never retries uncertain saves", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "old" }))
    .mockResolvedValueOnce(json({ error: { code: "csrf_rejected" } }, 403))
    .mockResolvedValueOnce(json({ csrf_token: "new" }))
    .mockRejectedValueOnce(new Error("network"));
  vi.stubGlobal("fetch", fetcher);
  await expect(
    createMonitor({
      name: monitor.name,
      url: monitor.url,
      method: "GET",
      expected_status: 200,
      interval_seconds: 60,
      timeout_seconds: 5,
      enabled: true,
    }),
  ).rejects.toMatchObject({ status: 0 });
  expect(fetcher).toHaveBeenCalledTimes(4);
});
it("redirects expired sessions without replaying a mutation", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(json({ csrf_token: "token" }))
    .mockResolvedValueOnce(
      json({ error: { code: "authentication_required" } }, 401),
    );
  vi.stubGlobal("fetch", fetcher);
  await expect(archiveMonitor(monitor)).rejects.toMatchObject({ status: 401 });
  expect(leaveWorkspace).toHaveBeenCalledWith("expired");
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("allows only implemented monitor return destinations", () => {
  for (const path of [
    "/monitors",
    "/monitors/new",
    `/monitors/${monitor.id}/edit`,
    `/monitors/${monitor.id}`,
  ])
    expect(safeReturnPath(path)).toBe(path);
  for (const path of [
    "/monitors//evil.com/edit",
    "/monitors/new?next=https://evil.com",
    `/monitors/${monitor.id}?next=https://evil.com`,
  ])
    expect(safeReturnPath(path)).toBe("/dashboard");
});
