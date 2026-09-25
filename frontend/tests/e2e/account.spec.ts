import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

async function codeFromEmail(
  request: APIRequestContext,
  email: string,
  subject: string,
) {
  const base = "http://127.0.0.1:8025";
  const response = await request.get(`${base}/api/v1/messages`);
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  const found = data.messages.find(
    (message: { Subject: string; To: { Address: string }[] }) =>
      message.Subject === subject &&
      message.To.some((to) => to.Address === email),
  );
  if (!found)
    throw new Error("Expected account email was not delivered to Mailpit.");
  const detail = await (
    await request.get(`${base}/api/v1/message/${found.ID}`)
  ).json();
  const code = detail.Text.match(/[A-Za-z0-9_-]{43}/)?.[0];
  if (!code) throw new Error("The account email has no usable code.");
  return code as string;
}
async function signIn(
  page: Page,
  email: string,
  password: string,
  next = "/dashboard",
) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}

test("account lifecycle uses the API, database, and real email", async ({
  page,
  request,
  browser,
}) => {
  const email = `browser-${crypto.randomUUID()}@example.com`;
  const password = "browser-test-password-1";
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?/);
  await page.getByRole("link", { name: "Create an account" }).click();
  // Login and registration share field labels; wait for the destination form before typing.
  await expect(page).toHaveURL(/\/register$/);
  await expect(
    page.getByRole("heading", { name: "Create your account" }),
  ).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Enter verification code", exact: true })
    .click();
  await page
    .getByLabel("Verification code")
    .fill(await codeFromEmail(request, email, "Verify your DevPulse email"));
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Your email is verified",
  );
  await signIn(page, email, password, "https://evil.example/");
  await expect(page).toHaveURL("http://localhost:3000/dashboard");
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText(email, { exact: true })).toBeVisible();
  const cookies = await page.context().cookies();
  expect(
    cookies
      .filter((cookie) => cookie.name.startsWith("devpulse_"))
      .every((cookie) => cookie.httpOnly && cookie.sameSite === "Lax"),
  ).toBeTruthy();
  await expect(
    page.evaluate(() => document.cookie.includes("devpulse_session")),
  ).resolves.toBeFalsy();

  const recoveryContext = await browser.newContext();
  const recovery = await recoveryContext.newPage();
  try {
    await recovery.goto("http://localhost:3000/forgot-password");
    await recovery.getByLabel("Email address").fill(email);
    await recovery.getByRole("button", { name: "Send reset code" }).click();
    await recovery.getByRole("link", { name: "Enter reset code" }).click();
    await recovery
      .getByLabel("Reset code")
      .fill(
        await codeFromEmail(request, email, "Reset your DevPulse password"),
      );
    await recovery
      .getByLabel("New password", { exact: true })
      .fill("replacement-password-2");
    await recovery
      .getByLabel("Confirm password")
      .fill("replacement-password-2");
    await recovery
      .getByRole("button", { name: "Reset password", exact: true })
      .click();
    await expect(recovery.getByRole("status")).toContainText(
      "existing sessions have been signed out",
    );
    // A real server-side revocation is detected when the existing workspace regains focus.
    await page.bringToFront();
    await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
    await expect(page).toHaveURL(/reason=expired/);
    await signIn(page, email, "replacement-password-2");
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/reason=signed-out/);
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: "Welcome back" }),
    ).toBeVisible();
  } finally {
    await recoveryContext.close();
  }
});

test("resend replaces the old code and unverified accounts see the verification action", async ({
  page,
  request,
}) => {
  const email = `resend-${crypto.randomUUID()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email address").fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("another-browser-password");
  await page.getByLabel("Confirm password").fill("another-browser-password");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("status")).toBeVisible();
  const oldCode = await codeFromEmail(
    request,
    email,
    "Verify your DevPulse email",
  );
  await signIn(page, email, "another-browser-password");
  await page.getByRole("link", { name: "Verify email", exact: true }).click();
  await page
    .getByRole("link", { name: "Request a new code", exact: true })
    .click();
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Send verification code" }).click();
  await page
    .getByRole("link", { name: "Enter verification code", exact: true })
    .first()
    .click();
  await page.getByLabel("Verification code").fill(oldCode);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(
    page.getByRole("form", { name: "Verify your email" }).getByRole("alert"),
  ).toContainText("invalid or has expired");
  await page
    .getByLabel("Verification code")
    .fill(await codeFromEmail(request, email, "Verify your DevPulse email"));
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await page.getByRole("link", { name: "Back to workspace" }).click();
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
});

test("mobile forms support keyboard validation and remain within the viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.goto("/register");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("form", { name: "Create your account" }).getByRole("alert"),
  ).toBeFocused();
  await expect(page.getByLabel("Email address")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({ path: "../.cache/auth-mobile.png", fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/login?next=https%3A%2F%2Fevil.example");
  await page.screenshot({ path: "../.cache/auth-desktop.png", fullPage: true });
});
