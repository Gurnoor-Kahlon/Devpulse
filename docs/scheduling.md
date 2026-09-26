# Database-driven scheduling

Milestone 11 adds one Beat process, a maintenance-queue dispatcher, and automatic
recovery of unpublished or expired work. PostgreSQL remains the authority;
Redis transports task messages only. No target-failure retries, incident
transitions, analytics, polling, or notification delivery are added.

## Startup

Use the existing Ubuntu-24.04 environment, root `.venv`, PostgreSQL 18, and Redis.
Stop application workers before upgrading. From the project root:

```bash
source .venv/bin/activate
cd backend
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
```

The head revision is `c82e7a1d904b`. It adds `check_runs.next_publish_at`, a partial
publication index for active runs, and `monitors.last_scheduled_check_at`.
Existing pending work becomes eligible for reconciliation. It preserves old
run/check evidence and does not invent past scheduled observations. Downgrades
are rehearsed only in isolated test schemas, never the development database.

Run each process below in its own activated backend terminal. Use the same
`backend/.env` database, broker, and prefix for all processes:

```bash
# Probe worker: only the probes queue.
python -m celery -A app.jobs.celery_app:celery_app --quiet worker --pool=prefork --queues=probes --concurrency=2 --without-gossip --without-mingle --without-heartbeat --loglevel=INFO
```

```bash
# Maintenance worker: only the maintenance queue.
python -m celery -A app.jobs.celery_app:celery_app --quiet worker --pool=prefork --queues=maintenance --concurrency=1 --without-gossip --without-mingle --without-heartbeat --loglevel=INFO
```

```bash
# Start exactly one Beat process for this broker/database environment.
mkdir -p .cache/celery
python -m celery -A app.jobs.celery_app:celery_app --quiet beat --loglevel=INFO --schedule .cache/celery/beat --pidfile .cache/celery/beat.pid
```

The local pidfile prevents an accidental second Beat using that file; it is not
a distributed leader election mechanism. Do not combine `worker --beat` with the
standalone process. Configuration banners are suppressed by `--quiet`; logs
remain sanitized JSON. Warm-stop Beat and workers with Ctrl+C. The files under
`backend/.cache/` are local scheduler bookkeeping, not monitoring history.

Enabled monitors belonging to verified accounts become eligible immediately.
Creating or viewing a monitor through the API never performs a probe. Beat and
both workers must be running for automatic execution. `/health/ready` still
checks PostgreSQL only, not scheduler health.

## Dispatch and recovery

Beat submits `devpulse.scheduler.dispatch` to the `maintenance` queue every five
seconds. Tick messages expire after five seconds, so obsolete queued ticks can
be discarded. Due state is always read from PostgreSQL at execution time.
Concurrent dispatcher deliveries are safe even though only one Beat is intended.

Each dispatcher uses one short transaction to:

1. Select at most 25 due pending runs or expired running leases. Lock monitors
   first using `FOR UPDATE SKIP LOCKED`, then their active runs, matching the
   worker/API lock order. Skip current leases and future attempt times.
2. Cancel ineligible or obsolete work. Reserve eligible publications by moving
   `next_publish_at` 30 seconds forward, without changing probe eligibility.
3. Claim at most 25 enabled, unarchived, verified-owner monitors whose due time
   has arrived and which have no active run. Create one `scheduled` pending run
   per monitor and atomically advance its next due time.
4. Commit before attempting Redis publication. Only run UUIDs enter probe tasks.

Publication stops on the first broker failure or after a 15-second loop budget;
an in-flight publication also has the existing bounded connection/socket limits.
The maximum reservation batch is 50, independent of total history size. No
database transaction is held during broker or probe network I/O.

A crash after commit, lost message, publication failure, or failed database write
leaves durable work. A later tick reconsiders it once its publication cooldown
and any current lease expire. Reservations are renewed under database locks so
concurrent ticks do not repeatedly publish the same row. Queued duplicates can
still occur; the existing token fencing and uniqueness constraints deduplicate
stored effects. Network GET/HEAD execution can repeat after crashes.

An expired manual run is recovered under the same ID. A scheduled run older than
one configured interval is cancelled instead of replayed; if its monitor is
still due, the dispatcher creates a current scheduled run. The worker performs
the same age/configuration check before HTTP and again on completion. An obsolete
in-flight attempt may be retained under a cancelled run, but it cannot refresh
current monitor evidence. Pausing, archiving, and unverified ownership prevent
new scheduled work. Configuration-version changes invalidate queued work.

