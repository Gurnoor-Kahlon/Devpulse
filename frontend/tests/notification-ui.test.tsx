import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { NotificationSettings } from "@/components/notifications/notification-settings";
import { DeliveryList } from "@/components/notifications/delivery-list";
import { ApiError } from "@/lib/api/client";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
  getDeliveries,
  type NotificationPreferences,
  type Delivery,
} from "@/lib/api/notifications";

vi.mock("@/lib/api/notifications", () => ({
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
  getDeliveries: vi.fn(),
}));
const preferences: NotificationPreferences = {
  enabled: false,
  on_open: true,
  on_recovery: true,
  configuration_version: 0,
  destination: "owner@example.com",
  verified: true,
};
const delivered: Delivery = {
  id: "00000000-0000-0000-0000-000000000001",
  incident_id: "00000000-0000-0000-0000-000000000002",
  transition: "opened",
  status: "sent",
  attempt_count: 1,
  created_at: "2026-09-28T12:00:00Z",
  completed_at: "2026-09-28T12:00:01Z",
  next_attempt_at: null,
  last_error_code: null,
  cancel_requested: false,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getNotificationPreferences).mockResolvedValue(preferences);
  vi.mocked(updateNotificationPreferences).mockResolvedValue({
    ...preferences,
    enabled: true,
    configuration_version: 1,
  });
  vi.mocked(getDeliveries).mockResolvedValue({ items: [], next_cursor: null });
});
function mount(element = <NotificationSettings />) {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      {element}
    </QueryClientProvider>,
  );
}

it("loads opt-in preferences and sends explicit typed choices", async () => {
  mount();
  const enabled = await screen.findByLabelText("Enable incident email");
  expect(enabled).not.toBeChecked();
  await userEvent.click(enabled);
  await userEvent.click(
    screen.getByLabelText("Email when recovery is observed"),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save preferences" }),
  );
  await screen.findByText("Notification preferences saved.");
  expect(updateNotificationPreferences).toHaveBeenLastCalledWith({
    configuration_version: 0,
    enabled: true,
    on_open: true,
    on_recovery: false,
  });
  await userEvent.click(screen.getByLabelText("Enable incident email"));
  await userEvent.click(
    screen.getByRole("button", { name: "Save preferences" }),
  );
  await waitFor(() =>
    expect(updateNotificationPreferences).toHaveBeenLastCalledWith({
      configuration_version: 1,
      enabled: false,
      on_open: true,
      on_recovery: false,
    }),
  );
});

it("requires email verification and exposes only the account destination", async () => {
  vi.mocked(getNotificationPreferences).mockResolvedValue({
    ...preferences,
    verified: false,
  });
  mount();
  expect(await screen.findByLabelText("Enable incident email")).toBeDisabled();
  expect(screen.getByRole("link", { name: "Verify email" })).toHaveAttribute(
    "href",
    "/verify-email",
  );
  expect(
    screen.getByText("Destination: owner@example.com"),
  ).toBeInTheDocument();
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
});

it("preserves a conflicting draft until an explicit reload", async () => {
  vi.mocked(updateNotificationPreferences).mockRejectedValue(
    new ApiError(409, "configuration_conflict"),
  );
  mount();
  await userEvent.click(await screen.findByLabelText("Enable incident email"));
  await userEvent.click(
    screen.getByRole("button", { name: "Save preferences" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Your edits are preserved",
  );
  expect(screen.getByLabelText("Enable incident email")).toBeChecked();
  expect(
    screen.getByRole("button", { name: "Save preferences" }),
  ).toBeDisabled();
  vi.mocked(getNotificationPreferences).mockResolvedValue({
    ...preferences,
    configuration_version: 2,
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Reload saved preferences" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Enable incident email")).not.toBeChecked(),
  );
});

it("prevents duplicate saves and explains uncertain network writes", async () => {
  let reject!: (error: Error) => void;
  vi.mocked(updateNotificationPreferences).mockImplementation(
    () =>
      new Promise((_, no) => {
        reject = no;
      }),
  );
  mount();
  await userEvent.click(await screen.findByLabelText("Enable incident email"));
  await userEvent.click(
    screen.getByRole("button", { name: "Save preferences" }),
  );
  expect(
    screen.getByRole("button", { name: "Save preferences" }),
  ).toBeDisabled();
  expect(screen.getByLabelText("Enable incident email")).toBeDisabled();
  reject(new Error("secret-server-error"));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not confirm the save",
  );
  expect(screen.queryByText("secret-server-error")).not.toBeInTheDocument();
});

it("retains edits if reloading fails", async () => {
  mount();
  fireEvent.click(await screen.findByLabelText("Enable incident email"));
  vi.mocked(getNotificationPreferences).mockRejectedValue(new Error("network"));
  await userEvent.click(
    screen.getByRole("button", { name: "Reload saved preferences" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reload preferences",
  );
  expect(screen.getByLabelText("Enable incident email")).toBeChecked();
});

it("shows honest delivery states, safe failure reasons, and paging", async () => {
  vi.mocked(getDeliveries)
    .mockResolvedValueOnce({ items: [delivered], next_cursor: "older" })
    .mockResolvedValue({
      items: [
        {
          ...delivered,
          status: "failed",
          last_error_code: "delivery_unknown",
          attempt_count: 5,
        },
      ],
      next_cursor: null,
    });
  mount(<DeliveryList />);
  expect(await screen.findByText("Accepted by SMTP")).toBeInTheDocument();
  expect(
    screen.getByText(/not that it reached your inbox/),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View incident" })).toHaveAttribute(
    "href",
    `/incidents/${delivered.incident_id}`,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Older deliveries" }),
  );
  expect(await screen.findByText(/Acceptance is unknown/)).toBeInTheDocument();
  expect(screen.getByText(/5 of 5 attempts/)).toBeInTheDocument();
  expect(getDeliveries).toHaveBeenLastCalledWith(
    { incidentId: undefined, cursor: "older" },
    expect.any(AbortSignal),
  );
});

it("shows in-flight cancellation without claiming an email can be recalled", async () => {
  vi.mocked(getDeliveries).mockResolvedValue({
    items: [
      {
        ...delivered,
        status: "sending",
        completed_at: null,
        cancel_requested: true,
      },
    ],
    next_cursor: null,
  });
  mount(<DeliveryList incidentId={delivered.incident_id} />);
  expect(
    await screen.findByText(/current send may already have been accepted/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "View incident" }),
  ).not.toBeInTheDocument();
});
