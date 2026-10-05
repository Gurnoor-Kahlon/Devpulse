import {
  test,
  expect,
  type Page,
  type APIRequestContext,
} from "@playwright/test";

async function prepareAccount(
  page: Page,
  request: APIRequestContext,
  verified = true,
) {
  const email = `monitors-${crypto.randomUUID()}@example.com`;
  const password = "monitor-browser-password";
  const csrf = (await (await page.request.get("/api/v1/auth/csrf")).json())
    .csrf_token;
  const headers = { Origin: "http://localhost:3000", "X-CSRF-Token": csrf };
  expect(
    (
      await page.request.post("/api/v1/auth/register", {
        headers,
        data: { email, password },
      })
    ).status(),
  ).toBe(202);
  if (verified) {
    const messages = await (
      await request.get("http://127.0.0.1:8025/api/v1/messages")
    ).json();
    const message = messages.messages.find(
      (item: { To: { Address: string }[] }) =>
        item.To.some((to) => to.Address === email),
    );
    expect(message).toBeTruthy();
    const detail = await (
      await request.get(`http://127.0.0.1:8025/api/v1/message/${message.ID}`)
    ).json();
    const token = detail.Text.match(/[A-Za-z0-9_-]{43}/)?.[0];
    expect(token).toBeTruthy();
    expect(
      (
        await page.request.post("/api/v1/auth/verify-email", {
          headers,
          data: { token },
        })
      ).ok(),
    ).toBeTruthy();
  }
  expect(
    (
      await page.request.post("/api/v1/auth/login", {
        headers,
        data: { email, password },
      })
    ).ok(),
  ).toBeTruthy();
}
async function assertNoOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
}

test("monitor management persists create, edit, pause, resume, and archive across desktop and mobile", async ({
  page,
  request,
}) => {
  await prepareAccount(page, request);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/monitors");
  await expect(page.getByText("No monitors yet")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Monitors", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Create monitor", exact: true }).click();
  await page
    .getByRole("button", { name: "Create monitor", exact: true })
    .click();
  await expect(
    page.getByRole("form", { name: "Create monitor" }).getByRole("alert"),
  ).toBeFocused();
  await page.getByLabel("Monitor name").fill("Payments API");
  await page
    .getByLabel("URL", { exact: true })
    .fill("https://example.com/health");
  await page
    .getByRole("button", { name: "Create monitor", exact: true })
    .click();
  await expect(page).toHaveURL(/\/monitors$/);
  let row = page.getByRole("article", { name: "Payments API", exact: true });
  await expect(row.getByText("No data", { exact: true })).toBeVisible();
  await expect(row.getByText("Never checked")).toBeVisible();
  await assertNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../.cache/monitors-desktop.png",
    fullPage: true,
  });
  await row.getByRole("link", { name: "Edit Payments API" }).click();
  await page.getByLabel("Monitor name").fill("Billing endpoint");
  await page.getByLabel("HTTP method").selectOption("HEAD");
  await page.getByLabel("Check interval (seconds)").fill("120");
  await page.getByLabel("Timeout (seconds)").fill("8");
  await page.getByLabel("Expected HTTP status").fill("204");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(/\/monitors$/);
  await page.reload();
  row = page.getByRole("article", { name: "Billing endpoint", exact: true });
  await expect(row).toContainText("HEAD · HTTP 204");
  await expect(row).toContainText("120s");
  await row.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(row.getByText("Paused", { exact: true })).toBeVisible();
  await page.getByLabel("Configuration").selectOption("enabled");
  await expect(page.getByText("No matching monitors")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page.getByLabel("Search monitors").fill("EXAMPLE.COM");
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(row.getByText("No data", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 360, height: 780 });
  await page.getByLabel("Search monitors").clear();
  await assertNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../.cache/monitors-mobile.png",
    fullPage: true,
  });
  await row.getByRole("link", { name: "Edit Billing endpoint" }).click();
  await expect(page.getByLabel("Timeout (seconds)")).toHaveValue("8");
  await assertNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../.cache/monitor-form-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  const archive = row.getByRole("button", { name: "Archive", exact: true });
  await archive.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(archive).toBeFocused();
  await archive.click();
  await assertNoOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../.cache/monitor-archive-mobile.png",
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Archive monitor", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("No monitors yet")).toBeVisible();
  await page.reload();
  await expect(page.getByText("No monitors yet")).toBeVisible();
  const data = await (await page.request.get("/api/v1/monitors")).json();
  expect(data.items).toEqual([]);
});

test("concurrent edits require an explicit reload and session refresh preserves the draft", async ({
  page,
  request,
}) => {
  await prepareAccount(page, request);
  const csrf = (await (await page.request.get("/api/v1/auth/csrf")).json())
    .csrf_token;
  const headers = { Origin: "http://localhost:3000", "X-CSRF-Token": csrf };
  const created = await (
    await page.request.post("/api/v1/monitors", {
      headers,
      data: { name: "Versioned API", url: "https://example.com/health" },
    })
  ).json();
  await page.goto(`/monitors/${created.id}/edit`);
  await page.getByLabel("Monitor name").fill("Unsaved draft");
  await page.evaluate(() => window.dispatchEvent(new Event("pageshow")));
  await expect(page.getByLabel("Monitor name")).toHaveValue("Unsaved draft");
  expect(
    (
      await page.request.patch(`/api/v1/monitors/${created.id}`, {
        headers,
        data: { configuration_version: 1, name: "Changed elsewhere" },
      })
    ).ok(),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("form", { name: "Edit monitor" }).getByRole("alert"),
  ).toContainText("changed elsewhere");
  await expect(page.getByLabel("Monitor name")).toHaveValue("Unsaved draft");
  await page.getByRole("button", { name: "Reload latest settings" }).click();
  await expect(page.getByLabel("Monitor name")).toHaveValue(
    "Changed elsewhere",
  );
  await page.getByLabel("Monitor name").fill("Reviewed edit");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("article", { name: "Reviewed edit" }),
  ).toBeVisible();
});

test("unverified accounts get verification guidance on monitor routes", async ({
  page,
  request,
}) => {
  await prepareAccount(page, request, false);
  await page.goto("/monitors");
  await expect(
    page.getByText("Verify your email before creating or enabling monitors."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Create monitor", exact: true }),
  ).toHaveCount(0);
  await page.goto("/monitors/new");
  await expect(
    page.getByRole("button", { name: "Create monitor", exact: true }),
  ).toBeDisabled();
});
