# Safe manual probes

Milestone 9 executes one real GET or HEAD for an enabled, saved monitor owned by
a verified account. There is no browser action or API endpoint for immediate
probing. Milestone 10 adds [Celery execution and lease recovery](jobs.md).
Milestone 11 adds [scheduling](scheduling.md); milestone 12 adds [scheduled retries
and incident views](incidents.md). Assertions and raw check history views remain deferred.

## Run a saved monitor

Use the WSL backend virtual environment and database configuration from the
[development guide](development.md). In a separate backend terminal:

```bash
source ../.venv/bin/activate
python -m alembic upgrade head
python -m app.monitoring.cli --help
python -m app.monitoring.cli YOUR_SAVED_MONITOR_UUID
```

Replace the UUID placeholder with the ID from the monitor's edit URL or owned
monitor API response. The command rejects URL arguments. It uses the monitor's
stored method, expected status, timeout, and configuration version. This is a
trusted local operator tool with database access, not an account authorization
endpoint. Paused, archived, unverified-owner, and already-running monitors are
rejected before network work.

The final JSON line includes run/check IDs, attempt outcome, nullable HTTP status,
duration in milliseconds, and a safe error code. Exit codes are 0 for successful
HTTP evaluation, 1 for an unsuccessful probe, and 2 for invalid input,
configuration, or persistence failure. Duration covers DNS, connection, TLS,
headers, and bounded body consumption, measured with a monotonic clock.
Structured completion logs contain correlation IDs, never request URLs, response
bodies, cookies, authorization headers, or raw exception messages.

## Persistence and health semantics

Revision `277e61607ff2` adds `check_runs` and `checks`. A short transaction locks
the monitor, checks eligibility, and creates a manual run. The synchronous
entrypoint invokes the asynchronous executor with `asyncio.run`; no database
session or transaction remains open during network I/O. A second transaction
persists attempt 1 and completes the run. Database constraints enforce one active
run per monitor, unique scheduled times, and unique attempt numbers. Milestone 10
uses the same pending-run and fenced-lease path for direct and queued probes.
Repeated or expired-lease completion cannot insert another attempt.

If the monitor was edited, paused, or archived during execution, the attempt is
retained but its run is cancelled and current monitor data is not updated.
Otherwise a successful or failed HTTP evaluation updates the latest-check time.
Blocked destinations and infrastructure failures do not update target health.
An infrastructure failure has a separate run state and outcome.

Manual probes remain single-attempt diagnostics and do not change health or
open/resolve incidents. Scheduled probes use the [milestone 12 retry policy](incidents.md). A monitor with an observation
and unknown health displays **Health not evaluated**. The command reports the
attempt's outcome; inspect the run state to distinguish a subsequently cancelled
run. Manual runs are explicitly tagged `trigger = 'manual'` so future scheduled
[dashboard uptime calculations](dashboard.md) exclude them.

To inspect evidence without retrieving URLs or bodies, connect to the development
database with `psql` and substitute the reported run ID:

```sql
SELECT r.id, r.state, r.trigger, r.configuration_version, r.final_outcome,
       c.started_at, c.finished_at, c.http_status, c.duration_ms, c.error_code
FROM check_runs AS r LEFT JOIN checks AS c ON c.run_id = r.id
WHERE r.id = 'REPORTED_RUN_UUID';
```

## Connection and response policy

- Only HTTP/HTTPS, GET/HEAD, and ports 80/443 are accepted normally. Credentials,
  fragments, control characters, malformed hosts, and URL lengths over 2,048
  characters are rejected.
- Asynchronous DNS resolves A and AAAA with search suffixes disabled. Every
  returned address must pass policy before any connection is attempted. Mixed
  public/private answers fail closed. IPv4-mapped IPv6 is normalized; non-public,
  reserved, loopback, link-local, multicast, metadata, and transition addresses
  are blocked.
- The network backend connects to a validated numeric address, with no second
  hostname lookup. The original hostname remains in Host and TLS SNI/certificate
  validation. Each probe creates its own client/pool and revalidates DNS.
