import { test, expect } from "@playwright/test";

const origin = process.env.TEST_CONTAINER_ORIGIN;
test.use({ baseURL: origin ?? "http://localhost:13000" });

test("standalone container serves the public UI, images and same-origin API on desktop and mobile", async ({
  page,
  request,
}, testInfo) => {
  test.skip(!origin, "Requires an already running local Compose stack.");
  const target = new URL(origin!);
  expect(target.protocol).toBe("http:");
  expect(["localhost", "127.0.0.1"]).toContain(target.hostname);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Reliability at a glance.",
  );
  await expect
    .poll(() =>
      page
        .getByRole("img")
        .evaluate((image) => (image as HTMLImageElement).naturalWidth),
    )
    .toBeGreaterThan(0);
  const asset = await request.get("/screenshots/demo-mobile.png");
  expect(asset.status()).toBe(200);
  expect(asset.headers()["content-type"]).toContain("image/png");
  expect((await request.get("/api/v1/monitors")).status()).toBe(401);
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 900 });
    await expect
      .poll(() =>
        page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      )
      .toBeTruthy();
    await page.screenshot({
      path: testInfo.outputPath(`container-${width}.png`),
      fullPage: true,
    });
  }
  await page.getByRole("link", { name: "Explore the read-only demo" }).click();
  await expect(page.getByText("No monitors are published yet")).toBeVisible();
  await page
    .getByRole("link", { name: "Create an account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Create your account" }),
  ).toBeVisible();
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
  expect(errors).toEqual([]);
});

test("container sign-in renders protected pages and survives a full reload", async ({
  page,
}) => {
  test.skip(!origin, "Requires an already running local Compose stack.");
  const email = `container-account-${crypto.randomUUID()}@example.com`;
  const password = "container-release-test-password";
  const csrf = (await (await page.request.get("/api/v1/auth/csrf")).json())
    .csrf_token;
  const registration = await page.request.post("/api/v1/auth/register", {
    headers: { Origin: origin!, "X-CSRF-Token": csrf },
    data: { email, password },
  });
  expect(registration.status()).toBe(202);
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  const response = await page.reload();
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.goto("/monitors");
  await expect(
    page.getByRole("heading", { name: "Monitors", exact: true }),
  ).toBeVisible();
});
