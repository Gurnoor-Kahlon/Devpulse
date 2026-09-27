import { test, expect } from "@playwright/test";

test("assertion editor saves real definitions while check and incident snapshots remain unchanged", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.TEST_ASSERTION_FIXTURES !== "1",
    "Requires isolated real-probe assertion fixtures.",
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
  const latest = page
    .getByRole("list", { name: "Check attempts" })
    .locator(":scope > li")
    .first();
  await latest.locator("summary").click();
  await expect(
    latest.getByText("Failed · Value or type did not match"),
  ).toBeVisible();
  await expect(latest.getByText("Expected: true")).toBeVisible();
  await expect(latest.locator("summary")).toContainText("HTTP 200");
  await page
    .getByRole("link", { name: "Edit assertions", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Response assertions" }),
  ).toBeVisible();
  await expect(page.getByLabel(/^JSON Pointer/)).toHaveValue("/ok");
  await page.getByLabel(/^Expected JSON value/).fill("false");
  await page.getByRole("button", { name: "Add assertion" }).click();
  const added = page.getByRole("group", { name: "Assertion 2", exact: true });
  await added
    .getByRole("combobox", { name: /^Type/ })
    .selectOption("text_contains");
  await added.getByLabel(/^Expected text/).fill("healthy");
  await page.getByRole("button", { name: "Save assertions" }).click();
  await expect(page.getByText(/Assertions saved/)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel(/^Expected JSON value/)).toHaveValue("false");
  await expect(page.getByLabel(/^Expected text/)).toHaveValue("healthy");
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.screenshot({
      path: testInfo.outputPath(`assertions-${width}.png`),
      fullPage: true,
    });
  }
  await page.goto(path);
  await latest.locator("summary").click();
  await expect(latest.getByText("Expected: true")).toBeVisible();
  await expect(latest.getByText("Expected: false")).toHaveCount(0);
  await page
    .getByRole("region", { name: "Monitor incident history" })
    .getByRole("link", { name: "Controlled incident fixture" })
    .first()
    .click();
  await expect(
    page
      .getByRole("region", { name: "Confirmation evidence" })
      .getByText("Expected: true"),
  ).toBeVisible();
  await expect(page.getByText("browser-body-canary")).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBeTruthy();
  expect(errors).toEqual([]);
});
