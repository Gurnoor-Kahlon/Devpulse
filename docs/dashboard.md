# Dashboard analytics and polling

Milestone 13 replaces the Overview placeholder with owned PostgreSQL aggregates,
current monitor states, recent incidents, and Recharts trends. It uses the
existing scheduler/worker pipeline and does not dispatch probes from reads.
Milestone 14 adds [per-monitor analytics and check-history pagination](monitor-history.md)
using the same metric rules. Assertions, notifications, retention jobs, public
demo data, and benchmarks remain separate milestones.

## Metric definitions

`GET /api/v1/dashboard?window=24h` requires an authenticated session. Supported
windows are `24h` (default), `7d`, and `30d`; other values return 422. Responses
use the existing private no-store policy. Every history/state/incident query
restricts monitor ownership; archived monitors remain owned. There is no
arbitrary URL or monitor ID parameter and no mutation endpoint.

| Field | Definition |
| --- | --- |
| `start`, `end` | Requested rolling UTC range; start inclusive, end exclusive. The response end is the sampling time. |
| `observations` | Completed scheduled runs with final outcome success/failure, scheduled in the range and completed by the sampling time. |
| `uptime_percent` | 100 × successful runs / observations. Null when there are no observations. |
| `excluded_runs` | Other scheduled runs in the range, including pending/running, cancelled, blocked, infrastructure-failed, or not yet completed by the sampling time. Manual runs are omitted entirely. |
| `response_count` | Eligible runs whose final stored attempt received an HTTP response. |
| `mean_latency_ms` | Sum of those final-attempt durations divided by `response_count`; null without responses. |
| `first_observation_at`, `last_observation_at` | Earliest/latest scheduled time among eligible retained runs in the window, or null. |

Each retry sequence counts as one run. The join selects the attempt matching
`check_runs.attempt_count`, so earlier failures cannot inflate either uptime
weight or latency. Overall uptime is weighted by run counts, not the average of
monitor percentages. Overall latency is weighted by response counts, not the
average of bucket means. An HTTP failure response contributes latency; a failure
without an HTTP response does not. Duration measures the executor's complete
probe duration and is not a server-only response-time measurement.

History includes paused/archived monitors and previous configurations. This
preserves past observations when settings change. Deleting a raw check leaves
its retained run outcome eligible for uptime but removes its latency sample.
Deleting the run removes it from aggregates. The dashboard never reconstructs
removed runs from incident evidence or invents observations for missed schedules.

## Buckets and coverage

The database groups by scheduled time into UTC hour boundaries for `24h`, six-hour
boundaries for `7d`, and day boundaries for `30d`. The rolling window clips the
first/last bucket and marks clipped buckets `partial`. Thus there are at most
25, 29, or 31 buckets respectively. Adjacent bucket edges are contiguous, even
when no observations exist. Changing windows requests a separate cached query;
old-window values are not shown under the new selection.

Each bucket repeats the same metric definitions as the total. SQL aggregates
return bounded bucket rows; Python fills missing buckets with zero counts and
null percentages/latencies. Totals are computed from those same aggregate rows,
so a concurrent completion cannot make chart and summary counts disagree. The
existing monitor/scheduled-time and unique run/attempt indexes support the query;
no new tables, migrations, aggregate cache, or partitioning were needed.

Empty buckets appear as chart gaps. Lines do not bridge null observations, and
no data is never converted to zero or 100%. A single populated bucket is shown
as a point. The accessible expandable table provides exact bucket boundaries,
partial flags, success/failure/excluded counts, percentages, response counts,
and mean latency without relying on color, hover, or chart interaction. Chart
animations are disabled; layouts support 360px and larger widths.

The UI explicitly labels retained history as partial, shows the requested and
observed ranges, and explains that gaps may exist even between recorded checks.
It does not infer historical schedule coverage from today's monitor settings,
guarantee continuity within a populated bucket, or claim SLA/time-weighted
availability. A 100% observed ratio means all counted runs succeeded, not that
unobserved periods were available.

## Current state and incidents

Current state counts cover unarchived monitors only, independent of the selected
history window. Disabled monitors count as paused; enabled monitors count once
as operational, down, confirming failure, or unknown. Stale and awaiting-first-
check counts are separate freshness indicators for enabled monitors, using the
existing two-interval rule. They can overlap saved health categories and must
not be added to the health totals. Stale observations do not imply target failure.

The dashboard also shows the current unresolved incident count and the five
latest incidents across all retained owned history, including archived monitors.
These are labelled as independent of the history window. Links open the existing
incident detail view. Absence of incidents is not presented as proof of availability.
Current state and incident projections are separate reads and may see a newer
worker commit than the chart aggregate; every polling response refreshes them.

## Polling

Dashboard, monitor lists/details, incident lists, and incident details use the shared
`usePollingQuery` hook with TanStack Query:

