# Account interfaces

Milestone 6 connects the account API to browser forms. It adds no monitor APIs,
monitor forms, or monitoring data.

## Start the local application

Use the [database guide](database.md) to configure PostgreSQL, dedicated roles,
and migrations. Start Mailpit in its own terminal as described in the
[authentication guide](authentication.md). Keep the backend origin at
`DEVPULSE_APP_ORIGIN=http://localhost:3000` for the commands below.

Backend terminal, from `backend/` with the virtual environment active:

```bash
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Frontend terminal, from `frontend/`:

```bash
npm ci --cache ../.cache/npm
npm run dev
```

Open **http://localhost:3000**. Use this hostname consistently: visiting
`127.0.0.1:3000` changes the browser Origin and will fail the configured CSRF
check. The initial redirect to `/dashboard` sends anonymous visitors to login.
The frontend rewrite forwards `/api/v1/*` to the fixed loopback backend on port
8000, preserving browser cookies and Origin. There is no user-controlled proxy
destination or browser-visible backend secret.

Next.js and FastAPI still run as separate processes. The checked-in loopback
topology supports direct development and local production-build validation.
Production ingress and container networking remain later milestones; the
eventual ingress must keep the same browser-facing `/api/v1` paths. Direct local
traffic is throttled by the backend's connecting IP, so users of this local proxy
share an IP bucket. Do not weaken forwarded-header trust to bypass this limit.

## Browser walkthrough

1. Choose **Create an account**, enter an email and a 12–128 character password,
   and confirm it. The response is generic to avoid exposing account existence.
2. Open local Mailpit at **http://127.0.0.1:8025**. Copy the verification code and
   use **Enter verification code**. Codes stay out of URLs and browser storage.
3. Sign in. The Overview shows your email and verification state, with a real
   sign-out control. Reloading keeps you signed in through the HttpOnly session
   cookie. Unverified accounts can sign in and see a **Verify email** action.
4. Use **Request a new code** if needed. Older verification codes are rejected;
   the form explains the error and lets you enter the latest code.
5. Use **Forgot password?**, copy the reset code from Mailpit, and set a new
   password. Existing sessions are revoked. Sign in again with the new password.
6. Choose **Sign out**. Server revocation and cookie deletion complete before
   the browser returns to login.

Invalid fields have linked errors and `aria-invalid`. A focused error summary
announces validation or API failures. Pending submissions prevent repeated
clicks and keep fields read-only. Passwords preserve whitespace and Unicode;
oversized input is rejected rather than silently truncated. Success states
provide working continuation links. The layouts support keyboard operation,
reduced motion, and 360px mobile widths using the existing design tokens.

## Session handling and API types

The server-rendered workspace layout calls FastAPI `/auth/me` using only the
session cookie, with a fixed destination, no shared caching, and a timeout.
Missing/invalid sessions redirect to login. Backend outages show a retryable
error instead of claiming that the user signed out. FastAPI remains the
authorization boundary for all business behavior.

TanStack Query holds session data only in memory and revalidates on mount,
window focus, and page restoration. A rejected session hides the workspace and
returns to login. Logout/login use a fresh document navigation and clear cached
account state. Password reset also clears the local query cache. No credentials,
cookies, or account data are written to localStorage/sessionStorage.

The browser API client fetches a CSRF token when needed. After login, logout,
or reset it discards that token because the cookie identity has changed. A
`csrf_rejected` response permits one refresh/retry because FastAPI rejects CSRF
before executing the operation. Network failures and other mutation errors are
never automatically retried. Cookies remain HttpOnly; the browser sends them
through the same-origin rewrite.

Only `/dashboard` is currently an allowed login return destination. External,
protocol-relative, encoded, script, and unimplemented destinations fall back to
the dashboard. Redirect query values are never copied directly into navigation.

`src/lib/api/schema.d.ts` is generated from FastAPI's OpenAPI schema. Request and
response types derive from that file; there are no manually maintained account
DTOs. The generator imports the backend using its local `.venv` without starting
the API or connecting to PostgreSQL. It ignores private backend configuration.
After an authorized API contract change, run from `frontend/`:

```bash
npm run api:generate
npm run api:check
npm run check
npm run build
```

## Browser tests

Use the dedicated PostgreSQL `_test` database and start local Mailpit on ports
1025/8025. Stop any manually running Next.js/FastAPI processes on ports 3000/8000;
the test runner refuses to reuse occupied ports. With dependencies installed,
from `frontend/` in WSL:

```bash
PLAYWRIGHT_BROWSERS_PATH=../.cache/playwright npx playwright install chromium
npm run build
read -rs -p 'Test database URL: ' TEST_DATABASE_URL
printf '\n'
export TEST_DATABASE_URL
npm run test:e2e
unset TEST_DATABASE_URL
```

The runner starts a test-only FastAPI process, applies real migrations to a
fresh random schema in the test database, starts the production frontend build,
and runs Chromium. Tests use real account APIs and Mailpit, without external
websites. Only their synthetic accounts and email messages are involved. The
runner shuts down the API through stdin, including on Windows, so its schema is
dropped on normal completion or test failure. Forcefully terminating the runner
can leave an `e2e_<UUID>` schema; inspect before manually removing an orphan.
It never drops the database or an existing schema.

Playwright covers signup, verification, persistent login, cross-session reset
revocation, logout, resend/superseded codes, and mobile keyboard validation.
Vitest covers form states, request contracts, CSRF retry boundaries, redirect
safety, session errors, and the existing shell/accessibility primitives.
Traces/video are off to avoid recording credentials; test reports and review
screenshots stay in ignored local output directories.

Validation used Windows Node 24, Python 3.13, PostgreSQL 18.3, Mailpit 1.31.2, and
Playwright Chromium. WSL2 Ubuntu validation remains pending until that environment
is supplied. No global installation, permission changes, Git operations, or
cloud deployment is part of this milestone.

References: [Next.js rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites),
[TanStack Query](https://tanstack.com/query/latest/docs/framework/react/guides/ssr),
and [OpenAPI TypeScript](https://openapi-ts.dev/node).
