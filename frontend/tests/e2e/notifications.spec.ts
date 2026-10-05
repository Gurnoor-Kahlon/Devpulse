import { test, expect } from "@playwright/test";

test("notification preferences and real SMTP delivery history work on desktop and mobile", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.TEST_NOTIFICATION_FIXTURES !== "1",
    "Requires isolated real probe and Mailpit fixtures.",
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login?next=%2Fnotifications");
  await page.getByLabel("Email address").fill("incident-browser@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("incident-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Notifications" }),
  ).toBeVisible();
  await expect(page.getByLabel("Enable incident email")).toBeChecked();
  const deliveries = page.getByRole("list", { name: "Email deliveries" });
  await expect(deliveries.getByRole("listitem")).toHaveCount(3);
  await expect(
    deliveries.getByText("Accepted by SMTP", { exact: true }),
  ).toHaveCount(3);
  await page.getByLabel("Email when recovery is observed").uncheck();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Notification preferences saved.")).toBeVisible();
  await page.reload();
  await expect(
    page.getByLabel("Email when recovery is observed"),
  ).not.toBeChecked();
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath(`notifications-${width}.png`),
      fullPage: true,
    });
  }
  await deliveries.getByRole("link", { name: "View incident" }).first().click();
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "Controlled incident fixture",
    }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "Email delivery history" })
      .getByText("Accepted by SMTP", { exact: true }),
  ).toBeVisible();
  await page.goto("/notifications");
  await page.getByLabel("Enable incident email").uncheck();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Notification preferences saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Enable incident email")).not.toBeChecked();
  await expect(deliveries.getByRole("listitem")).toHaveCount(3);
  expect(errors).toEqual([]);
});
