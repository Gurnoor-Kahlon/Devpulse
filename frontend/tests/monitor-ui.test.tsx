import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { AccountContext } from "@/components/auth/session-gate";
import { MonitorForm } from "@/components/monitors/monitor-form";
import { MonitorList } from "@/components/monitors/monitor-list";
import { MonitorEditor } from "@/components/monitors/monitor-editor";
import { ApiError } from "@/lib/api/client";
import {
  createMonitor,
  updateMonitor,
  archiveMonitor,
  listMonitors,
  getMonitor,
  type Monitor,
} from "@/lib/api/monitors";
import { account, monitor } from "./fixtures/monitors";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  usePathname: () => "/monitors",
}));
vi.mock("@/lib/api/monitors", () => ({
  createMonitor: vi.fn(),
  updateMonitor: vi.fn(),
  archiveMonitor: vi.fn(),
  listMonitors: vi.fn(),
  getMonitor: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listMonitors).mockResolvedValue([monitor]);
  vi.mocked(getMonitor).mockResolvedValue(monitor);
});
function mount(element: React.ReactNode, verified = true) {
  const cache = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={cache}>
      <AccountContext.Provider
        value={{
          ...account,
          email_verified_at: verified ? account.email_verified_at : null,
        }}
      >
        {element}
      </AccountContext.Provider>
    </QueryClientProvider>,
  );
  return cache;
}