- Fetch stored results on visible mount and every 15 seconds after completion.
- On consecutive failures, wait 30, 60, then at most 120 seconds; a success resets
  the interval to 15 seconds. There is no additional automatic retry loop.
- Pause scheduled polling while the document is hidden. A visible transition
  fetches fresh data. An already-running read can finish while hidden.
- Deduplicate in-flight requests, consume abort signals, and stop on unmount.
- Stop automatic polling on 401; existing client logic clears CSRF state and
  redirects out of the workspace. Queries retain no shared HTTP cache.
- Preserve cached data on refresh errors with a visible warning and original
  sample time. Manual refresh is available. Initial errors have a retry action.

Window focus/reconnect handlers do not bypass error backoff for these monitoring
queries. Forms, account-session checks, and mutations retain their existing
behavior. Polling never triggers checks, retries, or incident transitions.

## Startup and validation

Use the existing [development environment](development.md) and
[scheduler processes](scheduling.md#startup). Run `npm ci` from `frontend/` to
install the updated lockfile with Recharts 3.10.1. Python dependencies and the
migration head remain unchanged at `d93f8b2e015c`. Apply existing migrations to a
fresh database as usual; no development monitoring data is seeded.

From the activated backend environment, load the private test configuration and
run the suite against the dedicated `_test` database and Redis:

```bash
python -m ruff check . --no-cache
python -m ruff format --check . --no-cache
python -m mypy --cache-dir /tmp/devpulse-m13-mypy
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

From `frontend/` with Node.js 24:

```bash
npm run api:check
npm run check
npm run build
# Export the existing private TEST_DATABASE_URL first.
TEST_DASHBOARD_FIXTURES=1 npm run test:e2e -- dashboard.spec.ts
```

The opt-in browser test uses the existing disposable fixture account and actual
loopback HTTP probes: failure, success, then failure, with three attempts for
each failed run. The result is three observations and 33.33% displayed uptime,
not seven independent observations. Retry timestamps are accelerated only in the
test schema. The browser checks polling, window changes, charts, exact data table,
refresh failure/recovery, incident navigation, and desktop/mobile layout. Its
servers and random schema are removed by the harness. It does not need Mailpit.

Implementation references: [Recharts API](https://recharts.github.io/en-US/api/),
[Recharts accessibility](https://github.com/recharts/recharts/blob/main/storybook/stories/API/Accessibility.mdx),
and [TanStack Query v5 query API](https://tanstack.com/query/latest/docs/framework/react/reference/useQuery).

## Linux validation record — September 26, 2026 (America/Toronto)

- Existing Ubuntu-24.04 workspace, Python 3.13.15 in `.venv`, PostgreSQL 18.6,
  Redis 7.0.15, and the temporary Node.js 24.21.0 toolchain from milestone 11.
- Full backend unit/integration/real-worker suite: **220 passed, 1 skipped** in
  141.25 seconds. The optional Mailpit test remains skipped; two existing
  Starlette/AnyIO deprecation warnings remain. New analytics tests cover ownership,
  weighting, final attempts, all exclusions, inclusive/exclusive boundaries,
  null empty windows, bucket continuity, archived history, current states,
  stale thresholds, preserved run outcomes after check deletion, and read-only
  monitoring behavior. Existing real Redis/Celery/Beat regressions passed.
- Ruff lint/format passed (83 Python files), strict mypy passed (48 application
  files), dependency consistency passed, and migration head/drift checks passed.
  The head is unchanged at `d93f8b2e015c`; no migration was added.
- Frontend formatting, ESLint, strict TypeScript, **77 tests**, generated API
  contract verification, and the production build passed. Tests include real
  Recharts rendering, window/error/empty states, transport/session handling,
  15-second polling, 30/60/120-second backoff, reset on success, hidden-tab pause,
  visible resume, no overlapping requests, expiry, and unmount cleanup.
- The dashboard browser workflow passed against real isolated PostgreSQL/HTTP
  observations at 1280px and 360px, including actual 15-second polling, charts,
  table overflow containment, window changes, simulated service-error recovery,
  and incident navigation. Captured mobile layout was visually reviewed.
  The existing incident browser regression also passed after the polling change.
  Other SMTP-dependent account workflows were not rerun.
- Recharts 3.10.1 was added to the project-local npm manifest/lock. Installation
  reported no vulnerabilities; the existing optional `unrs-resolver` install-script
  notice remains. No Python pins or machine packages were changed. Browser checks
  reused the milestone 12 temporary Chromium/runtime libraries through
  `PLAYWRIGHT_BROWSERS_PATH` and test-only `LD_LIBRARY_PATH`.

All test servers and worker/Beat processes were stopped by their harnesses.
No development observation data was created. This record predates milestone 14.
Suggested commit: `feat: add monitoring dashboard analytics and polling`.
