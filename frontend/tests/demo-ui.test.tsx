import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { cloneElement, type ReactElement } from "react";
import { DemoView } from "@/components/public/demo-view";
import { getDemo, type Demo } from "@/lib/api/demo";
import { ApiError } from "@/lib/api/client";
import HomePage from "@/app/page";
import { dashboard } from "./fixtures/dashboard";

vi.mock("@/lib/api/demo", () => ({ getDemo: vi.fn() }));
vi.mock("recharts", async (original) => ({
  ...(await original<typeof import("recharts")>()),
  ResponsiveContainer: ({
    children,
  }: {
    children: ReactElement<{ width: number; height: number }>;
  }) => cloneElement(children, { width: 500, height: 240 }),
}));
const demo: Demo = {
  generated_at: dashboard.end,
  monitors: [
    {
      slug: "exercise",
      label: "Controlled endpoint",
      controlled_failure: true,
      state: "down",
      stale: true,
      last_checked_at: dashboard.end,
      history: dashboard,
      recent_incidents: [
        {
          started_at: dashboard.start,
          confirmed_at: dashboard.start,
          resolved_at: null,
        },
      ],
    },
  ],
};
function mount() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(
    <QueryClientProvider client={client}>
      <DemoView />
    </QueryClientProvider>,
  );
}
beforeEach(() => vi.mocked(getDemo).mockReset().mockResolvedValue(demo));
it("renders published data, labels controlled failures and offers a keyboard-accessible table", async () => {
  mount();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Loading published observations",
  );
  expect(await screen.findByText("75.00%", { selector: "dd" })).toBeVisible();
  expect(screen.getByText(/intentionally induced failures/)).toBeVisible();
  expect(screen.getByText(/Stale observations/)).toBeVisible();
  expect(screen.getByText(/Retries count once/)).toBeVisible();
  expect(screen.getByText("Open", { exact: true })).toBeVisible();
  expect(
    screen.queryByRole("link", { name: /Edit|View incident/ }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("View accessible observation table"));
  expect(screen.getByRole("table")).toBeVisible();
  expect(document.querySelectorAll(".recharts-line")).toHaveLength(2);
});
it("removes old observations when a refresh fails, and retries", async () => {
  vi.mocked(getDemo)
    .mockResolvedValueOnce(demo)
    .mockRejectedValueOnce(new ApiError(503, "unavailable"))
    .mockResolvedValue({ ...demo, monitors: [] });
  mount();
  await screen.findByText("Controlled endpoint");
  await userEvent.click(screen.getByRole("button", { name: "Refresh demo" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "temporarily unavailable",
  );
  expect(screen.queryByText("Controlled endpoint")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(
    await screen.findByText("No monitors are published yet"),
  ).toBeVisible();
});
it("shows no data honestly when the selected window has no observations", async () => {
  vi.mocked(getDemo)
    .mockResolvedValueOnce(demo)
    .mockResolvedValue({
      ...demo,
      monitors: [
        {
          ...demo.monitors[0],
          history: {
            ...dashboard,
            window: "7d",
            buckets: [],
            metrics: {
              ...dashboard.metrics,
              observations: 0,
              successful_runs: 0,
              failed_runs: 0,
              uptime_percent: null,
              mean_latency_ms: null,
              first_observation_at: null,
              last_observation_at: null,
            },
          },
        },
      ],
    });
  mount();
  await screen.findByText("Controlled endpoint");
  await userEvent.selectOptions(screen.getByLabelText("History window"), "7d");
  expect(
    await screen.findByText(/No observations in this window/),
  ).toBeVisible();
  expect(screen.queryByText("75.00%")).not.toBeInTheDocument();
  expect(getDemo).toHaveBeenLastCalledWith("7d", expect.any(AbortSignal));
});
it("connects landing CTAs to signup and identifies screenshots as controlled captures", () => {
  render(<HomePage />);
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Reliability at a glance.",
  );
  expect(
    screen.getByRole("link", { name: "Start monitoring" }),
  ).toHaveAttribute("href", "/register");
  expect(
    screen.getByRole("link", { name: "Explore the read-only demo" }),
  ).toHaveAttribute("href", "/demo");
  expect(screen.getByText(/Static illustration of the product/)).toBeVisible();
  expect(screen.getByRole("img")).toHaveAttribute(
    "alt",
    expect.stringContaining("controlled failure"),
  );
});
