# Incident email and retention

Milestone 16 adds opt-in incident email, durable delivery status, and bounded
retention jobs. PostgreSQL owns delivery intent and retries; Redis transports UUIDs.
The page at `/notifications` manages preferences and displays delivery history.
Incident detail pages also show their scoped delivery status. Public demo work
and deployment remain outside this milestone.

## Preferences and API

Each account has one email channel, using its verified account address. There is
no arbitrary destination, webhook, test-send endpoint, or per-monitor override.
Email is disabled by default, including for existing verified users. Enabling
email applies only to future transitions; old incidents are not backfilled.
Confirmation and recovery preferences can be selected independently.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/notifications/preferences` | Current choices, version, account destination, and verification status |
| `PUT /api/v1/notifications/preferences` | Atomic versioned replacement of `enabled`, `on_open`, and `on_recovery` |
| `GET /api/v1/notifications/deliveries` | Owned status history; optional `incident_id`, cursor, and limit (default 25, maximum 100) |

All routes require an authenticated session and use the existing private no-store
policy. Writes require Origin and CSRF validation. Enabling requires a verified
email; destinations cannot be supplied in the request. Unknown or foreign
incident filters return 404. Stale preference versions return 409.

An account without a saved channel reads as disabled, with version zero and both
transition options selected. The first save creates version one; subsequent changed
saves increment it, and unchanged saves preserve it. Example first opt-in:

```json
{
  "configuration_version": 0,
  "enabled": true,
  "on_open": true,
  "on_recovery": true
}
```

Disabling a transition cancels its pending deliveries and marks in-flight ones to
stop further attempts. An SMTP send already claimed cannot be recalled. Successful
in-flight acceptance is still recorded honestly as sent; failure or an expired
lease stops without another send. Re-enabling does not revive these cancelled
attempts. Pausing or archiving a monitor does not invent recovery or cancel an
already recorded incident email; email preferences control that separately.

The editor preserves failed/conflicting drafts until an explicit reload. It does
not poll over active edits. Delivery history uses the existing 15-second visible-tab
polling with error backoff and hidden-tab pause. Reads never send mail.

## Transactional delivery and retries

The first two failed probe attempts do not create mail. Incident confirmation
creates an `opened` delivery; a successful scheduled recovery creates a `resolved`
delivery. Each intent commits in the same PostgreSQL transaction as its incident
transition and check. Uniqueness on `(incident_id, transition, channel_id)` prevents
duplicate intent. A transaction rollback removes both the transition and its intent.
No SMTP or Redis call occurs in that transaction.

Beat schedules `devpulse.notification.dispatch` every five seconds on `maintenance`.
It reserves at most 25 eligible deliveries, commits, then publishes only delivery
UUIDs to `devpulse.notification.deliver` on `notifications`. Publication has a
15-second budget and stops at the first broker failure. A 30-second reservation
cooldown permits reconciliation after lost publication, lost broker messages, or
worker failure. Redis is not a result or delivery-history database.

A sender locks channel then delivery, checks current eligibility and verification,
and takes a fresh UUID lease for 60 seconds. It increments the attempt count at
claim, closes the database session, and sends SMTP. Completion requires the same
unexpired token. Duplicate messages, expired senders, and repeated completion cannot
overwrite newer state. Recovery waits until its corresponding confirmation delivery
is terminal, so retries do not reorder the two recorded transitions.

At most five SMTP attempts are allowed, including interrupted attempts. Retry delays
after failures are 30, 120, 600, and 1,800 seconds, based on PostgreSQL UTC. Workers
do not sleep between attempts. SMTP 4xx responses and network/ambiguous errors retry;
5xx rejection is terminal. At the final expired lease, acceptance is recorded as
unknown and no sixth attempt is sent. Failed deliveries are terminal; changing
preferences or SMTP settings does not silently resend them.

The standard-library [SMTP client](https://docs.python.org/3/library/smtplib.html)
uses a five-second socket timeout and the existing plain/STARTTLS/TLS settings.
TLS modes verify certificates; production rejects plain SMTP. Celery's existing
40-second soft and 45-second hard limits bound stuck sends. A failed QUIT does not
turn an already acknowledged DATA response into a failed delivery. All connections
close, and no database transaction survives SMTP I/O.

SMTP acceptance and the PostgreSQL completion cannot be atomic. A worker can die
or lose database access after the server accepted mail. Reconciliation can therefore
send a duplicate. Each delivery uses the same Message-ID across attempts, but this
does not guarantee provider deduplication. The UI says **Accepted by SMTP**, not
“delivered to inbox.” There are no bounce callbacks, inbox verification, or
exactly-once email claims.

| Stored status | Meaning |
| --- | --- |
| `pending` | Waiting for initial send, retry time, or earlier confirmation delivery |
| `sending` | A leased attempt is in progress; interruption may leave it until lease expiry |
| `sent` | SMTP acknowledged acceptance and that completion was persisted |
| `failed` | Permanent rejection, retry exhaustion, or exhausted interrupted attempts |
| `cancelled` | Further sending stopped because preferences or verification disallow it |

The API exposes attempt counts, created/completed times, the next eligible time,
cancellation requests, and fixed error codes. It never exposes raw SMTP responses,
credentials, recipients other than the account's own preference destination, or
message bodies. Notification failures do not rewrite monitor health, incident
state, or uptime. Database outages leave intent/leases recoverable.

## Email content and privacy

Confirmation and recovery have fixed subjects, plain-text and escaped HTML bodies,
UTC event dates, the captured monitor name, and links to authenticated incident
history and preferences. Emails describe recorded transitions and direct readers
to the current incident state. A delayed confirmation can mention an already
observed recovery. Target URLs, query strings, response bodies/headers, actual
assertion values, and configured assertion expectations are excluded.

Logs contain UUID delivery IDs, worker PID, fixed events/codes, and whether the
completion was stored or obsolete. SMTP errors and free-form exception text are
not logged. Authentication emails reuse the same connection helper but keep their
existing token and delivery lifecycle.

## Retention

Beat submits `devpulse.retention.prune` every 60 seconds to `maintenance`. A sweep
removes at most 500 terminal runs completed more than 30 days ago, cascading their
raw checks. Pending/running work is excluded. It locks monitors before runs,
matching probe completion and preventing conflicting incident FK updates; busy
rows are skipped. The batch limit and cadence provide headroom over the scheduler's
100 enabled monitors at a minimum 60-second interval. Outages/backlogs can extend
actual retention; this is an eligibility threshold, not an exact deletion deadline.

Each sweep also removes up to 500 expired/inactive sessions, up to 500 tokens expired
or consumed more than one day ago, and up to 500 expired rate-limit buckets, each
in a separate short transaction. Current sessions, usable tokens, and active
rate-limit buckets are preserved. Database failures roll back their current batch;
earlier committed batches remain valid and a later tick continues.

Incident opening/confirmation/recovery evidence, including assertion snapshots,
and notification status are retained indefinitely. Raw run/check references become
null through the existing foreign keys. Monitor archives and definitions are not
removed. Analytics continue to describe only retained observations and show gaps
or No data when raw history is gone. No aggregate history is fabricated.

## Migration and local operation

Migration `f16b4d8e302a` follows `e15a9c7d204f`. It adds `notification_channels`,
`notification_deliveries`, delivery constraints/indexes, and a terminal-run retention
index. It does not opt users in, invent past deliveries, or delete history during
migration. Downgrade removes channel/delivery status and the new index; it does not
restore previously pruned raw data.

Stop old API/workers, migrate, then restart with the new code. Use the existing
Ubuntu `.venv`, PostgreSQL 18, Redis, and SMTP configuration in private `backend/.env`.
Local [Mailpit](https://mailpit.axllent.org/docs/install/) must bind to loopback and
capture development/test mail. No external mail service or cloud deployment is
configured by this milestone.

For the Linux Mailpit binary already cached during validation, start a separate
terminal from the project root (it captures mail locally):

```bash
.cache/mailpit-linux/v1.31.2/mailpit --smtp 127.0.0.1:1025 --listen 127.0.0.1:8025 --database .cache/mailpit-linux/devpulse.db --disable-version-check
```

From the activated backend environment:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check

# Probe worker, in its own terminal.
python -m celery -A app.jobs.celery_app:celery_app --quiet worker --pool=prefork --queues=probes --concurrency=2 --without-gossip --without-mingle --without-heartbeat --loglevel=INFO

# Maintenance and notification worker, in its own terminal.
python -m celery -A app.jobs.celery_app:celery_app --quiet worker --pool=prefork --queues=maintenance,notifications --concurrency=2 --without-gossip --without-mingle --without-heartbeat --loglevel=INFO

# Exactly one Beat process, in its own terminal.
python -m celery -A app.jobs.celery_app:celery_app beat --schedule=../.cache/celerybeat --loglevel=INFO
```

