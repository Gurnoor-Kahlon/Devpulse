import type { components, paths } from "./schema";

export type User = components["schemas"]["UserResponse"];
type ErrorBody = components["schemas"]["ErrorResponse"];
type AuthPath = Extract<keyof paths, `/api/v1/auth/${string}`>;
type PostPath = {
  [P in AuthPath]: paths[P]["post"] extends { responses: unknown } ? P : never;
}[AuthPath];
type Body<P extends PostPath> = paths[P]["post"] extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : undefined;
type Result<P extends PostPath> = paths[P]["post"] extends {
  responses: { 200: { content: { "application/json": infer R } } };
}
  ? R
  : components["schemas"]["MessageResponse"];

const messages: Record<string, string> = {
  invalid_credentials: "Email or password is incorrect.",
  invalid_token:
    "This code is invalid or has expired. Request a new code and try again.",
  csrf_rejected: "Your session changed. Please try again.",
  authentication_required: "Your session has expired. Sign in again.",
  validation_error: "Check the highlighted fields and try again.",
  rate_limited: "Too many attempts. Please wait before trying again.",
  email_verification_required:
    "Verify your email before creating or enabling a monitor.",
  monitor_quota_exceeded:
    "Your account has reached its limit of 10 monitors. Archive a monitor to add another.",
  enabled_monitor_quota_exceeded:
    "The service has reached its limit of 100 enabled monitors. Save this monitor paused or try again later.",
  configuration_conflict:
    "This monitor changed elsewhere. Reload the latest settings before trying again.",
  monitor_not_found: "This monitor is unavailable. It may have been archived.",
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public fields: ErrorBody["error"]["fields"] = [],
    public requestId?: string,
  ) {
    super(messages[code] ?? "We couldn’t reach the service. Please try again.");
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    const timeout = AbortSignal.timeout(15_000);
    response = await fetch(path, {
      ...options,
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      signal: options.signal
        ? AbortSignal.any([options.signal, timeout])
        : timeout,
    });
  } catch {
    throw new ApiError(0, "unavailable");
  }
  if (response.status === 204 && response.ok) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      response.status,
      data?.error?.code ?? "unavailable",
      data?.error?.fields ?? [],
      response.headers.get("x-request-id") ?? undefined,
    );
  }
  if (data === null) throw new ApiError(0, "unavailable");
  return data as T;
}

let csrfToken: string | undefined;
let csrfPending: Promise<string> | undefined;
export function clearCsrf() {
  csrfToken = undefined;
  csrfPending = undefined;
}

export async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  csrfPending ??= request<components["schemas"]["CsrfResponse"]>(
    "/api/v1/auth/csrf",
  )
    .then((result) => {
      csrfToken = result.csrf_token;
      return result.csrf_token;
    })
    .finally(() => {
      csrfPending = undefined;
    });
  return csrfPending;
}

export async function authPost<P extends PostPath>(
  path: P,
  body: Body<P>,
): Promise<Result<P>> {
  for (let attempt = 0; ; attempt++) {
    const token = await csrf();
    try {
      const result = await request<Result<P>>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": token },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (
        [
          "/api/v1/auth/login",
          "/api/v1/auth/logout",
          "/api/v1/auth/reset-password",
        ].includes(path)
      )
        clearCsrf();
      return result;
    } catch (error) {
      // FastAPI rejects CSRF before executing the operation. Never retry uncertain writes.
      if (
        attempt === 0 &&
        error instanceof ApiError &&
        error.code === "csrf_rejected"
      ) {
        clearCsrf();
        continue;
      }
      throw error;
    }
  }
}

export function getMe(signal?: AbortSignal) {
  return request<User>("/api/v1/auth/me", { signal });
}
