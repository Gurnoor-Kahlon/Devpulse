import { afterEach, expect, it, vi } from "vitest";
import { getDashboard } from "@/lib/api/dashboard";
import { leaveWorkspace } from "@/lib/auth/redirect";
vi.mock("@/lib/auth/redirect", () => ({ leaveWorkspace: vi.fn() }));
afterEach(() => vi.unstubAllGlobals());
it("reads the selected window with same-origin credentials, no caching, and cancellation", async () => {
  const fetcher = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetcher);
  const signal = new AbortController().signal;
  await getDashboard("30d", signal);
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/dashboard?window=30d");
  expect(fetcher.mock.calls[0][1]).toMatchObject({
    credentials: "same-origin",
    cache: "no-store",
    signal,
  });
});
it("redirects an expired dashboard session", async () => {
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
  await expect(getDashboard("24h")).rejects.toMatchObject({ status: 401 });
  expect(leaveWorkspace).toHaveBeenCalledWith("expired");
});
