import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { AssertionEditor } from "@/components/monitors/assertion-editor";
import { AssertionEvidence } from "@/components/monitors/assertion-evidence";
import {
  getAssertions,
  replaceAssertions,
  type AssertionPage,
} from "@/lib/api/monitors";
import { ApiError } from "@/lib/api/client";
import { monitor } from "./fixtures/monitors";

vi.mock("@/lib/api/monitors", () => ({
  getAssertions: vi.fn(),
  replaceAssertions: vi.fn(),
}));
const page: AssertionPage = {
  monitor_id: monitor.id,
  method: "GET",
  configuration_version: 4,
  items: [{ id: "a", kind: "json_equals", pointer: "/ok", expected: true }],
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getAssertions).mockResolvedValue(page);
  vi.mocked(replaceAssertions).mockResolvedValue({
    ...page,
    configuration_version: 5,
  });
});
function mount() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false, gcTime: 0 } },
        })
      }
    >
      <AssertionEditor id={monitor.id} />
    </QueryClientProvider>,
  );
}

it("saves typed JSON values and advances the configuration version for later saves", async () => {
  mount();
  fireEvent.change(await screen.findByLabelText(/^Expected JSON value/), {
    target: { value: "null" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save assertions" }),
  );
  await screen.findByText(/Assertions saved/);
  expect(replaceAssertions).toHaveBeenLastCalledWith(monitor.id, {
    configuration_version: 4,
    items: [{ kind: "json_equals", pointer: "/ok", expected: null }],
  });
  fireEvent.change(screen.getByLabelText(/^Expected JSON value/), {
    target: { value: '"healthy"' },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save assertions" }),
  );
  await waitFor(() =>
    expect(replaceAssertions).toHaveBeenLastCalledWith(monitor.id, {
      configuration_version: 5,
      items: [{ kind: "json_equals", pointer: "/ok", expected: "healthy" }],
    }),
  );
});

it("rejects compound JSON and bounds before submission", async () => {
  mount();
  const input = await screen.findByLabelText(/^Expected JSON value/);
  for (const value of [
    "{}",
    "[]",
    "1e999",
    "9007199254740992",
    '"' + "x".repeat(1025) + '"',
  ]) {
    fireEvent.change(input, { target: { value } });
    await userEvent.click(
      screen.getByRole("button", { name: "Save assertions" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("valid JSON scalar");
  }
  expect(replaceAssertions).not.toHaveBeenCalled();
});

it("preserves edits on conflict and reloads explicitly", async () => {
  vi.mocked(replaceAssertions).mockRejectedValue(
    new ApiError(409, "configuration_conflict"),
  );
  mount();
  fireEvent.change(await screen.findByLabelText(/^Expected JSON value/), {
    target: { value: "false" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save assertions" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Your edits are preserved",
  );
  expect(screen.getByLabelText(/^Expected JSON value/)).toHaveValue("false");
  expect(
    screen.getByRole("button", { name: "Save assertions" }),
  ).toBeDisabled();
  vi.mocked(getAssertions).mockResolvedValue({
    ...page,
    configuration_version: 8,
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Reload saved assertions" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText(/^Expected JSON value/)).toHaveValue("true"),
  );
});

it("keeps edits on reload failure and shows safe unknown-save errors", async () => {
  mount();
  fireEvent.change(await screen.findByLabelText(/^Expected JSON value/), {
    target: { value: "false" },
  });
  vi.mocked(getAssertions).mockRejectedValue(new Error("secret"));
  await userEvent.click(
    screen.getByRole("button", { name: "Reload saved assertions" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not reload assertions",
  );
  expect(screen.getByLabelText(/^Expected JSON value/)).toHaveValue("false");
  vi.mocked(replaceAssertions).mockRejectedValue(new Error("secret"));
  await userEvent.click(
    screen.getByRole("button", { name: "Save assertions" }),
  );
  await screen.findByText(/Could not confirm the save/);
  expect(screen.queryByText("secret")).not.toBeInTheDocument();
});

it("switches to raw text, removes definitions, and caps the editor at ten", async () => {
  mount();
  await userEvent.selectOptions(
    await screen.findByLabelText("Type"),
    "text_contains",
  );
  expect(screen.queryByLabelText(/^JSON Pointer/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText(/^Expected text/), {
    target: { value: "healthy" },
  });
  await userEvent.click(
    screen.getByRole("button", { name: "Save assertions" }),
  );
  await waitFor(() =>
    expect(replaceAssertions).toHaveBeenLastCalledWith(monitor.id, {
      configuration_version: 4,
      items: [{ kind: "text_contains", pointer: "", expected: "healthy" }],
    }),
  );
  for (let i = 1; i < 10; i++)
    await userEvent.click(
      screen.getByRole("button", { name: "Add assertion" }),
    );
  expect(screen.getByRole("button", { name: "Add assertion" })).toBeDisabled();
  await userEvent.click(
    screen.getByRole("button", { name: /^Remove assertion 1$/ }),
  );
  expect(screen.getByRole("button", { name: "Add assertion" })).toBeEnabled();
});

it("does not offer body assertions for HEAD monitors", async () => {
  vi.mocked(getAssertions).mockResolvedValue({
    ...page,
    method: "HEAD",
    items: [],
  });
  mount();
  expect(
    await screen.findByRole("button", { name: "Add assertion" }),
  ).toBeDisabled();
  expect(screen.getByText(/Body assertions require GET/)).toBeInTheDocument();
});

it("renders captured definitions and missing historical snapshots honestly", () => {
  const { rerender } = render(<AssertionEvidence results={[]} />);
  expect(screen.getByText(/No assertion snapshots/)).toBeInTheDocument();
  rerender(
    <AssertionEvidence
      results={[
        {
          definition: page.items[0],
          status: "failed",
          reason: "value_mismatch",
        },
      ]}
    />,
  );
  expect(
    screen.getByText("Failed · Value or type did not match"),
  ).toBeInTheDocument();
  expect(screen.getByText("Expected: true")).toBeInTheDocument();
  expect(
    screen.getByText(/Actual response values are not retained/),
  ).toBeInTheDocument();
});