`scheduler_dispatched` logs reserved/published counts; `scheduler_deferred`
reports a safe persistence error code. Probe job logs retain run/job UUIDs and
worker process IDs. URLs, query strings, credentials, response bodies, and raw
exception text are excluded. Operators may still use the
[manual recovery commands](jobs.md#manual-recovery) while automatic dispatch is
stopped; do not edit run lease or publication fields as a recovery procedure.

## Missed intervals

The policy is **one current observation, no historical replay**. A monitor due
hours ago gets one run with `scheduled_at` equal to the current PostgreSQL clock,
and its next due time becomes that time plus its interval. It does not receive
one run per missed interval. A monitor with active work receives no overlapping
run; when that work completes or is cancelled, the next tick evaluates its due
time again. Monitor rows and the active-run/scheduled-time constraints prevent
duplicate scheduled identities under concurrency.

Long service outages therefore leave gaps in history. They are neither synthetic
successful checks nor target downtime. New observations resume the cadence from
the next successful dispatch. There is no claim of exact wall-clock cadence or
exactly-once network execution.

## Freshness and health

Responses add `last_scheduled_check_at` and read-only `observation_status`:

| Status | Meaning |
| --- | --- |
| `paused` | Configuration is disabled. |
| `awaiting_check` | No accepted scheduled observation for this configuration, within the initial grace period. |
| `current` | An accepted scheduled observation is less than two intervals old. |
| `stale` | Two intervals elapsed without a new accepted scheduled observation. |

Before the first scheduled observation, the grace period starts at the most
recent configuration change (`updated_at`). Every actual configuration change
increments the version, clears current scheduled freshness, and restarts that
grace period; historical checks remain. A no-op edit changes neither. A rename
still preserves the existing next due time.

Successful and failed target evaluations refresh scheduled freshness. Manual
observations, blocked destinations, cancelled work, and infrastructure failures
do not. The existing latest-check timestamp can still show accepted manual work.
Freshness does not decide aggregate health or incidents: those remain milestone
12. The UI shows **Stale observations** ahead of saved health labels and **Paused**
for disabled monitors. Read time determines freshness; the current list requires
Refresh list for a new reading. Visibility-aware polling remains milestone 13.

## Validation

Use the root virtual environment and the ignored test-only `backend/.env.test`.
From the activated backend directory:

```bash
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir /tmp/devpulse-m11-mypy
python -m pip check
python - <<'PYTEST'
import os
import pytest
from dotenv import dotenv_values

os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker']))
PYTEST
```

Tests use random PostgreSQL schemas in the dedicated `_test` database and random
Redis prefixes, never `FLUSHDB`. Real Beat, maintenance, and probe processes use
the production task configuration; the test worker overrides only the database
schema. The harness stops only its own subprocesses and cleans its own data.
Recovery tests advance fixture cooldown/lease timestamps instead of waiting a
full minute; the actual PostgreSQL eligibility/fencing paths still execute.

Coverage includes concurrent dispatch, row-lock skipping, bounded batches,
missed intervals, active/future/ineligible monitors, broker/message/dispatcher
loss, expired leases, obsolete messages/completions, scheduled freshness,
migration upgrade/downgrade/drift, and the real five-second Beat pipeline.
Frontend types are generated from FastAPI rather than maintained separately.


### Linux validation record — September 25, 2026

- Ubuntu-24.04, root `.venv` Python 3.13.15, real PostgreSQL/Redis, and Celery
  prefork processes. The development database was upgraded to `c82e7a1d904b`;
  current-head and Alembic drift checks passed. Upgrade/downgrade/re-upgrade and
  preservation of milestone 10 pending rows passed in isolated schemas.
- Full backend run with integration/worker flags: **197 passed, 1 skipped** in
  142.97 seconds. This includes a real five-second Beat process, separate
  maintenance/probe queues, all previous worker-loss tests, and the new scheduler
  concurrency/recovery/freshness regressions. Two existing Starlette/AnyIO
  deprecation warnings remain.
- Ruff lint/format checks passed (70 Python files), strict mypy passed (40
  application files), and `pip check` passed. No Python dependency pins changed.
- A SHA-256-verified official Linux Node 24.21.0 toolchain under
  `/tmp/devpulse-node24` enabled frontend validation without a machine install.
  `npm ci` installed the existing lock locally. Frontend formatting, ESLint,
  strict TypeScript, all **58 component/transport tests**, generated FastAPI
  contract verification, and the production build passed. Contract/browser
  scripts now resolve the workspace's root `.venv`.
- Mailpit SMTP/API ports were unavailable. Its one backend email test was skipped
  and SMTP-dependent Playwright workflows were not run. No email service,
  machine package, or cloud resource was installed. Existing npm ESLint
  deprecation/optional install-script notices were not addressed through unrelated
  dependency changes; frontend checks and the build passed with the lock as-is.

The test harness stopped its Beat and worker processes. Start the documented
three processes for ongoing development monitoring; validation did not leave a
background scheduler running against development monitors. No milestone 12
retry or incident behavior is included.
