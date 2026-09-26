import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { cloneElement, type ReactElement } from "react";
import { DashboardView } from "@/components/dashboard/dashboard-view";
import { getDashboard } from "@/lib/api/dashboard";
import { ApiError } from "@/lib/api/client";
import { dashboard } from "./fixtures/dashboard";

vi.mock("@/lib/api/dashboard", () => ({ getDashboard: vi.fn() }));
// jsdom has no layout; exercise real Recharts using a deterministic container size.
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
      <DashboardView />
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.mocked(getDashboard).mockReset().mockResolvedValue(dashboard);
});
it("renders stored aggregates, real chart series, coverage and incident navigation", async () => {
  mount();
  expect(screen.getByRole("status")).toHaveTextContent("Loading overview");
  expect(await screen.findByText("75.00%", { selector: "dd" })).toBeVisible();
  expect(screen.getByText(/Retries count once/)).toBeVisible();
  expect(screen.getByText(/3 unarchived monitors · 1 stale/)).toBeVisible();
  expect(screen.getByText(/Partial history/)).toBeVisible();
  expect(
    screen.getByRole("link", {
      name: dashboard.recent_incidents[0].monitor_name,
    }),
  ).toHaveAttribute("href", `/incidents/${dashboard.recent_incidents[0].id}`);
  expect(document.querySelectorAll(".recharts-line").length).toBe(2);
  await userEvent.click(screen.getByText("View bucket observations"));
  expect(screen.getByRole("table")).toBeVisible();
});
it("shows no data instead of perfect uptime and never carries old data across windows", async () => {
  vi.mocked(getDashboard)
    .mockResolvedValueOnce(dashboard)
    .mockResolvedValue({
      ...dashboard,
      window: "7d",
      metrics: {
        ...dashboard.metrics,
        successful_runs: 0,
        failed_runs: 0,
        observations: 0,
        uptime_percent: null,
        mean_latency_ms: null,
        first_observation_at: null,
        last_observation_at: null,
      },
      buckets: [],
    });
  mount();
  await screen.findByText("75.00%", { selector: "dd" });
  await userEvent.selectOptions(screen.getByLabelText("History window"), "7d");
  expect(
    await screen.findByText("No observations in this window"),
  ).toBeVisible();
  expect(screen.queryByText("75.00%")).not.toBeInTheDocument();
  expect(screen.getAllByText("No data")).toHaveLength(2);
  expect(getDashboard).toHaveBeenLastCalledWith("7d", expect.any(AbortSignal));
});
it("keeps cached observations with an explicit refresh failure", async () => {
  vi.mocked(getDashboard)
    .mockResolvedValueOnce(dashboard)
    .mockRejectedValue(new ApiError(503, "unavailable"));
  mount();
  await screen.findByText("75.00%", { selector: "dd" });
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh overview" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Showing the last loaded overview",
  );
  expect(screen.getByText("75.00%", { selector: "dd" })).toBeVisible();
});
it("offers retry for an initial service error", async () => {
  vi.mocked(getDashboard).mockRejectedValueOnce(
    new ApiError(503, "unavailable"),
  );
  mount();
  await userEvent.click(
    await screen.findByRole("button", { name: "Try again" }),
  );
  await waitFor(() =>
    expect(screen.getByText("75.00%", { selector: "dd" })).toBeVisible(),
  );
});
