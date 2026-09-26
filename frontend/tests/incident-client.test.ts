import { afterEach, expect, it, vi } from "vitest";
import { getIncident, listIncidents } from "@/lib/api/incidents";
import { leaveWorkspace, safeReturnPath } from "@/lib/auth/redirect";
vi.mock("@/lib/auth/redirect", async (original) => ({
  ...(await original<typeof import("@/lib/auth/redirect")>()),
  leaveWorkspace: vi.fn(),
}));
afterEach(() => vi.unstubAllGlobals());
it("encodes incident filters and requests stored data without caching", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ items: [], next_cursor: null })),
    );
  vi.stubGlobal("fetch", fetcher);
  await listIncidents({
    monitorId: "monitor",
    status: "open",
    cursor: "opaque+cursor",
  });
  expect(fetcher.mock.calls[0][0]).toContain("cursor=opaque%2Bcursor");
  expect(fetcher.mock.calls[0][0]).toContain("monitor_id=monitor");
  expect(fetcher.mock.calls[0][1]).toMatchObject({
    credentials: "same-origin",
    cache: "no-store",
  });
});
it("redirects an expired incident session", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: "authentication_required" } }),
          { status: 401 },
        ),
      ),
  );
  await expect(getIncident("id")).rejects.toMatchObject({ status: 401 });
  expect(leaveWorkspace).toHaveBeenCalledWith("expired");
});
it("allows implemented incident return paths without allowing external destinations", () => {
  const path = "/incidents/00000000-0000-0000-0000-000000000001";
  expect(safeReturnPath(path)).toBe(path);
  expect(safeReturnPath("/incidents")).toBe("/incidents");
  expect(safeReturnPath("/incidents//evil.test")).toBe("/dashboard");
  expect(safeReturnPath("/incidents?next=https://evil.test")).toBe(
    "/dashboard",
  );
});
