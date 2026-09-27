import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { cloneElement, type ReactElement } from "react";
import { MonitorDetail } from "@/components/monitors/monitor-detail";
import { getMonitorAnalytics, getMonitorChecks } from "@/lib/api/monitors";
import { listIncidents } from "@/lib/api/incidents";
import { ApiError } from "@/lib/api/client";
import { analytics, checks } from "./fixtures/monitor-history";
import { incident } from "./fixtures/incidents";
vi.mock("@/lib/api/monitors", () => ({
  getMonitorAnalytics: vi.fn(),
  getMonitorChecks: vi.fn(),
}));
vi.mock("@/lib/api/incidents", () => ({ listIncidents: vi.fn() }));
vi.mock("recharts", async (original) => ({
  ...(await original<typeof import("recharts")>()),
  ResponsiveContainer: ({
    children,
  }: {
    children: ReactElement<{ width: number; height: number }>;
  }) => cloneElement(children, { width: 500, height: 240 }),
}));
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <MonitorDetail id={analytics.monitor.id} />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.mocked(getMonitorAnalytics).mockReset().mockResolvedValue(analytics);
  vi.mocked(getMonitorChecks).mockReset().mockResolvedValue(checks);
  vi.mocked(listIncidents)
    .mockReset()
    .mockResolvedValue({ items: [incident], next_cursor: null });
});
it("shows scoped metrics, real latency chart, statuses and expandable safe evidence", async () => {
  mount();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Loading monitor history",
  );
  expect(
    await screen.findByRole("heading", {
      level: 1,
      name: analytics.monitor.name,
    }),
  ).toBeVisible();
  expect(screen.getByText("75.00%", { selector: "dd" })).toBeVisible();
  expect(document.querySelectorAll(".recharts-line")).toHaveLength(1);
  expect(
    within(
      screen.getByRole("region", { name: "HTTP status distribution" }),
    ).getByText("HTTP 503"),
  ).toBeVisible();
  await userEvent.click(await screen.findByText(/Attempt 3 · failure/));
  expect(
    screen.getByText(checks.items[0].error_message!, { exact: false }),
  ).toBeVisible();
  expect(screen.getByText("Final stored attempt")).toBeVisible();
  expect(screen.getByRole("link", { name: "Edit settings" })).toHaveAttribute(
    "href",
    `/monitors/${analytics.monitor.id}/edit`,
  );
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  await waitFor(() =>
    expect(listIncidents).toHaveBeenCalledWith(
      expect.objectContaining({ monitorId: analytics.monitor.id }),
      expect.any(AbortSignal),
    ),
  );
});
it("paginates checks and resets their cursor on window changes", async () => {
  vi.mocked(getMonitorChecks).mockResolvedValue({
    ...checks,
    next_cursor: "cursor-older",
  });
  mount();
  await userEvent.click(
    await screen.findByRole("button", { name: "Older checks" }),
  );
  await waitFor(() =>
    expect(getMonitorChecks).toHaveBeenLastCalledWith(
      analytics.monitor.id,
      "24h",
      "cursor-older",
      expect.any(AbortSignal),
    ),
  );
  await userEvent.selectOptions(screen.getByLabelText("History window"), "7d");
  await waitFor(() =>
    expect(getMonitorChecks).toHaveBeenLastCalledWith(
      analytics.monitor.id,
      "7d",
      undefined,
      expect.any(AbortSignal),
    ),
  );
  expect(getMonitorAnalytics).toHaveBeenLastCalledWith(
    analytics.monitor.id,
    "7d",
    expect.any(AbortSignal),
  );
});
it("keeps archive history read-only and distinguishes missing raw checks from retained incidents", async () => {
  vi.mocked(getMonitorAnalytics).mockResolvedValue({
    ...analytics,
    archived_at: analytics.end,
    metrics: {
      ...analytics.metrics,
      observations: 0,
      uptime_percent: null,
      mean_latency_ms: null,
      response_count: 0,
    },
    status_distribution: [],
  });
  vi.mocked(getMonitorChecks).mockResolvedValue({ ...checks, items: [] });
  mount();
  expect(await screen.findByText(/Archived · read-only history/)).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "Edit settings" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("No response latency data")).toBeVisible();
  expect(
    await screen.findByText("No retained checks in this window"),
  ).toBeVisible();
  expect(
    await screen.findByRole("link", { name: incident.monitor_name }),
  ).toBeVisible();
});
it("retains data with explicit independent refresh errors", async () => {
  vi.mocked(getMonitorAnalytics)
    .mockResolvedValueOnce(analytics)
    .mockRejectedValue(new ApiError(503, "unavailable"));
  vi.mocked(getMonitorChecks)
    .mockResolvedValueOnce(checks)
    .mockRejectedValue(new ApiError(503, "unavailable"));
  mount();
  await userEvent.click(
    await screen.findByRole("button", { name: "Refresh analytics" }),
  );
  expect(await screen.findByText(/Analytics refresh failed/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Refresh checks" }));
  expect(await screen.findByText(/Check refresh failed/)).toBeVisible();
  expect(screen.getByText("75.00%", { selector: "dd" })).toBeVisible();
});
it("handles unavailable monitors and initial errors", async () => {
  vi.mocked(getMonitorAnalytics)
    .mockRejectedValueOnce(new ApiError(503, "unavailable"))
    .mockRejectedValue(new ApiError(404, "monitor_not_found"));
  mount();
  await userEvent.click(
    await screen.findByRole("button", { name: "Try again" }),
  );
  expect(await screen.findByText("Monitor unavailable")).toBeVisible();
  expect(getMonitorChecks).not.toHaveBeenCalled();
});