The maintenance worker must consume both queues. SMTP work does not occupy probe
worker slots. Beat only publishes periodic tasks; it does not hold authoritative
retry state. After outages, restart the same components; pending deliveries and
expired leases reconcile automatically. Investigate persistent `failed` deliveries
using their safe status code and local SMTP configuration. Do not reset a delivery
row or blindly republish a terminal ID expecting a new send.

## Validation

Backend tests isolate PostgreSQL schemas and Redis prefixes; they never flush
Redis or seed development monitoring history. Use local Mailpit for the full email
suite. From `backend/`:

```bash
../.venv/bin/python -m ruff check .
../.venv/bin/python -m ruff format --check .
../.venv/bin/python -m mypy app
../.venv/bin/python -m pip check
../.venv/bin/python - <<'PY'
import os
import pytest
from dotenv import dotenv_values
os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker', '--run-mailpit']))
PY
```

From `frontend/`, with the private `TEST_DATABASE_URL` loaded and Linux Chromium
available through `PLAYWRIGHT_BROWSERS_PATH`:

```bash
npm run api:check
npm run check
npm run build
TEST_NOTIFICATION_FIXTURES=1 npm run test:e2e -- notifications.spec.ts
```

The notification browser fixture records real loopback probe failures/recovery,
sends their three transition emails to local Mailpit, and displays the persisted
status. Only test probe retry timestamps are accelerated. Separate real Celery
coverage checks duplicate jobs, restart with the actual 30-second retry deadline,
worker death after SMTP acceptance, stable Message-ID on possible duplicate sends,
and retention on a real maintenance worker.

