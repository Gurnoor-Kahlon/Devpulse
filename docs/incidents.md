# Retries and incident lifecycle

Milestone 12 adds scheduled target-failure retries, atomic health/incident
transitions, retained evidence, and authenticated incident lists/details.
Use the existing [scheduler startup](scheduling.md#startup): one Beat process,
one maintenance worker, and probe workers sharing PostgreSQL and Redis settings.
No browser/API request initiates a probe.

## Migration

Stop application workers, then run from the activated backend environment:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
```

The new head is `d93f8b2e015c`, following `c82e7a1d904b`. It adds
`check_runs.attempt_count`, constrained to 0–3, and the `incidents` table.
Existing attempt counts are backfilled from stored checks. Existing history and
pending work are preserved; the migration does not invent historical incidents.
Downgrades remove the new incident data and are tested only in disposable schemas.

## Scheduled attempts

| Accepted observation | Run and health behavior |
| --- | --- |
| First target failure | Save attempt 1; leave the run pending for ten seconds. Health becomes `confirming_failure`, or stays `down` if an incident is already open. |
| Second target failure | Save attempt 2; leave the same run pending for another ten seconds. |
| Third target failure | Save attempt 3; complete the run as failed, set health to `down`, and open an incident if none is already open. |
| Success at any attempt | Complete the run successfully, set health to `operational`, and resolve an existing incident. |
| Blocked destination or infrastructure failure | End this run without confirming or resolving an incident. Clear an unconfirmed failure state to `unknown`; an existing incident stays open. |

The retry becomes eligible ten seconds after the previous result is persisted,
measured with PostgreSQL's clock. The five-second dispatcher cadence and queue
latency can delay execution beyond that point. Workers do not sleep, schedule
Celery ETA tasks, or rely on broker retry counters. Durable `next_attempt_at` and
`next_publish_at` determine eligibility after process/broker restarts.

All attempts share one scheduled run ID and configuration version. Active-run
uniqueness prevents overlapping schedules. Each claim receives a new fenced
lease; an expired worker cannot add an attempt or transition an incident. A
replacement claim repeats the next unsaved attempt number. External GET/HEAD
requests may repeat after a crash; stored effects remain deduplicated.

Unstarted scheduled work retains the one-interval age limit. Once an attempt is
stored, continuations have the greater of one interval or 180 seconds from the
original scheduled time. This bounded window accommodates retries and lease
recovery. Older work is cancelled and the scheduler considers current work;
missed historical intervals are never replayed in a burst.

Manual operator probes remain single-attempt diagnostics. They update accepted
latest-check evidence but neither retry target failures nor change health or
incidents. They remain excluded from future scheduled uptime calculations.

## Atomic transitions and evidence

A completion transaction locks the monitor before the run, verifies the current
lease and configuration, and stores the attempt, run timing/outcome, freshness,
health, and incident transition together. A failed commit leaves no partial
incident or attempt; the existing lease recovery path handles unfinished work.
No database transaction remains open during network I/O.

An incident starts at the first failed attempt's start time; confirmation is
recorded separately when the third failure finishes. A later successful scheduled
attempt records recovery. Timestamp ordering is bounded against wall-clock
corrections. Repeated failures keep the same unresolved incident, enforced by a
partial unique index. A later failure sequence after recovery can open a new one.

Pausing, archiving, configuration changes, obsolete work, blocked destinations,
and infrastructure failures never imply target recovery. Ineligible work is
cancelled; a pending unconfirmed failure is cleared when that cancellation is
processed. Archived monitors retain owned incident history. Observation freshness
remains separate: stale observations are not proof that a target is down.

Each incident retains the monitor name at confirmation and compact snapshots of
the opening, confirmation, and recovery observations. Snapshots include attempt
number, configuration version, method/expected status, timestamps, outcome, HTTP
status when received, duration, and fixed safe error code/message. They contain
no URL, query string, credentials, response body, or headers. They do not depend
on the monitor's later settings.

Run/check references are optional and use `ON DELETE SET NULL`. Deleting raw
checks or runs preserves the incident and its snapshots. Monitor deletion stays
an archive operation; its incident foreign key restricts hard deletion. The
planned retention policy remains 30 days for raw runs/checks and indefinite
incident evidence. Automated pruning jobs belong to milestone 16 and are not
introduced here.

## Read-only API and views

Both endpoints require the existing account session and return only owned data,
with private no-store responses. An inaccessible resource returns 404;
unauthenticated access returns 401. No incident mutation endpoint is provided.

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/incidents` | Summary page with `items` and `next_cursor`. Optional `status=open|resolved`, `monitor_id`, `cursor`, and `limit` (default 25, maximum 100). |
| `GET /api/v1/incidents/{id}` | Summary, optional raw references, and retained opening/confirmation/recovery evidence. |

The list orders by first-failure timestamp and UUID descending. A cursor keeps
pagination stable when new incidents arrive. Filtering by an archived owned
monitor is supported. A malformed cursor yields a safe validation error.

The workspace navigation links to `/incidents`, and each monitor links to its
filtered list. Lists support status filtering, older/newest pages, explicit
refresh, and loading/empty/error states. `/incidents/[id]` shows the three
observations with separate first-failure, confirmation, and recovery times.
Unresolved incidents say recovery has not been observed. Retained evidence
remains usable after archival and raw-history deletion. An empty list does not
claim uninterrupted availability.

These views use the generated FastAPI TypeScript contract and the existing
TanStack Query/session handling. Milestone 13 adds [dashboard analytics](dashboard.md)
and visible-tab polling to incident lists/details. Milestone 14 links incident
details to [monitor history](monitor-history.md), including archived monitors.
Notification delivery and response assertions remain deferred.

## Validation

Use the root `.venv` and the ignored `backend/.env.test` containing the existing
dedicated `_test` database and test Redis connection. From `backend/`:

```bash
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir /tmp/devpulse-m12-mypy
python -m pip check
python - <<'PYTEST'
import os
import pytest
from dotenv import dotenv_values

os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker']))
PYTEST
```

The integration suite covers early retry rejection, attempts 1–3, success at any
attempt, concurrent confirmations/recoveries, repeated and new incidents,
rollback after transition writes, expired-token fencing, worker restart, bounded
continuations, edits/pause/archive, infrastructure exclusions, ownership,
pagination, retained evidence, migration backfill/roundtrip, and schema drift.
The Redis/prefork test waits the actual ten seconds between controlled failed
HTTP requests and restarts the worker between attempts. Other tests can advance
isolated fixture timestamps to exercise eligibility without unnecessary waits.

From `frontend/` with Node.js 24:

```bash
npm run api:check
npm run check
npm run build
# Export TEST_DATABASE_URL using the existing private test configuration first.
TEST_INCIDENT_FIXTURES=1 npm run test:e2e -- incidents.spec.ts
```

The opt-in browser fixture creates a verified test account and performs real
loopback probes through the completion pipeline in a random test schema. Its
retry timestamps are accelerated. It then archives the monitor and removes raw
runs, exercising retained evidence through the real API. No Mailpit dependency
or development monitoring data is needed for this test. The runner requires
ports 8000 and 3000 to be free, owns its server processes, and removes its schema
on shutdown. `PLAYWRIGHT_BROWSERS_PATH` can point to an existing Linux browser
cache; see the [development guide](development.md) for normal browser setup.

### Linux validation record — September 25, 2026 (America/Toronto)

- Python 3.13.15, PostgreSQL 18.6, Redis 7.0.15, real Celery prefork workers,
  and Node.js 24.21.0 in the existing Ubuntu workspace.
- Development migration upgraded to `d93f8b2e015c`; head and Alembic drift checks
  passed. Migration rollback/re-upgrade and existing-attempt backfill passed in
  isolated test schemas.
- Full backend suite: **214 passed, 1 skipped** in 171.12 seconds. The optional
  Mailpit test was skipped; two existing Starlette/AnyIO deprecation warnings
  remain. Real retry spacing, worker restart, recovery, and the existing Beat,
  broker-loss, persistence, and lease-fencing tests passed.
- Ruff lint and format passed (79 Python files), strict mypy passed (45 application
  files), and dependency consistency passed. No Python dependency pins changed.
- Frontend formatting, ESLint, strict TypeScript, **67 component/client tests**,
  generated contract verification, and production build passed.
- The real browser incident workflow passed at 1280px and 360px widths, including
  status filtering, open/resolved details, refresh/reload, retained evidence, and
  no horizontal overflow on the detail view. Other SMTP-dependent browser flows
  were not rerun.
- Linux Chromium was downloaded under `/tmp/devpulse-m12-browsers`. Its missing
  NSPR, NSS, and ALSA runtime libraries were downloaded from Ubuntu packages and
  extracted under `/tmp/devpulse-m12-browser-libs`, supplied through a test-only
  `LD_LIBRARY_PATH`. No machine packages or services were installed or changed.
  The temporary Node toolchain was reused from milestone 11.

Test harnesses stopped their own browser/API/worker/Beat processes. Start the
three documented scheduler processes for ongoing development monitoring.
This historical record predates milestone 13. Suggested milestone 12 commit message:
`feat: add durable retries and incident lifecycle`.
