# Redis and Celery job execution

Milestone 10 moves saved-monitor probes outside the API into Linux Celery prefork
workers. Operators can create manual runs. Milestone 11 adds [Beat scheduling
and automatic reconciliation](scheduling.md); failure retries and incidents remain
deferred. The milestone 10 validation record below is historical.

## Local configuration and startup

Use the existing Ubuntu-24.04 workspace, root `.venv`, PostgreSQL 18, and Redis.
No containers or machine installations are needed. From the project root:

```bash
source .venv/bin/activate
cd backend
python -m pip install --require-hashes -r requirements-dev.lock --cache-dir /tmp/devpulse-pip-cache
```

`backend/.env` uses `DEVPULSE_DATABASE_URL`, `DEVPULSE_BROKER_URL`, and optionally
`DEVPULSE_BROKER_KEY_PREFIX`; see [the template](../backend/.env.example).
Settings are loaded regardless of the working directory; environment variables
win. The current local PostgreSQL setup uses peer authentication through its
Unix socket; see [database setup](database.md#local-setup). Keep test settings in
the separate ignored `backend/.env.test`, never in the application's `.env`.

Redis defaults to `redis://127.0.0.1:6379/0` and prefix `devpulse:`. Only `redis`
and `rediss` URLs with an explicit database from 0 to 15 are accepted. Query
strings and fragments are rejected; `rediss` requires certificate verification.
Keep the broker private and use distinct prefixes for separate environments.

Stop old direct probe executors and workers before upgrading. Revision
`b31d8e0c6a10` converts unfinished legacy running rows into pending work. The
current head, `c82e7a1d904b`, also supports scheduled publication recovery. Existing
completed evidence is retained. Run from the activated backend directory:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
redis-cli -h 127.0.0.1 -p 6379 ping
python -m celery -A app.jobs.celery_app:celery_app --quiet worker --pool=prefork --queues=probes --concurrency=2 --without-gossip --without-mingle --without-heartbeat --loglevel=INFO
```

The Redis command checks the default local broker and should return `PONG`.
For a differently configured broker, use its existing secure connection setup;
do not put passwords into command arguments. `--quiet` suppresses Celery's raw
configuration banner; the worker emits a sanitized JSON `worker_ready` event
once its consumer is ready. Stop the foreground worker with Ctrl+C for a warm
shutdown. The API's `/health/ready` checks PostgreSQL only; it does not certify
worker or Redis availability.

## Queue one saved monitor

In another activated backend terminal:

```bash
python -m app.jobs.cli enqueue YOUR_SAVED_MONITOR_UUID
```

The monitor must be enabled, unarchived, and owned by a verified account. This is
a trusted local operator command, not a browser or account authorization API.
It accepts saved IDs, never arbitrary URLs. A short PostgreSQL transaction
creates a durable pending run before any publication. The command prints that
run ID before contacting Redis, then prints `published: true` or `false`.

Exit 0 means published, not that the probe succeeded. Exit 1 means publication
failed and the durable run remains available. Exit 2 means input, configuration,
or database failure. If the command is interrupted or a database commit response
is lost, inspect existing runs before enqueueing again. A publication result can
be ambiguous after connection loss; republishing the same ID is safe for stored
effects.

Only the run UUID is sent as the task argument. Task `devpulse.probe.execute`
is routed to queue `probes`; results are disabled, messages use JSON, and Redis
never owns monitoring history. Inspect PostgreSQL for completion:

```sql
SELECT r.id, r.monitor_id, r.state, r.trigger, r.next_attempt_at,
       r.lease_expires_at, r.completed_at, r.final_outcome,
       c.attempt_number, c.http_status, c.duration_ms, c.error_code
FROM check_runs AS r LEFT JOIN checks AS c ON c.run_id = r.id
WHERE r.id = 'REPORTED_RUN_UUID';
```

## Leases, duplicates, and failure semantics

- PostgreSQL permits only one pending/running run per monitor and one stored
  attempt number per run. All mutation paths lock monitor before run.
- A worker claims an eligible run with a fresh UUID lease token and a 60-second
  expiry measured by PostgreSQL's clock. Unexpired leases and future pending
  times cannot be claimed. Paused, archived, unverified-owner, or outdated
  configurations are cancelled before HTTP work.
- Every task creates and disposes its own database engine after fork. No database
  session or transaction remains open during HTTP. Each probe retains the
  existing SSRF checks, pinned destination, TLS verification, and body/deadline
  limits described in [safe probes](probes.md). A backward wall-clock correction
  cannot make a stored finish timestamp precede its start; elapsed duration is
  still measured independently by a monotonic clock.
- Completion requires the current unexpired token. An expired or superseded
  worker cannot persist an attempt or update the monitor. Edits during execution
  retain the attempt under a cancelled run without updating current monitor data.
- Celery uses late acknowledgments, rejects on worker loss, prefetch 1, and
  concurrency 2. Soft/hard task limits are 40/45 seconds, below the 60-second
  lease; Redis visibility timeout is 90 seconds. Long tasks are cancelled on
  broker connection loss. Events and remote control are disabled.
- Publication uses bounded connection/socket timeouts and no automatic retry.
  Database failures leave pending work or an expiring lease, emit a safe
  `job_deferred` event, and never manufacture target downtime. Duplicate,
  ineligible, and already-finished messages emit `job_ignored`.
- Job logs contain run/job UUIDs and worker process IDs, never URLs, query
  strings, payloads, bodies, credentials, or raw exception text. The task result
  backend is disabled; completed evidence lives in PostgreSQL.

Network execution is not exactly once: a GET/HEAD can reach its destination
before a crash or failed database write. Recovery can repeat that request while
stored attempts remain deduplicated. Manual observations update latest-check
time but do not determine aggregate health or incidents and are excluded from
future scheduled uptime calculations.

## Manual recovery

After a failed/lost publication, restart the broker/worker through your normal
local service workflow, inspect the durable run, and republish it:

```bash
python -m app.jobs.cli publish REPORTED_RUN_UUID
```

Pending work can be republished immediately when due. For `running` work, wait
until its lease expires before republishing. A duplicate delivered while the
lease is active is safely ignored and acknowledged; it does not arrange a later
retry. A killed child may cause immediate broker redelivery while its lease is
still active. Milestone 11 reconciliation recovers it after expiry, or cancels
an obsolete scheduled run and schedules current work; manual republication
remains available if the scheduler is stopped. Do not
edit lease fields or create a replacement run as a normal recovery procedure.
Completed/cancelled runs cannot be republished through the command.

Inspect unfinished work without retrieving monitor URLs:

```sql
SELECT id, monitor_id, state, next_attempt_at, lease_expires_at
FROM check_runs
WHERE state IN ('pending', 'running')
ORDER BY scheduled_at;
```

Milestone 11 adds automatic pending reconciliation and scheduled dispatch. Use
the [scheduler startup instructions](scheduling.md#startup) for the current system.

## Validation

From the activated backend directory, load the locally supplied test connection
settings explicitly. The current ignored `.env.test` contains `TEST_DATABASE_URL`
for `devpulse_test` and `TEST_REDIS_URL` for the local Redis database 1. This file
is configuration only, not a service provisioner.

```bash
python -m pip check
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir /tmp/devpulse-m10-mypy
python - <<'PYTEST'
import os
import pytest
from dotenv import dotenv_values

os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker']))
PYTEST
```

Tests require a database ending in `_test`, create isolated random schemas, and
remove only those schemas. Each worker test uses a random Redis prefix and
removes only its keys; it never flushes a Redis database or stops the existing
service. Only worker process groups started by the tests are terminated. HTTP
fixtures stay on loopback with exact non-production destination exceptions.

Coverage includes registration/routing, real HTTP through a prefork worker,
duplicate delivery, lost-message republishing, whole-worker and child loss,
expired/stale lease fencing, broker publication failure, and database lock failure
after HTTP. A deterministic clock-correction regression checks that a successful
probe remains persistable when wall time moves backwards. Recovery tests explicitly expire fixture leases to avoid waiting a
full minute; they still use the real PostgreSQL clock and token checks. Migration
tests exercise upgrade, downgrade/re-upgrade, old unfinished runs, and schema
drift. Mailpit tests require their separate opt-in and local service.

### Ubuntu validation record — September 24, 2026 (America/Toronto)

- Python 3.13.15 in the root `.venv`; hashed development lock installed without
  changing dependency pins. Celery 5.6.3, Redis server 7.0.15, PostgreSQL 18.6.
- Development/test peer connections succeeded with a non-superuser role. The
  development database was upgraded to `b31d8e0c6a10`; the current-head check and
  Alembic drift check passed. No development monitoring observations were created.
- Final complete backend run with `--run-integration --run-worker`: **179 passed,
  1 skipped**, in 60.04 seconds. The skipped test requires unavailable Mailpit;
  no email-service installation was performed. All six real Redis/prefork worker
  tests passed, along with lease/persistence and migration roundtrip coverage.
- Ruff lint and formatting passed (66 Python files); strict mypy passed (39
  application files); `pip check`, application import, OpenAPI generation, and
  the job CLI help command passed.
- The full regression initially exposed a backward wall-clock correction during
  recovery. A deterministic PostgreSQL regression reproduced the stranded run;
  clamping the finish timestamp to at least its start fixed it while retaining
  monotonic duration measurement. The final full run includes that regression.
- Two existing Starlette/AnyIO deprecation warnings remain. Frontend checks and
  browser workflows were not rerun: Linux Node.js was unavailable, and milestone
  10 changes no frontend code or API contracts. Earlier Windows results are not
  claimed as new Linux results.

At milestone 10, test workers were stopped by their harness and normal operation
required manual enqueue/republication. The separate milestone 11
[validation record](scheduling.md#validation) covers automatic execution.