## Verified milestone 16 result — 2026-09-28

- The full backend suite passed **306 tests**, including PostgreSQL, real Redis/Celery
  prefork workers, and Mailpit, with no skips. After the final SMTP teardown and
  retention-cadence adjustments, the affected email/authentication, notification,
  retention, and worker tests passed **47 tests**, including two added teardown cases.
  Existing Starlette/AnyIO deprecation warnings remain.
- Real worker evidence includes confirmation/recovery delivery to Mailpit,
  duplicate-job suppression, persisted 30-second retry deadlines across restart,
  killed senders after SMTP acceptance, and raw-history pruning on a maintenance worker.
- Frontend: **102 tests passed**, plus formatting, ESLint, strict TypeScript,
  generated API contract drift checks, and the production build.
- Chromium: the notification workflow passed with actual SMTP-backed delivery
  history, saved preferences, and 1280px/360px layouts without horizontal overflow
  or browser page errors. Screenshots are in `.cache/ui-review/m16/` locally.
- Ruff lint/format checks passed for **109 Python files**, mypy for **64 application
  files**, and dependency consistency passed. No Python/npm dependency or lockfile
  changes were needed.
- Development migration is `f16b4d8e302a`; head and schema drift checks passed.
  Isolated schemas exercised upgrade/downgrade, transaction rollback, ownership,
  preference races, exhausted attempts, retention cutoffs, and retained evidence.
- The project-local Mailpit 1.31.2 Linux archive was checked against its official
  release-asset SHA-256 digest. Test Mailpit bound only to loopback and was stopped
  after validation. No messages were sent through an external SMTP service.
- No Git commands, machine installations, ownership/permission changes, deployment,
  or milestone 17 work were performed. Development monitoring history was not seeded.

Suggested commit message: `feat: deliver incident emails reliably and prune expired history`.
Milestone 16 is complete. Stop before milestone 17.
