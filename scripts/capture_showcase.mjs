// Capture the real app. Credentials arrive on stdin and are never logged or saved.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import path from "node:path";
const require = createRequire(
  new URL("../frontend/package.json", import.meta.url),
);
const { chromium, expect } = require("@playwright/test");
const input = JSON.parse(readFileSync(0, "utf8"));
const browser = await chromium.launch({ headless: true });
const captures = [];
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1100 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.name));
  await page.goto(`${input.origin}/login`);
  await page.getByLabel("Email address", { exact: true }).fill(input.email);
  await page.getByLabel("Password", { exact: true }).fill(input.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  const monitors = input.snapshot.monitors;
  const incident = input.snapshot.incidents.find(
    (i) => i.monitor_id === monitors.checkout.id,
  );
  async function capture(
    file,
    route,
    heading,
    { fullPage = true, expand = false } = {},
  ) {
    await page.goto(`${input.origin}${route}`);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    if (route === "/dashboard") {
      await expect(
        page.getByText("Completed observations", { exact: true }),
      ).toBeVisible();
      await expect(page.locator(".recharts-surface")).toHaveCount(2);
      await expect(
        page.getByRole("region", { name: "Recent incidents" }),
      ).toBeVisible();
    } else if (route === "/monitors") {
      await expect(page.getByRole("heading", { level: 2 })).toHaveCount(5);
    } else if (route.endsWith("/assertions")) {
      await expect(page.getByLabel(/^JSON Pointer/)).toHaveValue("/available");
    } else if (route.startsWith("/monitors/")) {
      await expect(
        page.getByRole("list", { name: "Check attempts" }),
      ).toBeVisible();
      await expect(page.locator(".recharts-surface")).toHaveCount(1);
    } else if (route.startsWith("/incidents/")) {
      await expect(
        page.getByRole("region", {
          name: "Confirmation evidence",
          exact: true,
        }),
      ).toBeVisible();
    }
    await expect(
      page.getByText(/Loading (checks|monitor history|incident)/),
    ).toHaveCount(0);
    if (expand) {
      const attempt = page
        .getByRole("list", { name: "Check attempts" })
        .locator("li")
        .first();
      await attempt.locator("summary").click();
      await expect(attempt.getByText("Expected: true")).toBeVisible();
    }
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => window.scrollTo(0, 0));
    // Mask only the actual loopback target URL, never statistics or evidence.
    const mask = page
      .locator("p")
      .filter({ hasText: /^http:\/\/127\.0\.0\.1:8081\// });
    await page.screenshot({
      path: path.join(input.output, file),
      fullPage,
      animations: "disabled",
      mask: [mask],
      maskColor: "#334155",
    });
    captures.push({
      file,
      route: route.replace(/[0-9a-f-]{36}/g, "{id}"),
      stage: input.stage,
      captured_at: new Date().toISOString(),
      target_url_masked: (await mask.count()) > 0,
    });
  }
  if (input.stage === "incident") {
    await capture(
      "incident-open.png",
      `/incidents/${incident.id}`,
      monitors.checkout.name,
    );
    await capture(
      "tour-incident.png",
      `/incidents/${incident.id}`,
      monitors.checkout.name,
      { fullPage: false },
    );
  } else {
    await capture("dashboard.png", "/dashboard", "Overview");
    await capture("monitors.png", "/monitors", "Monitors");
    await capture(
      "monitor-history.png",
      `/monitors/${monitors.search.id}`,
      monitors.search.name,
    );
    await capture(
      "incident-recovery.png",
      `/incidents/${incident.id}`,
      monitors.checkout.name,
    );
    await expect(
      page.getByText("Resolved incident", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Recovery evidence", exact: true }),
    ).toBeVisible();
    await capture(
      "assertion-config.png",
      `/monitors/${monitors.inventory.id}/assertions`,
      "Response assertions",
    );
    await capture(
      "assertion-result.png",
      `/monitors/${monitors.inventory.id}`,
      monitors.inventory.name,
      { expand: true },
    );
    await capture("tour-dashboard.png", "/dashboard", "Overview", {
      fullPage: false,
    });
    await capture(
      "tour-monitor.png",
      `/monitors/${monitors.search.id}`,
      monitors.search.name,
      { fullPage: false },
    );
    await capture(
      "tour-recovery.png",
      `/incidents/${incident.id}`,
      monitors.checkout.name,
      { fullPage: false },
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await capture("dashboard-mobile.png", "/dashboard", "Overview");
  }
  expect(errors).toEqual([]);
  process.stdout.write(JSON.stringify(captures));
} finally {
  await browser.close();
}
