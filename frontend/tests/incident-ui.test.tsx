import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { IncidentList } from "@/components/incidents/incident-list";
import { IncidentDetailView } from "@/components/incidents/incident-detail";
import { getIncident, listIncidents } from "@/lib/api/incidents";
import { ApiError } from "@/lib/api/client";
import { incident } from "./fixtures/incidents";

vi.mock("@/lib/api/incidents", () => ({
  getIncident: vi.fn(),
  listIncidents: vi.fn(),
}));
function mount(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
beforeEach(() => {
  vi.mocked(listIncidents)
    .mockReset()
    .mockResolvedValue({ items: [incident], next_cursor: null });
  vi.mocked(getIncident).mockReset().mockResolvedValue(incident);
});
it("announces loading and an honest empty incident list", async () => {
  vi.mocked(listIncidents).mockResolvedValue({ items: [], next_cursor: null });
  mount(<IncidentList />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading incidents");
  expect(await screen.findByText("No incidents found")).toBeVisible();
  expect(
    screen.getByText(/does not imply uninterrupted availability/),
  ).toBeVisible();
});
it("paginates and resets the cursor when the status filter changes", async () => {
  vi.mocked(listIncidents).mockResolvedValueOnce({
    items: [incident],
    next_cursor: "next-page",
  });
  mount(<IncidentList monitorId={incident.monitor_id} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Older incidents" }),
  );
  await waitFor(() =>
    expect(listIncidents).toHaveBeenLastCalledWith(
      {
        monitorId: incident.monitor_id,
        status: undefined,
        cursor: "next-page",
      },
      expect.any(AbortSignal),
    ),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Incident status"),
    "open",
  );
  await waitFor(() =>
    expect(listIncidents).toHaveBeenLastCalledWith(
      { monitorId: incident.monitor_id, status: "open", cursor: undefined },
      expect.any(AbortSignal),
    ),
  );
  expect(
    screen.getByRole("link", { name: "Show all incidents" }),
  ).toHaveAttribute("href", "/incidents");
});
it("preserves loaded incidents on a refresh failure", async () => {
  vi.mocked(listIncidents)
    .mockResolvedValueOnce({ items: [incident], next_cursor: null })
    .mockRejectedValue(new ApiError(503, "unavailable"));
  mount(<IncidentList />);
  await screen.findByRole("link", { name: incident.monitor_name });
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh incidents" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent("Refresh failed");
  expect(
    screen.getByRole("link", { name: incident.monitor_name }),
  ).toBeVisible();
});
it("renders retained evidence after raw check references are removed", async () => {
  mount(<IncidentDetailView id={incident.id} />);
  expect(
    await screen.findByRole("heading", { name: incident.monitor_name }),
  ).toBeVisible();
  expect(
    within(screen.getByRole("region", { name: "Opening evidence" })).getByText(
      "HTTP 503",
    ),
  ).toBeVisible();
  expect(
    within(
      screen.getByRole("region", { name: "Confirmation evidence" }),
    ).getByText("3"),
  ).toBeVisible();
  expect(
    within(screen.getByRole("region", { name: "Recovery evidence" })).getByText(
      "HTTP 200",
    ),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /resolve/i }),
  ).not.toBeInTheDocument();
});
it("shows an open incident without inventing recovery", async () => {
  vi.mocked(getIncident).mockResolvedValue({
    ...incident,
    status: "open",
    resolved_at: null,
    recovery_evidence: null,
  });
  mount(<IncidentDetailView id={incident.id} />);
  expect(
    await screen.findByText("Open incident · recovery not observed"),
  ).toBeVisible();
  expect(
    screen.queryByRole("region", { name: "Recovery evidence" }),
  ).not.toBeInTheDocument();
});
it("handles unavailable incidents and offers retry for service errors", async () => {
  vi.mocked(getIncident)
    .mockRejectedValueOnce(new ApiError(503, "unavailable"))
    .mockRejectedValueOnce(new ApiError(404, "incident_not_found"));
  mount(<IncidentDetailView id={incident.id} />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Try again" }),
  );
  expect(await screen.findByText("Incident unavailable")).toBeVisible();
});