it("validates required fields and numeric bounds with an accessible focused summary", async () => {
  mount(<MonitorForm />);
  await userEvent.click(screen.getByRole("button", { name: "Create monitor" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
  expect(screen.getByLabelText("Monitor name")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(createMonitor).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Monitor name"), {
    target: { value: "API" },
  });
  fireEvent.change(screen.getByLabelText("URL"), {
    target: { value: "https://example.com/#fragment" },
  });
  fireEvent.change(screen.getByLabelText("Timeout (seconds)"), {
    target: { value: "11" },
  });
  fireEvent.change(screen.getByLabelText("Check interval (seconds)"), {
    target: { value: "59" },
  });
  fireEvent.change(screen.getByLabelText("Expected HTTP status"), {
    target: { value: "199" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Create monitor" }));
  for (const label of [
    "URL",
    "Timeout (seconds)",
    "Check interval (seconds)",
    "Expected HTTP status",
  ])
    expect(screen.getByLabelText(label)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  expect(createMonitor).not.toHaveBeenCalled();
});

it("submits typed settings once and prevents duplicate saves while pending", async () => {
  let finish!: (value: Monitor) => void;
  vi.mocked(createMonitor).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  mount(<MonitorForm />);
  fireEvent.change(screen.getByLabelText("Monitor name"), {
    target: { value: " Payments API " },
  });
  fireEvent.change(screen.getByLabelText("URL"), {
    target: { value: monitor.url },
  });
  await userEvent.selectOptions(screen.getByLabelText("HTTP method"), "HEAD");
  await userEvent.click(screen.getByRole("button", { name: "Create monitor" }));
  expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
  fireEvent.submit(screen.getByRole("form"));
  expect(createMonitor).toHaveBeenCalledTimes(1);
  expect(createMonitor).toHaveBeenCalledWith({
    name: monitor.name,
    url: monitor.url,
    method: "HEAD",
    expected_status: 200,
    timeout_seconds: 5,
    interval_seconds: 60,
    enabled: true,
  });
  await act(async () => finish(monitor));
  await waitFor(() => expect(push).toHaveBeenCalledWith("/monitors"));
});

it("keeps drafts and maps safe server field errors to inputs", async () => {
  vi.mocked(updateMonitor).mockRejectedValue(
    new ApiError(422, "validation_error", [
      {
        field: "body.url",
        code: "invalid_value",
        message: "Enter a valid URL.",
      },
    ]),
  );
  mount(<MonitorForm monitor={monitor} />);
  fireEvent.change(screen.getByLabelText("Monitor name"), {
    target: { value: "My draft" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() =>
    expect(screen.getByLabelText("URL")).toHaveAccessibleDescription(
      /Enter a valid URL/,
    ),
  );
  expect(screen.getByLabelText("Monitor name")).toHaveValue("My draft");
  expect(updateMonitor).toHaveBeenCalledWith(monitor.id, {
    configuration_version: 1,
    name: "My draft",
  });
});

it("requires explicit reload on version conflict before discarding a draft", async () => {
  vi.mocked(updateMonitor).mockRejectedValue(
    new ApiError(409, "configuration_conflict"),
  );
  vi.mocked(getMonitor)
    .mockResolvedValueOnce(monitor)
    .mockResolvedValueOnce({
      ...monitor,
      name: "Server edit",
      configuration_version: 2,
    });
  mount(<MonitorEditor id={monitor.id} />);
  fireEvent.change(await screen.findByLabelText("Monitor name"), {
    target: { value: "Draft" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "replace your unsaved edits",
  );
  expect(screen.getByLabelText("Monitor name")).toHaveValue("Draft");
  expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  await userEvent.click(
    screen.getByRole("button", { name: "Reload latest settings" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Monitor name")).toHaveValue("Server edit"),
  );
  expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
});

it("explains quota failures without navigating or losing input", async () => {
  vi.mocked(updateMonitor).mockRejectedValue(
    new ApiError(409, "enabled_monitor_quota_exceeded"),
  );
  mount(<MonitorForm monitor={{ ...monitor, enabled: false }} />);
  await userEvent.click(screen.getByRole("checkbox", { name: "Enabled" }));
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "100 enabled monitors",
  );
  expect(push).not.toHaveBeenCalled();
});

it("guides unverified users to verification and blocks monitor creation", () => {
  mount(<MonitorForm />, false);
  expect(screen.getByRole("link", { name: "Verify email" })).toHaveAttribute(
    "href",
    "/verify-email",
  );
  expect(screen.getByRole("button", { name: "Create monitor" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "Enabled" })).toBeDisabled();
});

it("searches the complete owned list, filters paused monitors, and shows no invented checks", async () => {
  vi.mocked(listMonitors).mockResolvedValue([
    monitor,
    { ...monitor, id: "second", name: "Catalog", enabled: false },
  ]);
  mount(<MonitorList />);
  await screen.findByRole("article", { name: monitor.name });
  expect(screen.getAllByText("Never checked")).toHaveLength(2);
  expect(screen.getByText("No data")).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Configuration"),
    "paused",
  );
  expect(
    screen.queryByRole("article", { name: monitor.name }),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("article", { name: "Catalog" })).toBeVisible();
  await userEvent.type(screen.getByLabelText("Search monitors"), "missing");
  expect(screen.getByText("No matching monitors")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getAllByRole("article")).toHaveLength(2);
});

it("distinguishes a manual observation from an evaluated health state", async () => {
  vi.mocked(listMonitors).mockResolvedValue([
    { ...monitor, last_completed_check_at: "2026-01-01T00:01:00Z" },
  ]);
  mount(<MonitorList />);
  expect(await screen.findByText("Health not evaluated")).toBeVisible();
  expect(screen.queryByText("No data")).not.toBeInTheDocument();
});

it("retains the saved state when pause fails and shows a recoverable error", async () => {
  vi.mocked(updateMonitor).mockRejectedValue(new ApiError(503, "unavailable"));
  mount(<MonitorList />);
  await userEvent.click(await screen.findByRole("button", { name: "Pause" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("couldn’t reach");
  expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled();
  expect(screen.queryByText("Monitor paused.")).not.toBeInTheDocument();
});

it("offers retry for list failures and shows a genuine empty state", async () => {
  vi.mocked(listMonitors)
    .mockRejectedValueOnce(new ApiError(503, "unavailable"))
    .mockResolvedValueOnce([]);
  mount(<MonitorList />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Try again" }),
  );
  expect(await screen.findByText("No monitors yet")).toBeVisible();
});

it("retains a confirmed pause when the following list refresh fails", async () => {
  vi.mocked(listMonitors)
    .mockResolvedValueOnce([monitor])
    .mockRejectedValue(new ApiError(503, "unavailable"));
  vi.mocked(updateMonitor).mockResolvedValue({
    ...monitor,
    enabled: false,
    configuration_version: 2,
  });
  mount(<MonitorList />);
  await userEvent.click(await screen.findByRole("button", { name: "Pause" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Refresh failed");
  expect(
    within(screen.getByRole("article", { name: monitor.name })).getByText(
      "Paused",
      { exact: true },
    ),
  ).toBeVisible();
  expect(screen.getByRole("button", { name: "Resume" })).toBeEnabled();
});

it("opens archive confirmation on the safe action and restores keyboard focus on Escape", async () => {
  mount(<MonitorList />);
  const trigger = await screen.findByRole("button", {
    name: "Archive",
  });
  await userEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Archive monitor?" });
  expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
  expect(dialog).toHaveTextContent("Stored history is retained");
  await userEvent.keyboard("{Escape}");
  expect(trigger).toHaveFocus();
  expect(archiveMonitor).not.toHaveBeenCalled();
});

it("keeps archive conflicts visible and requires a new review", async () => {
  vi.mocked(archiveMonitor).mockRejectedValue(
    new ApiError(409, "configuration_conflict"),
  );
  mount(<MonitorList />);
  await userEvent.click(await screen.findByRole("button", { name: "Archive" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Archive monitor" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Cancel and refresh",
  );
  expect(
    screen.getByRole("button", { name: "Archive monitor" }),
  ).toBeDisabled();
  expect(screen.getByRole("dialog")).toBeVisible();
});

it("removes archived monitors only after API success", async () => {
  vi.mocked(archiveMonitor).mockResolvedValue();
  vi.mocked(listMonitors)
    .mockResolvedValueOnce([monitor])
    .mockResolvedValue([]);
  mount(<MonitorList />);
  await userEvent.click(await screen.findByRole("button", { name: "Archive" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Archive monitor" }),
  );
  expect(await screen.findByText("No monitors yet")).toBeVisible();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("shows stale observations without claiming target downtime", async () => {
  vi.mocked(listMonitors).mockResolvedValue([
    { ...monitor, observation_status: "stale", current_state: "operational" },
  ]);
  mount(<MonitorList />);
  expect(await screen.findByText("Stale observations")).toBeVisible();
  expect(screen.queryByText("Operational")).not.toBeInTheDocument();
  expect(screen.queryByText("Failing")).not.toBeInTheDocument();
});
