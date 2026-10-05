import { test, expect } from "@playwright/test";

test("monitor detail uses real scoped history, paging, evidence and archived views", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.TEST_MONITOR_HISTORY_FIXTURES !== "1",
    "Requires isolated real-probe history fixtures.",
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login?next=%2Fmonitors");
  await page.getByLabel("Email address").fill("incident-browser@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("incident-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page
    .getByRole("link", { name: "Controlled incident fixture", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Controlled incident fixture",
    }),
  ).toBeVisible();
  const path = new URL(page.url()).pathname;
  await expect(
    page.locator("dd").filter({ hasText: /^33\.33%$/ }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "HTTP status distribution" })
      .getByText("2 responses · 66.67%"),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Check attempts" }).getByRole("listitem"),
  ).toHaveCount(25);
  await page.getByRole("button", { name: "Older checks" }).click();
  await expect(
    page.getByRole("list", { name: "Check attempts" }).getByRole("listitem"),
  ).toHaveCount(2);
  await page
    .getByRole("list", { name: "Check attempts" })
    .locator("summary")
    .first()
    .click();
  await expect(
    page
      .getByRole("list", { name: "Check attempts" })
      .getByRole("listitem")
      .first()
      .getByText("The HTTP status did not match the expected status.", {
        exact: false,
      }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Newest checks" }).click();
  await expect(
    page.getByRole("list", { name: "Check attempts" }).getByRole("listitem"),
  ).toHaveCount(25);
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator(".recharts-line")).toHaveCount(1);
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath(`monitor-history-${width}.png`),
      fullPage: true,
    });
  }
  await page.getByLabel("History window").selectOption("7d");
  await expect(
    page.locator("dd").filter({ hasText: /^33\.33%$/ }),
  ).toBeVisible();
  await page.getByText("View latency buckets").click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBeTruthy();
  await page.getByRole("link", { name: "Edit settings" }).click();
  await expect(
    page.getByRole("heading", { name: "Edit monitor" }),
  ).toBeVisible();
  await page.goto("/monitors");
  await page
    .getByRole("article", { name: "Controlled incident fixture" })
    .getByRole("button", { name: "Archive", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Archive monitor", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goto(path);
  await expect(page.getByText(/Archived · read-only history/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Edit settings" })).toHaveCount(
    0,
  );
  await expect(
    page
      .getByRole("region", { name: "Monitor incident history" })
      .getByRole("listitem"),
  ).toHaveCount(2);
  await expect(
    page.getByRole("list", { name: "Check attempts" }).getByRole("listitem"),
  ).toHaveCount(25);
  expect(errors).toEqual([]);
});
