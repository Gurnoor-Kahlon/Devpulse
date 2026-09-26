import { test, expect } from "@playwright/test";

test("dashboard shows real weighted runs, responsive charts, polling and retained failures", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.TEST_DASHBOARD_FIXTURES !== "1",
    "Requires isolated real-probe dashboard fixtures.",
  );
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/login?next=%2Fdashboard");
  await page.getByLabel("Email address").fill("incident-browser@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("incident-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.locator("dd").filter({ hasText: /^33\.33%$/ }),
  ).toBeVisible();
  await expect(
    page.getByText(/1 successful \/ 3 completed scheduled runs/),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Recent incidents" })
      .getByRole("link", { name: "Controlled incident fixture" }),
  ).toHaveCount(2);
  await page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/dashboard?") &&
      response.status() === 200,
    { timeout: 20_000 },
  );
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator(".recharts-line")).toHaveCount(2);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.screenshot({
      path: testInfo.outputPath(`dashboard-${width}.png`),
      fullPage: true,
    });
  }
  await page.getByLabel("History window").selectOption("7d");
  await expect(
    page.locator("dd").filter({ hasText: /^33\.33%$/ }),
  ).toBeVisible();
  await page.getByText("View bucket observations").click();
  await expect(page.getByRole("table")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.route("**/api/v1/dashboard?*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "service_unavailable", message: "Try again." },
      }),
    }),
  );
  await page.getByRole("button", { name: "Refresh overview" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Refresh failed" }),
  ).toContainText("Showing the last loaded overview");
  await expect(
    page
      .locator("dd")
      .filter({ hasText: /^33\.33%$/ })
      .first(),
  ).toBeVisible();
  await page.unroute("**/api/v1/dashboard?*");
  await page.getByRole("button", { name: "Refresh overview" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Refresh failed" }),
  ).toHaveCount(0);
  await page
    .getByRole("region", { name: "Recent incidents" })
    .getByRole("link", { name: "Controlled incident fixture" })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Opening evidence" }),
  ).toBeVisible();
  expect(failures).toEqual([]);
});
