import { test, expect } from "@playwright/test";

test("public demo uses real probes, supports mobile and keyboard access, and links to verified signup", async ({
  page,
  request,
}, testInfo) => {
  test.skip(
    process.env.TEST_DEMO_FIXTURES !== "1",
    "Requires the isolated real-probe publication fixture and local Mailpit.",
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const html = await (await request.get("/")).text();
  expect(html).toContain("Reliability at a glance.");
  expect(html).toContain('href="/register"');
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("img")).toHaveJSProperty("complete", true);
  await expect
    .poll(() =>
      page
        .getByRole("img")
        .evaluate((image) => (image as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByRole("link", { name: "Explore the read-only demo" }).click();
  await expect(
    page.getByText("Controlled HTTP endpoint", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("dd").filter({ hasText: "33.33%" })).toBeVisible();
  await expect(page.getByText(/intentionally induced failures/)).toBeVisible();
  const initial = await (await request.get("/api/v1/demo")).json();
  expect(initial.monitors[0].history.metrics.observations).toBe(3);
  expect(initial.monitors[0].recent_incidents).toHaveLength(2);
  expect(JSON.stringify(initial)).not.toMatch(
    /incident-browser|127\.0\.0\.1|password|monitor_id|user_id|opening_evidence/,
  );
  expect((await request.get("/api/v1/monitors")).status()).toBe(401);
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await expect(page.locator(".recharts-line")).toHaveCount(2);
    await page.screenshot({
      path: testInfo.outputPath(`demo-${width}.png`),
      fullPage: true,
    });
  }
  const summary = page.getByText("View accessible observation table");
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBeTruthy();
  await page.getByLabel("History window").selectOption("7d");
  await expect
    .poll(
      async () =>
        (await (await request.get("/api/v1/demo?window=7d")).json()).monitors[0]
          .history.window,
    )
    .toBe("7d");
  await page.getByRole("button", { name: "Refresh demo" }).click();
  expect((await request.post("/api/v1/demo", { data: {} })).status()).toBe(405);
  const after = await (await request.get("/api/v1/demo")).json();
  expect(after.monitors[0].history.metrics.observations).toBe(3);
  await page.getByRole("link", { name: "DevPulse home" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Reliability at a glance.",
  );
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.screenshot({
      path: testInfo.outputPath(`landing-${width}.png`),
      fullPage: true,
    });
  }
  await page.getByRole("link", { name: "Start monitoring" }).click();
  await expect(
    page.getByRole("heading", { name: "Create your account" }),
  ).toBeVisible();
  const email = `demo-signup-${crypto.randomUUID()}@example.com`;
  const password = "demo-browser-password-17";
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page
    .getByRole("link", { name: "Enter verification code", exact: true })
    .click();
  const messages = await (
    await request.get("http://127.0.0.1:8025/api/v1/messages")
  ).json();
  const message = messages.messages.find(
    (m: { Subject: string; To: { Address: string }[] }) =>
      m.Subject === "Verify your DevPulse email" &&
      m.To.some((to) => to.Address === email),
  );
  expect(message).toBeTruthy();
  const detail = await (
    await request.get(`http://127.0.0.1:8025/api/v1/message/${message.ID}`)
  ).json();
  const token = detail.Text.match(/[A-Za-z0-9_-]{43}/)?.[0];
  if (!token) throw new Error("Verification email did not contain a code.");
  await page.getByLabel("Verification code").fill(token);
  await page.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Your email is verified",
  );
  await page.getByRole("link", { name: "Continue to sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
  await page.goto("/monitors/new");
  await expect(
    page.getByRole("heading", { name: "Create monitor" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
