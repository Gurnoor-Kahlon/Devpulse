# Monitor persistence and API

Milestone 7 introduced owned monitor configurations in PostgreSQL. API requests
only read/write stored state; milestone 11 schedules probes in separate workers. Every new monitor has
`current_state: "unknown"` and `last_completed_check_at: null`. An enabled
configuration is eligible for scheduling while Beat and workers are running.
See [scheduling](scheduling.md) and the [monitor management UI](monitor-ui.md).

## Startup and contracts

Use the [database setup](database.md) and [account setup](authentication.md).
In the activated WSL backend terminal, apply the new migration and start the API:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The current head revision is `e15a9c7d204f` (milestone 15);
[response assertions](assertions.md) share monitor ownership and versioning.
Manual execution is documented in the [probe guide](probes.md).
Development OpenAPI documentation is at
`http://127.0.0.1:8000/docs`. Next.js forwards `/api/v1` through the frontend
origin. Log in using the account UI or the API walkthrough; mutation requests
need the session cookie, exact configured `Origin`, and `X-CSRF-Token` returned
by `/api/v1/auth/csrf`.

The generated frontend contract now includes monitor schemas and routes. From
`frontend/`, run `npm run api:generate` after changing API models and
`npm run api:check` to detect drift. The account-specific client remains limited
to auth routes so monitor creation's `201` response cannot be mistaken for an
account message response.

## Endpoints

| Method and path                                        | Behavior                                                                     |
| ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `GET /api/v1/monitors`                                 | Owned, non-archived monitors, newest first; `items` and `next_cursor`.       |
| `POST /api/v1/monitors`                                | Create configuration; `201`, full monitor response, and relative `Location`. |
| `GET /api/v1/monitors/{id}`                            | One owned, non-archived monitor.                                             |
| `PATCH /api/v1/monitors/{id}`                          | Partial settings update with required `configuration_version`.               |
| `DELETE /api/v1/monitors/{id}?configuration_version=1` | Archive at the supplied version; `204`, empty body.                          |

All endpoints require an active authenticated session. Missing, expired,
anonymous, or revoked sessions receive `401`. Write requests with invalid CSRF
or Origin receive `403`. Every individual read/write includes owner and
non-archived predicates; foreign, absent, and archived IDs return the same
`404 monitor_not_found`. All responses are `Cache-Control: no-store`.

Example create body (only name and URL are required):

```json
{
  "name": "Example API",
  "url": "https://example.com/health",
  "method": "GET",
  "expected_status": 200,
  "interval_seconds": 60,
  "timeout_seconds": 5,
  "enabled": true
}
```

Settings accept a trimmed name of 1–100 characters, GET/HEAD, one expected status
from 200–599, an integer interval of 60–86,400 seconds, an integer timeout of
1–10 seconds, and a boolean enabled flag. Defaults match the example. Numeric
strings, boolean-as-integer values, unsupported properties, and explicit null
settings are rejected with safe `422` errors. IDs, ownership, health, scheduling,
timestamps, and deletion state cannot be supplied by clients.

URLs must be HTTP/HTTPS and at most 2,048 characters before and after
normalization. Hosts/default ports are normalized. Credentials (including empty
userinfo), fragments, whitespace/control characters, backslashes, malformed
authorities, and ports outside 80/443 are rejected. Query strings are stored as
part of the owned configuration and never logged. This is syntax validation,
**not connection-time SSRF protection**. No DNS lookup or HTTP request occurs;
milestone 9 must enforce the full address/transport policy before any probe.

## Edits, pause, and archive

PATCH requires the version last read and at least one setting:

```json
{ "configuration_version": 1, "enabled": false }
```

Both PATCH and DELETE check the version under a row lock. A stale version yields
`409 configuration_conflict`; fetch the latest configuration and review changes
before retrying. Each actual edit increments the version and updates
`updated_at`. An exact no-op PATCH keeps the version and timestamps, but still
checks for stale input. Concurrent edits against one version accept only one
actual change. Archive also increments the version.

Enabled creation, resume, and non-name settings changes set `next_due_at` to
the current UTC time. Renaming leaves the due time unchanged. Pause clears it;
archive clears it, disables the monitor, and records `deleted_at`. Both preserve
the last health state and last completed check timestamp. They are not evidence
of recovery. The current state is independent of `enabled`; future UI can show
paused without overwriting the last observation.

