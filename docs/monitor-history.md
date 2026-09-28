# Monitor detail analytics and check evidence

Milestone 14 adds `/monitors/[id]`. Monitor names in the list open this detail
view; Edit actions still open `/monitors/[id]/edit`. Incident details also link
back to their monitor's history. The page combines current configuration and
health, scoped history windows, a latency trend, final HTTP status distribution,
paginated individual attempts, and the existing owned incident list.

The same [visibility-aware polling](dashboard.md#polling) refreshes stored
analytics, checks, and incidents. Reads never create runs, send network probes,
retry failures, or transition incidents. No new dependencies, database tables,
migrations, retention jobs, or response assertions were introduced by milestone 14.
Milestone 15 adds [assertion snapshots](assertions.md) to expanded check and incident evidence.

## Owned read-only API

| Endpoint | Parameters and response |
| --- | --- |
| `GET /api/v1/monitors/{id}/analytics` | `window=24h|7d|30d`, default `24h`. Returns the current monitor, `archived_at`, requested range, sampled end time, run metrics, UTC buckets, and final HTTP status distribution. |
| `GET /api/v1/monitors/{id}/checks` | Same `window`, plus `limit` (default 25, maximum 100) and optional cursor. Returns frozen range bounds, safe individual attempts, and `next_cursor`. |
| `GET /api/v1/incidents?monitor_id={id}` | Existing paginated incident history across retained time, independent of the selected check window. |

Authentication and ownership are checked by FastAPI. Another account's or a
missing monitor returns 404; unauthenticated access returns 401. Invalid windows,
limits, and cursors return safe 422 responses. All responses use the existing
no-store policy. Browser requests use same-origin cookies and generated FastAPI
TypeScript contracts, consume cancellation signals, and redirect on session expiry.

Archived monitors remain accessible through these history endpoints and incident
links. Existing CRUD access to archived monitors still returns 404. The page
labels archived history read-only and hides Edit settings. Pausing or archiving
does not fabricate recovery or remove past observations.

## Analytics

The monitor analytics service and dashboard now call the same bounded SQL
aggregation function. All [milestone 13 definitions](dashboard.md#metric-definitions)
remain unchanged: successful completed scheduled runs divided by successful plus
failed completed scheduled runs, retries weighted once, and manual, incomplete,
cancelled, blocked, and infrastructure-failed runs excluded. Empty populations
return null percentages and latencies, displayed as **No data**.

History includes earlier configuration versions and retained observations from
before pause/archive. The current method, expected status, URL, interval, and
configuration version are explicitly labelled as current settings; they are not
presented as snapshots of older attempts. The check/run schema previously stored
only the configuration version, so this milestone does not invent missing past
configuration details.

The Recharts latency graph reuses the dashboard's chart implementation. It shows
mean complete-probe duration from final attempts with HTTP responses, grouped by
scheduled time into one-hour, six-hour, or one-day UTC buckets respectively.
Null buckets stay gaps, line interpolation is linear, single samples stay visible,
and animation is disabled. A horizontally scrollable table provides exact bucket
bounds, partial flags, completed-run/response counts, and latency. Its overflow
stays within the page at 360px mobile widths.

HTTP status distribution groups the final HTTP response of each eligible
completed scheduled run by its exact status code. Counts and percentages use
only those final responses, excluding earlier retries, manual diagnostics, and
no-response failures. Labels accompany proportional bars. Status does not itself
determine success: the configured expected status can be something other than 200.
The distribution is a separate bounded aggregate read using the same sampled
window, so concurrent persistence/pruning may be reflected a read later than the
latency summary. No monitoring history is loaded wholesale into application memory.

Requested and observed ranges, sampling time, excluded counts, response counts,
and partial history are visible. Stale observations remain separate from saved
health. The page does not assert continuous coverage, time-weighted availability,
or an SLA.

## Check pagination and safe evidence

The check list intentionally shows individual attempts of both scheduled and
manual runs, including failures, blocked destinations, infrastructure failures,
and attempts retained under cancelled runs. It differs from the aggregate metric
population and says so explicitly. Pending runs without an attempt do not create
an invented check row.

Ordering is descending by run scheduled time, run UUID, then attempt number.
Cursors carry the monitor/window scope, original range bounds, and last ordering
key. A page returns at most `limit` rows plus an opaque continuation cursor.
Checks must belong to a run scheduled within the range and have finished by its
frozen end. Paging keeps these bounds even when time advances or new runs arrive.
The existing monitor/scheduled-time and run/attempt indexes are reused.

A cursor is validated, not trusted as authorization: ownership is checked on every
request and the query still restricts the monitor. Malformed, naive-time,
wrong-window, wrong-monitor, or invalid-range cursors are rejected. This is not a
multi-request database snapshot: rows pruned between pages disappear, late-persisted
observations with old finish times can appear, and run lifecycle labels reflect
current stored state. **Newest checks** returns to a fresh window; changing the
window resets pagination. Older-page polling retains its original bounds.

Expand an attempt for:

- Check/run UUIDs and run scheduled time.
- Manual/scheduled origin, current run state, final outcome if available,
  attempt number, and whether it is the terminal run's final stored attempt.
- The run's recorded configuration version, attempt start/finish, outcome,
  HTTP status when received, and probe duration.
- Fixed safe error code/message from the executor's known vocabulary.

No response body, headers, URL/query string, credentials, lease tokens, or raw
exception text enter check evidence. Stored error text is not copied into the
API: recognized codes are mapped to fixed messages and unknown codes are omitted.
The current monitor URL remains visible only in its owned configuration header,
as in the existing monitor management UI.

Removing raw checks/runs shrinks history and metrics. Incident snapshots remain
available independently, including when the check list becomes empty. Automatic
30-day raw-history pruning is implemented by [milestone 16](notifications.md#retention).

## Validation commands

Use the existing root `.venv`, Node.js 24, PostgreSQL 18, and Redis. The migration
head is now `f16b4d8e302a` (milestone 16). From the activated backend directory:

```bash
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir /tmp/devpulse-m14-mypy
python -m pip check
python -m alembic current --check-heads
python -m alembic check
python - <<'PYTEST'
import os
import pytest
from dotenv import dotenv_values

os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker']))
PYTEST
```

From `frontend/`:

```bash
npm run api:check
npm run check
npm run build
# Export the existing private TEST_DATABASE_URL first.
TEST_MONITOR_HISTORY_FIXTURES=1 npm run test:e2e -- monitor-history.spec.ts
```

The opt-in browser fixture creates real loopback HTTP observations in a random
test schema: three scheduled runs (two confirmed failures and one success) plus
20 single-attempt manual runs. The UI therefore shows 27 raw attempts across two
pages, but only three aggregate observations and 33.33% displayed uptime. Retry
timestamps are accelerated only in the fixture. Tests exercise status counts,
evidence expansion, window changes, editing navigation, archival, retained
incidents, and desktop/mobile layout. The harness stops its own servers and drops
its test schema. No Mailpit or development observations are required.

## Linux validation record — September 26, 2026 (America/Toronto)

- Existing Ubuntu-24.04 environment, Python 3.13.15 in the root `.venv`,
  PostgreSQL 18.6, Redis 7.0.15, and the existing temporary Node.js 24.21.0
  toolchain. No dependency pins changed and no machine packages were installed.
- Full backend suite with integration and worker flags: **226 passed, 1 skipped**
  in 194.58 seconds. This includes the shared dashboard regressions, new monitor
  analytics/pagination/privacy/archive tests, and real Redis/Celery/Beat checks.
  The optional Mailpit test remains skipped; two existing Starlette/AnyIO
  deprecation warnings remain.
- Ruff lint/format passed (87 Python files), strict mypy passed (51 application
  files), dependency consistency passed, and migration head/drift checks passed.
  The migration head remains `d93f8b2e015c`.
- Frontend formatting, ESLint, strict TypeScript, **84 component/client/polling
  tests**, generated API contract verification, and production build passed.
  The production route list includes `/monitors/[id]` alongside existing edit,
  dashboard, and incident routes.
- The real browser monitor-history workflow passed at 1280px and 360px widths:
  three scheduled observations, 33.33% run-weighted uptime, final-status counts,
  27 raw attempts across two pages, evidence expansion, cursor reset, window
  changes, chart/table overflow containment, settings navigation, archive through
  the existing UI, and retained incident/check history after archival. Captured
  mobile layout was reviewed. Browser console errors were checked and absent.
- Browser validation reused the temporary Linux Chromium and runtime libraries
  from milestone 12 with `PLAYWRIGHT_BROWSERS_PATH` and test-only
  `LD_LIBRARY_PATH`. SMTP-dependent account browser workflows were not rerun.
  No service configuration, file ownership, or permissions were changed.

The harness stopped its own servers/workers and removed isolated test schemas.
No development monitoring observations were created. Milestone 15 was not started.
Suggested commit: `feat: add monitor detail analytics and check history`.
