import { act, cleanup, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { usePollingQuery } from "@/lib/use-polling-query";
import { ApiError } from "@/lib/api/client";

let visibility = "visible";
beforeEach(() => {
  vi.useFakeTimers();
  visibility = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(
    () => visibility as DocumentVisibilityState,
  );
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function mount(fetcher: (signal: AbortSignal) => Promise<number>) {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: 0 } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => usePollingQuery(["poll-test"], fetcher), { wrapper });
}
async function hide(value: string) {
  await act(async () => {
    visibility = value;
    document.dispatchEvent(new Event("visibilitychange"));
  });
}
it("polls every 15 seconds, pauses when hidden, resumes, and stops on unmount", async () => {
  const fetcher = vi.fn().mockResolvedValue(1);
  const view = mount(fetcher);
  await advance(1);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await advance(15_000);
  expect(fetcher).toHaveBeenCalledTimes(2);
  await hide("hidden");
  await advance(60_000);
  expect(fetcher).toHaveBeenCalledTimes(2);
  await hide("visible");
  await advance(1);
  expect(fetcher).toHaveBeenCalledTimes(3);
  view.unmount();
  await advance(60_000);
  expect(fetcher).toHaveBeenCalledTimes(3);
});
it("backs off through 30/60/120 seconds and resets after success", async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new Error())
    .mockRejectedValueOnce(new Error())
    .mockRejectedValueOnce(new Error())
    .mockResolvedValue(1);
  mount(fetcher);
  await advance(1);
  await advance(29_000);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await advance(1_001);
  expect(fetcher).toHaveBeenCalledTimes(2);
  await advance(59_000);
  expect(fetcher).toHaveBeenCalledTimes(2);
  await advance(1_001);
  expect(fetcher).toHaveBeenCalledTimes(3);
  await advance(119_000);
  expect(fetcher).toHaveBeenCalledTimes(3);
  await advance(1_001);
  expect(fetcher).toHaveBeenCalledTimes(4);
  await advance(15_001);
  expect(fetcher).toHaveBeenCalledTimes(5);
});
it("does not fetch on a hidden mount or continue polling after session expiry", async () => {
  visibility = "hidden";
  const fetcher = vi
    .fn()
    .mockRejectedValue(new ApiError(401, "authentication_required"));
  mount(fetcher);
  await advance(60_000);
  expect(fetcher).not.toHaveBeenCalled();
  await hide("visible");
  await advance(1);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await advance(300_000);
  expect(fetcher).toHaveBeenCalledTimes(1);
});
it("never overlaps an outstanding request", async () => {
  const fetcher = vi.fn(() => new Promise<number>(() => {}));
  mount(fetcher);
  await advance(120_000);
  expect(fetcher).toHaveBeenCalledTimes(1);
});