- TLS verification stays enabled. Caller-supplied Host, authorization headers,
  TLS-name overrides, and tracing extensions are discarded. Automatic redirects,
  HTTP retries, and ambient proxy configuration are disabled.
- One total deadline covers DNS through body consumption. Wire body and decoded
  body limits are independently 1 MiB. Content-Length can reject early; streaming
  counters also handle missing lengths and compressed responses. Small bounded
  reads detect overflow without buffering the full response. HTTP framing plus
  headers have a separate 1 MiB + 64 KiB transport budget; excessive framing may
  therefore reject an otherwise small payload.
- Identity, gzip, and zlib-wrapped deflate are supported. Other encodings,
  concatenated gzip members, and truncated/invalid compression fail safely.
  HEAD does not consume a body. JSON content is not parsed until assertions are
  implemented; malformed JSON alone does not fail a matching HTTP status.

The adapter uses the public [HTTPX transport interface](https://www.python-httpx.org/advanced/transports/)
and [HTTPCore network backend interface](https://www.encode.io/httpcore/network-backends/).
The address/redirect policy follows the relevant
[OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
Deployment-level outbound network isolation is still required in the later AWS
design; this milestone does not configure infrastructure.

## Controlled tests

From the activated backend environment:

```bash
python -m pytest tests/test_probe_policy.py tests/test_probe_execution.py
export TEST_DATABASE_URL='postgresql+psycopg://devpulse_test_owner:REPLACE_ME@127.0.0.1:5432/devpulse_test'
python -m pytest tests/integration/test_probes.py tests/integration/test_persistence.py --run-integration
```

Tests start ephemeral loopback HTTP/HTTPS fixtures, generate a temporary trusted
CA in memory, and verify both correct and mismatched certificate hostnames. They
cover status matching, redirects, rebinding/mixed DNS answers, timeouts, streaming
deadlines, malformed responses, oversized bodies, compression bombs, persistence,
concurrency, configuration changes, and log privacy. Fixtures are not application
routes and require no global certificates or host-file changes.

Tests pass exact `(host, port, loopback address)` exceptions through settings.
For a manually controlled local fixture, an explicitly non-production environment
may set, for example:

```bash
export DEVPULSE_PROBE_FIXTURE_DESTINATIONS='[{"host":"127.0.0.1","port":8081,"address":"127.0.0.1"}]'
```

This does not provision a fixture or relax monitor API port validation. Automated
tests save fixture monitors directly in isolated test schemas. The default is
`[]`; production startup rejects any exception, and transport policy also ignores
exceptions in production. Never enable fixture exceptions for public deployment.

## Current operational limits

A process crash or database failure after run creation can leave a run active.
Inspect its evidence before retrying. Milestone 10 permits republishing the same
durable run ID after lease expiry; see [manual recovery](jobs.md#manual-recovery).
Milestone 11 automatically reconciles eligible pending/expired work. This is
infrastructure recovery; milestone 12 separately handles ten-second target-failure retries. A request may have
reached its target even if persistence failed, so do not assume exactly-once
network execution. DNS resolver/service and local-resource failures are separated
from ordinary target failures where identifiable; the total deadline can also
expire while awaiting DNS.

Validation in this milestone used Python 3.13 and PostgreSQL 18 on Windows because
Ubuntu WSL2 was unavailable. Milestone 10 separately records [Linux validation](jobs.md#validation). No external monitored websites or cloud resources were used in
the test evidence.

## Milestone validation

On September 24, 2026, the complete backend run passed 159 tests with real
PostgreSQL and Mailpit enabled, including 43 probe-specific scenarios. Ruff,
strict mypy, dependency consistency, backend import, migration upgrade/head,
and Alembic drift checks passed. Frontend formatting, lint, typing, 57 component
tests, generated API contract verification, production build, and all six
Playwright browser workflows passed.

Regression runs exposed two existing test timing assumptions: password-reset
concurrency needed a fresh CSRF token before a subsequent login, and browser
registration needed to wait for navigation before filling fields shared with
Login. The tests now model those transitions explicitly; authentication behavior
was unchanged. The two existing Starlette/AnyIO deprecation warnings remain
visible. These are historical milestone 9 results; current worker validation is
recorded in the milestone 10 guide.
