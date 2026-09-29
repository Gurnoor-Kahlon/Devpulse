import { afterEach, expect, it, vi } from "vitest";
import { getDemo } from "@/lib/api/demo";

afterEach(() => vi.unstubAllGlobals());
it("reads only the bounded public endpoint without a CSRF bootstrap or private request", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ monitors: [] }), { status: 200 }),
    );
  vi.stubGlobal("fetch", fetcher);
  await getDemo("30d");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/demo?window=30d",
    expect.objectContaining({ cache: "no-store", credentials: "same-origin" }),
  );
});
