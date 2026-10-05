import { test, expect } from "@playwright/test";

test("incident history retains evidence across desktop and mobile after archive and pruning", async ({
  page,
}, testInfo) => {
  test.skip(
    process.env.TEST_INCIDENT_FIXTURES !== "1",
    "Requires the opt-in isolated incident fixture.",
  );
  await page.goto("/login?next=%2Fincidents");
  await page.getByLabel("Email address").fill("incident-browser@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("incident-browser-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Incidents", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Incidents" }).getByRole("listitem"),
  ).toHaveCount(2);
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByLabel("Incident status").selectOption("resolved");
    await expect(
      page.getByRole("list", { name: "Incidents" }).getByRole("listitem"),
    ).toHaveCount(1);
    await page
      .getByRole("link", { name: "Controlled incident fixture" })
      .click();
    await expect(
      page.getByText("Resolved incident", { exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Opening evidence" })
        .getByText("HTTP 503", { exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Confirmation evidence" })
        .getByText("3", { exact: true }),
    ).toBeVisible();
    await expect(
      page
        .getByRole("region", { name: "Recovery evidence" })
        .getByText("HTTP 200", { exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("region", { name: "Recovery evidence" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({
      path: testInfo.outputPath(`incident-resolved-${width}.png`),
      fullPage: true,
    });
    await page.getByRole("link", { name: "Back to incidents" }).click();
    await page.getByLabel("Incident status").selectOption("open");
    await page
      .getByRole("link", { name: "Controlled incident fixture" })
      .click();
    await expect(
      page.getByText("Open incident · recovery not observed"),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Recovery evidence" }),
    ).toHaveCount(0);
    await page.getByRole("link", { name: "Back to incidents" }).click();
  }
});
