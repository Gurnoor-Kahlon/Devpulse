import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, authPost, clearCsrf, getMe } from "@/lib/api/client";
import { safeReturnPath } from "@/lib/auth/redirect";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
beforeEach(() => clearCsrf());
afterEach(() => vi.unstubAllGlobals());

describe("authentication transport", () => {
  it("bootstraps CSRF, uses same-origin cookies, and refreshes after rotation", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ csrf_token: "initial" }))
      .mockResolvedValueOnce(
        json({
          id: "user",
          email: "user@example.com",
          email_verified_at: null,
        }),
      )
      .mockResolvedValueOnce(json({ csrf_token: "rotated" }))
      .mockResolvedValueOnce(json({ message: "Signed out." }));
    vi.stubGlobal("fetch", fetcher);
    await authPost("/api/v1/auth/login", {
      email: "user@example.com",
      password: "example-password",
    });
    await authPost("/api/v1/auth/logout", undefined);
    expect(fetcher.mock.calls[1][1]).toMatchObject({
      credentials: "same-origin",
      cache: "no-store",
      method: "POST",
      headers: { "X-CSRF-Token": "initial" },
    });
    expect(fetcher.mock.calls[3][1].headers["X-CSRF-Token"]).toBe("rotated");
    expect(fetcher.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/auth/login",
      "/api/v1/auth/csrf",
      "/api/v1/auth/logout",
    ]);
  });
  it("retries only a CSRF rejection, once, before the operation ran", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ csrf_token: "old" }))
      .mockResolvedValueOnce(json({ error: { code: "csrf_rejected" } }, 403))
      .mockResolvedValueOnce(json({ csrf_token: "new" }))
      .mockResolvedValueOnce(json({ message: "accepted" }));
    vi.stubGlobal("fetch", fetcher);
    await authPost("/api/v1/auth/forgot-password", {
      email: "user@example.com",
    });
    expect(fetcher).toHaveBeenCalledTimes(4);
  });
  it("does not retry an uncertain failed mutation or expose upstream text", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(json({ csrf_token: "token" }))
      .mockRejectedValueOnce(new Error("private-proxy-detail"));
    vi.stubGlobal("fetch", fetcher);
    await expect(
      authPost("/api/v1/auth/register", {
        email: "user@example.com",
        password: "example-password",
      }),
    ).rejects.toThrow("We couldn’t reach the service");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it("keeps expiry distinguishable from an outage", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json({ error: { code: "authentication_required" } }, 401),
        ),
    );
    await expect(getMe()).rejects.toMatchObject({
      status: 401,
      code: "authentication_required",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("proxy-secret", { status: 502 })),
    );
    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
  });
});

it.each([
  "https://evil.example",
  "//evil.example",
  "/\\evil.example",
  "javascript:alert(1)",
  "%2F%2Fevil.example",
  ["/dashboard"],
  undefined,
  "/login",
])("rejects unsafe or unavailable return destinations: %s", (value) => {
  expect(safeReturnPath(value)).toBe("/dashboard");
});
