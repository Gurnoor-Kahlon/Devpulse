# Account and session API

Milestone 5 implements account access at the API level. Browser forms, route
protection, and same-origin frontend forwarding arrive in milestone 6. No monitor
endpoints exist yet. Unverified accounts may log in; verified-email enforcement
for monitor creation/enabling belongs to milestone 7.

## Local prerequisites and startup

Use the project Python environment and the dedicated PostgreSQL databases from
the [database guide](database.md). Supply [Mailpit](https://mailpit.axllent.org/docs/install/)
as a local executable; a portable binary is sufficient. No global installation
or operating-system service configuration is needed by the application.

Start Mailpit in its own WSL terminal:

```bash
mailpit --listen 127.0.0.1:8025 --smtp 127.0.0.1:1025 --disable-version-check --smtp-disable-rdns
```

Mailpit captures messages locally and does not deliver them to real inboxes.
Open <http://127.0.0.1:8025> to read verification/reset codes. Keep its SMTP and web
interfaces on loopback. Its default temporary message store is deleted on normal
shutdown. Do not enable SMTP relay or forwarding for development.

In the backend terminal, activate `.venv`, install `requirements-dev.lock`, then:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Use the settings in `backend/.env.example`. In particular:

| Setting                                             | Default / behavior                                                |
| --------------------------------------------------- | ----------------------------------------------------------------- |
| `DEVPULSE_APP_ORIGIN`                               | `http://localhost:3000`; exact Origin required on every auth POST |
| `DEVPULSE_SMTP_HOST`                                | `127.0.0.1`                                                       |
| `DEVPULSE_SMTP_PORT`                                | `1025`                                                            |
| `DEVPULSE_SMTP_MODE`                                | `plain` locally; `starttls` or `tls` uses verified TLS            |
| `DEVPULSE_MAIL_FROM`                                | `devpulse@localhost.localdomain`                                  |
| `DEVPULSE_SMTP_USERNAME` / `DEVPULSE_SMTP_PASSWORD` | Optional pair; authentication requires TLS                        |

Production configuration rejects HTTP origins and plaintext SMTP. SMTP secrets
are masked settings and belong in private configuration only. Delivery has a
five-second socket timeout. Database failure produces a safe `503`; SMTP failure
keeps the generic email-request response and records `auth_email_failed` without
addresses, codes, credentials, or exception text.

The app uses the connecting client's IP for throttling and ignores forwarded
headers. Run the direct local API with `--no-proxy-headers`. A future trusted
ingress must supply verified client identity through an explicitly restricted
proxy configuration; arbitrary forwarded headers must never become trusted.

## HTTP contract

All paths below start with `/api/v1/auth`. Requests use JSON; extra body fields are
rejected. Email addresses are validated and normalized to lowercase. New/reset
passwords must be 12–128 characters; whitespace and Unicode are preserved without
normalization or silent truncation. Login accepts 1–128 characters.

| Method/path                 | Body                | Success                                                       |
| --------------------------- | ------------------- | ------------------------------------------------------------- |
| `GET /csrf`                 | None                | `200`, `{ "csrf_token": "..." }` and session cookies          |
| `POST /register`            | `email`, `password` | `202`, generic email message                                  |
| `POST /login`               | `email`, `password` | `200`, `id`, `email`, `email_verified_at`; rotated cookies    |
| `GET /me`                   | None                | `200`, the same user fields; otherwise `401`                  |
| `POST /logout`              | None                | `200`; revokes current session and clears cookies             |
| `POST /verify-email`        | `token`             | `200`; verifies the token's account                           |
| `POST /resend-verification` | `email`             | `202`, generic email message                                  |
| `POST /forgot-password`     | `email`             | `202`, generic email message                                  |
| `POST /reset-password`      | `token`, `password` | `200`; revokes all account sessions and clears caller cookies |

Every POST requires the exact configured `Origin`, a valid session cookie, and
`X-CSRF-Token` from `GET /csrf`. This includes login, registration, and password
recovery. First call `/csrf` without authentication; it creates a 30-minute
anonymous session whose `user_id` is null. It grants no account access. The CSRF
bootstrap rejects foreign Origin and cross-site Fetch Metadata headers.

Keep both HttpOnly cookies in the HTTP client's cookie jar. After login, fetch
`/csrf` again because login rotates both session and CSRF identities. A matching
CSRF cookie lets repeated bootstrap calls return the same token, supporting
multiple tabs. The server validates the header against the stored session hash;
it does not trust a header/cookie match alone. Missing/invalid CSRF or Origin
returns `403 csrf_rejected`.

Expired/revoked sessions return `401` on `/me`; state-changing requests return
`403` until CSRF is bootstrapped again. Login failures use the same
`401 invalid_credentials` response for absent accounts and wrong passwords.
Invalid, expired, superseded, wrong-purpose, and consumed email codes return
`400 invalid_token`. All errors follow the shared safe error/request-ID contract.
Responses are not cacheable, and no CORS permission is granted to other origins.

Registration, resend, and recovery use the same `202` message for eligible,
absent, duplicate, or already-verified accounts as applicable. This reduces
enumeration through status/body differences; synchronous SMTP can still create
timing differences. Duplicate signup never replaces an existing password.

## Session and token policy

- Passwords use Argon2id (64 MiB, three iterations, parallelism four), independent
  salts, and rehash-on-login when parameters change. Unknown accounts still run
  Argon2 verification against a dummy hash.
- Session/CSRF/email tokens each contain 32 cryptographically random bytes.
  PostgreSQL stores only SHA-256 hashes of these high-entropy tokens. Passwords
  are never hashed with SHA-256.
- Account sessions expire absolutely after seven days and after 24 hours of
  inactivity. Valid requests update activity without extending absolute expiry.
  Login invalidates the prior session before issuing a new identity.
- Cookies are HttpOnly, SameSite=Lax, Path=/, and host-only. In production both
  use the `__Host-` prefix and Secure. Development uses unprefixed HTTP cookies.
- Verification codes expire after 24 hours; password-reset codes after 30 minutes.
  New requests supersede older codes of the same purpose. Consumption is atomic,
  serialized by a user row lock. Reset and login share that lock so reset cannot
  leave behind a session established concurrently with the old password.
- Email codes appear only in SMTP content. The current emails contain codes for
  API verification; there are no links to unfinished frontend pages.

Account/token persistence commits before SMTP starts, with no open database
transaction during delivery. On delivery failure, the token is invalidated;
resend/recovery issues a fresh one. The account remains recoverable. Process
failure after commit but before delivery may require a resend. Authentication
email delivery is synchronous in this milestone; no queue or plaintext-token
outbox is introduced.

## Shared throttling

PostgreSQL upserts atomically update fixed-window counters; state is shared across
API processes and counts failed attempts. Keys are hashed rather than stored as
raw addresses/IPs. They are not an anonymity guarantee for low-entropy inputs.

| Scope                               | Limit                                                  |
| ----------------------------------- | ------------------------------------------------------ |
| CSRF bootstrap                      | 60 requests / IP / hour                                |
| Login                               | 20 requests / IP / 15 minutes; 10 / email / 15 minutes |
| Register, resend, forgot (combined) | 10 requests / IP / hour; 3 / email / hour              |
| Verify and reset (combined)         | 20 requests / IP / 15 minutes                          |

Exceeded limits return `429 rate_limited` with a conservative `Retry-After`
matching the affected window length. Expired buckets reset on use. Expired
session/token pruning is deferred to the planned maintenance milestone; expiry
is enforced on every lookup regardless of whether rows have been pruned.

## Manual API exercise

From an activated development environment, run `python` and enter the following.
Passwords and codes use hidden prompts; do not print cookie jars or full request
objects. Keep the API and Mailpit running in their separate terminals.

```python
from getpass import getpass
import httpx

client = httpx.Client(
    base_url="http://127.0.0.1:8000/api/v1/auth",
    headers={"Origin": "http://localhost:3000"},
    trust_env=False,
    timeout=15,
)

def csrf():
    response = client.get("/csrf")
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]

csrf()
email = input("Email: ")
password = getpass("Password (12–128 characters): ")
client.post("/register", json={"email": email, "password": password}).raise_for_status()
code = getpass("Verification code from Mailpit: ")
client.post("/verify-email", json={"token": code}).raise_for_status()
client.post("/login", json={"email": email, "password": password}).raise_for_status()
csrf()
assert client.get("/me").status_code == 200
client.post("/forgot-password", json={"email": email}).raise_for_status()
code = getpass("Reset code from Mailpit: ")
password = getpass("New password: ")
client.post("/reset-password", json={"token": code, "password": password}).raise_for_status()
assert client.get("/me").status_code == 401
csrf()
client.post("/login", json={"email": email, "password": password}).raise_for_status()
csrf()
client.post("/logout").raise_for_status()
assert client.get("/me").status_code == 401
client.close()
```

## Automated checks

Set `TEST_DATABASE_URL` as described in the database guide. Default unit tests
need neither PostgreSQL nor Mailpit. Integration tests use fresh migrated
PostgreSQL schemas and capture most emails in a test-only in-memory outbox.
The explicit Mailpit test sends real SMTP verification/reset messages to unique
synthetic addresses and retrieves them through Mailpit's local API.

```bash
python -m pytest
python -m pytest --run-integration
python -m pytest --run-integration --run-mailpit
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pip check
```

The Mailpit test expects SMTP on `127.0.0.1:1025` and its API on
`http://127.0.0.1:8025` (`TEST_MAILPIT_URL` can override the API URL). It fails when
explicitly enabled without a working Mailpit. Use a local test instance only.
The test covers receipt and use of both kinds of code without printing them.

Validation for this milestone used Windows Python 3.13, PostgreSQL 18.3, and
portable Mailpit 1.31.2. WSL2 Ubuntu validation remains pending availability of
that environment. Existing Starlette/AnyIO test-client deprecations remain
visible. No frontend changes, Docker services, or deployment were introduced.

References: [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [Argon2-cffi PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/api.html).
