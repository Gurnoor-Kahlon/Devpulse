import { afterEach, expect, it, vi } from "vitest";
import { getMonitorAnalytics, getMonitorChecks } from "@/lib/api/monitors";
import { leaveWorkspace, safeReturnPath } from "@/lib/auth/redirect";
vi.mock("@/lib/auth/redirect", async (original) => ({
  ...(await original<typeof import("@/lib/auth/redirect")>()),
  leaveWorkspace: vi.fn(),
}));
afterEach(() => vi.unstubAllGlobals());
it("encodes history parameters and uses cancellable, private cookie reads", async () => {
  const fetcher = vi.fn().mockImplementation(async () => new Response("{}"));
  vi.stubGlobal("fetch", fetcher);
  const signal = new AbortController().signal;
  await getMonitorAnalytics("id", "30d", signal);
  await getMonitorChecks("id", "7d", "opaque+cursor", signal);
  expect(fetcher.mock.calls[0][0]).toBe(
    "/api/v1/monitors/id/analytics?window=30d",
  );
  expect(fetcher.mock.calls[1][0]).toContain("cursor=opaque%2Bcursor");
  expect(fetcher.mock.calls[1][1]).toMatchObject({
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
});
it("redirects expired history sessions and permits only exact detail return paths", async () => {
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
  await expect(getMonitorChecks("id", "24h")).rejects.toMatchObject({
    status: 401,
  });
  expect(leaveWorkspace).toHaveBeenCalledWith("expired");
  const path = "/monitors/00000000-0000-0000-0000-000000000001";
  expect(safeReturnPath(path)).toBe(path);
  expect(safeReturnPath(path + "?next=https://evil.test")).toBe("/dashboard");
  expect(safeReturnPath("/monitors//evil.test")).toBe("/dashboard");
});
