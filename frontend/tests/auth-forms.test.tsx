import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthForm } from "@/components/auth/auth-form";
import { SessionGate } from "@/components/auth/session-gate";
import { ApiError, authPost, getMe } from "@/lib/api/client";
import { goToWorkspace, leaveWorkspace } from "@/lib/auth/redirect";

vi.mock("@/lib/api/client", async (original) => ({
  ...(await original<typeof import("@/lib/api/client")>()),
  authPost: vi.fn(),
  getMe: vi.fn(),
}));
vi.mock("@/lib/auth/redirect", async (original) => ({
  ...(await original<typeof import("@/lib/auth/redirect")>()),
  goToWorkspace: vi.fn(),
  leaveWorkspace: vi.fn(),
}));
beforeEach(() => {
  vi.mocked(authPost).mockReset();
  vi.mocked(getMe).mockReset();
  vi.mocked(goToWorkspace).mockClear();
  vi.mocked(leaveWorkspace).mockClear();
});
function mount(element: React.ReactNode) {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(<QueryClientProvider client={cache}>{element}</QueryClientProvider>);
  return cache;
}

it("links validation errors and focuses the summary without making a request", async () => {
  mount(<AuthForm mode="register" />);
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(authPost).not.toHaveBeenCalled();
  await waitFor(() => expect(screen.getByRole("alert")).toHaveFocus());
  expect(screen.getByLabelText("Email address")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(
    screen.getByLabelText("Password", { exact: true }),
  ).toHaveAccessibleDescription(/12–128/);
});

it("preserves password characters and reports a mismatch before submitting", async () => {
  mount(<AuthForm mode="register" />);
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "user@example.com",
  );
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "  secret-password  ",
  );
  await userEvent.type(
    screen.getByLabelText("Confirm password"),
    "secret-password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByLabelText("Confirm password")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(authPost).not.toHaveBeenCalled();
});

it("prevents repeated submissions and provides the verification continuation", async () => {
  let resolve!: (result: { message: string }) => void;
  vi.mocked(authPost).mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const cache = mount(<AuthForm mode="register" />);
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "user@example.com",
  );
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "  secret-password  ",
  );
  await userEvent.type(
    screen.getByLabelText("Confirm password"),
    "  secret-password  ",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  await waitFor(() =>
    expect(authPost).toHaveBeenCalledWith("/api/v1/auth/register", {
      email: "user@example.com",
      password: "  secret-password  ",
    }),
  );
  expect(
    screen.getByRole("button", { name: "Creating account…" }),
  ).toBeDisabled();
  expect(cache.getMutationCache().getAll()[0].state.variables).toBeUndefined();
  resolve({ message: "accepted" });
  expect(
    await screen.findByRole("link", { name: "Enter verification code" }),
  ).toHaveAttribute("href", "/verify-email");
  expect(
    screen.queryByLabelText("Password", { exact: true }),
  ).not.toBeInTheDocument();
});

it("presents safe login failures and allows a successful retry", async () => {
  vi.mocked(authPost)
    .mockRejectedValueOnce(new ApiError(401, "invalid_credentials"))
    .mockResolvedValueOnce({
      id: "id",
      email: "user@example.com",
      email_verified_at: null,
    });
  mount(<AuthForm mode="login" />);
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "user@example.com",
  );
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Email or password is incorrect",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(goToWorkspace).toHaveBeenCalledWith("/dashboard"));
});

it("explains a rejected code without putting it in a URL", async () => {
  vi.mocked(authPost).mockRejectedValue(new ApiError(400, "invalid_token"));
  mount(<AuthForm mode="verify" />);
  await userEvent.type(
    screen.getByLabelText("Verification code"),
    "a".repeat(43),
  );
  await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "invalid or has expired",
  );
  expect(
    screen.getByRole("link", { name: "Request a new code" }),
  ).toHaveAttribute("href", "/resend-verification");
});

it("clears prior session cache after password reset and offers sign-in", async () => {
  vi.mocked(authPost).mockResolvedValue({ message: "reset" });
  const cache = mount(<AuthForm mode="reset" />);
  cache.setQueryData(["session"], { id: "old" });
  await userEvent.type(screen.getByLabelText("Reset code"), "a".repeat(43));
  await userEvent.type(
    screen.getByLabelText("New password"),
    "new-example-password",
  );
  await userEvent.type(
    screen.getByLabelText("Confirm password"),
    "new-example-password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Reset password" }));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "existing sessions have been signed out",
  );
  expect(cache.getQueryData(["session"])).toBeUndefined();
});

const account = {
  id: "account",
  email: "user@example.com",
  email_verified_at: null,
};
it("hides private content and redirects when a session is rejected", async () => {
  vi.mocked(getMe).mockRejectedValue(
    new ApiError(401, "authentication_required"),
  );
  mount(
    <SessionGate initialUser={account}>
      <p>Private workspace</p>
    </SessionGate>,
  );
  await waitFor(() => expect(leaveWorkspace).toHaveBeenCalledWith("expired"));
  expect(screen.queryByText("Private workspace")).not.toBeInTheDocument();
});

it("offers retry for an outage without claiming the user is signed out", async () => {
  vi.mocked(getMe)
    .mockRejectedValueOnce(new ApiError(503, "unavailable"))
    .mockResolvedValue(account);
  mount(
    <SessionGate initialUser={account}>
      <p>Private workspace</p>
    </SessionGate>,
  );
  await screen.findByRole("alert");
  expect(leaveWorkspace).not.toHaveBeenCalled();
  await userEvent.click(
    screen.getByRole("button", { name: "Retry session check" }),
  );
  expect(await screen.findByText("Private workspace")).toBeVisible();
  expect(screen.getByRole("link", { name: "Verify email" })).toHaveAttribute(
    "href",
    "/verify-email",
  );
});

it("preserves an unsaved draft while the session refreshes and when refresh fails", async () => {
  let fail!: (error: Error) => void;
  vi.mocked(getMe).mockImplementation(
    () =>
      new Promise((_, reject) => {
        fail = reject;
      }),
  );
  mount(
    <SessionGate initialUser={account}>
      <input aria-label="Draft" defaultValue="Original" />
    </SessionGate>,
  );
  await userEvent.clear(screen.getByLabelText("Draft"));
  await userEvent.type(screen.getByLabelText("Draft"), "Unsaved edit");
  await act(async () => fail(new ApiError(503, "unavailable")));
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Draft")).toHaveValue("Unsaved edit");
});