Archive is permanent through this API. It hides the monitor from ordinary reads
and writes while retaining its row for later historical evidence. A repeated
DELETE returns `404`. No hard-delete API exists. The user foreign key uses
`RESTRICT`; deleting an account row cannot silently cascade through monitors.
Runs and retained incident evidence were added in milestones 9 and 12. Archiving
preserves that history and does not resolve an open incident.

## Quotas and transactions

Email must be verified to create any monitor, including paused ones, and to
submit `enabled: true`. Existing unverified accounts may inspect, edit other
settings, pause, and archive their own configurations.

The account quota is ten non-archived monitors, including paused monitors.
Archiving frees an account slot; pausing does not. The system quota is 100
enabled, non-archived monitors. Pausing or archiving frees an enabled slot.
Creating paused monitors does not consume an enabled slot. Rejected requests
return `409 monitor_quota_exceeded` or `409 enabled_monitor_quota_exceeded` with
an explanatory message and leave the configuration unchanged.

Every monitor mutation acquires PostgreSQL transaction advisory lock `7157001`,
then the user row and (when applicable) monitor row. Counts and mutations occur
in that same short transaction, so separate API processes cannot both consume
the last quota slot. A commit or rollback releases the lock automatically.
This deliberately serializes low-volume configuration writes at the initial
100-monitor scale; reads remain concurrent. It does not serialize future probe
execution. Future code that changes monitor quota membership must follow this
same lock protocol. Privileged direct SQL is outside API quota enforcement.
See [PostgreSQL advisory locks](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS).

Database constraints additionally enforce settings bounds, valid health/method
values, positive versions, archived-disabled state, due-time consistency, and
the user foreign key. The owner/creation/ID index serves lists; a partial
`next_due_at` index covers enabled, non-archived rows for future scheduling.

## Pagination

`limit` defaults to 25 and accepts 1–100. Invalid limits receive `422`. Pass
`next_cursor` back as `cursor` without interpreting or changing it. Ordering is
`created_at DESC, id DESC`, so timestamp ties are deterministic. A new monitor
inserted before an existing cursor does not shift later pages. Archived rows
disappear; this is a live list, not a frozen snapshot. A null cursor marks the
end. Cursor syntax is bounded and validated; invalid syntax returns `422`.
Every page independently applies ownership, even if another user's cursor is
supplied. Cursors are positions, not credentials.

## Validation

With `TEST_DATABASE_URL` pointing to the dedicated PostgreSQL test database:

```bash
python -m pytest --run-integration
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

The new tests cover setting/URL boundaries, authentication and CSRF, verification,
owned reads/writes, persisted defaults, cursor ties and concurrent insertions,
conflicting edits, quota races, pause/archive behavior, retained health evidence,
database constraints, upgrade/downgrade, and log privacy. Each integration test
uses a fresh schema in the dedicated test database. No monitored destination is
contacted. Full account email checks additionally require Mailpit and
`--run-mailpit`.

Validation used the existing disposable Windows PostgreSQL 18.3 cluster and
Python 3.13 environment: all 116 backend tests (including PostgreSQL and Mailpit)
and 37 frontend tests passed. Lint, formatting, strict type checks, dependency
consistency, generated-contract drift, and the production frontend build passed.
The development migration reached the head revision with no schema drift;
isolated migration tests exercised downgrade/re-upgrade. The two existing
Starlette/AnyIO deprecation warnings remain visible.

WSL2 Linux execution remains pending until a working
user-provided distribution is available. No new dependencies are required.


## Observation freshness (milestone 11)

Monitor responses include `last_scheduled_check_at` for the current configuration
and a read-only `observation_status`: `paused`, `awaiting_check`, `current`, or
`stale`. Freshness is evaluated at request time. An enabled monitor becomes stale
when two configured intervals have elapsed since its latest accepted scheduled
observation, or since its last configuration change if none exists. Manual
checks and infrastructure failures do not refresh this timestamp. Configuration
changes reset it; historical runs/checks and `last_completed_check_at` remain.

This is distinct from `current_state`: milestone 12 sets `confirming_failure`
during scheduled retries, `down` after confirmation, and `operational` after
success. Manual observations do not change health. See [incident semantics](incidents.md). API reads never dispatch jobs or perform HTTP
probes. See [scheduling semantics](scheduling.md#freshness-and-health) for details.
