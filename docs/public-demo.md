# Public demo and landing page
Current validation and release gates: [portfolio release report](portfolio-release.md). Dated results below are historical.

The server-rendered `/` landing page links to `/demo`, sign-in, and the existing
registration flow. Signup requires real email verification before monitor creation.
The public demo reads stored PostgreSQL observations; loading, refreshing, and
changing windows never enqueue or execute probes. No deployment is included.

## Explicit publication

Publication is an operator setting, empty by default. There is no public mutation,
arbitrary URL input, monitor lookup, or account-wide publication endpoint. Existing
development accounts and monitors are not automatically published.

For a monitor **you own and intend to publish**, obtain its ID and current
`configuration_version` from the authenticated monitor API and its owner's ID from
`GET /api/v1/auth/me`. Set `DEVPULSE_DEMO_PUBLICATIONS` in `backend/.env` to a JSON
array of entries with this shape (replace the illustrative UUIDs):

```json
[
  {
    "owner_id": "00000000-0000-4000-8000-000000000001",
    "monitor_id": "00000000-0000-4000-8000-000000000002",
    "configuration_version": 1,
    "slug": "controlled-http",
    "label": "Controlled HTTP endpoint",
    "controlled_failure": true
  }
]
```

Use a single-line JSON array for the environment variable. Restart the API to apply
setting changes. Slugs and monitor IDs must be unique; at most ten entries are
accepted. Slugs contain lowercase letters, digits, and hyphens, beginning with a
letter. Labels are deliberately public text, independent of the private monitor
name: do not put URLs, credentials, email addresses, or private identifiers in them.
The explicit `controlled_failure` flag must be true for intentional failure exercises.

Each request checks the exact owner, monitor, configuration version, verified owner,
and non-archived state. Missing or ineligible entries are silently omitted. Editing
configuration (including pause/resume and assertion edits) invalidates publication
until the operator reviews and pins the new version. Archival removes publication;
removing the entry and restarting the API revokes it as well. Revocation removes the
entire public history projection on subsequent requests, not only current health.
Already downloaded information cannot be recalled. Do not publish private history.
Publication includes retained observations and incident times from earlier configurations.

The repository leaves `DEVPULSE_DEMO_PUBLICATIONS=[]` as the example/default. It does
not change the user's development `.env` or select their monitors. With no eligible
publication, the demo truthfully says **No monitors are published yet**. This is
separate from a published monitor with **No observations in this window**.

## Public API and data boundary

`GET /api/v1/demo?window=24h|7d|30d` is anonymous and read-only. It returns:

- Response generation time and the approved public slug/label/failure-exercise flag.
- Saved health, last scheduled check time, and freshness based on two intervals.
- Run metrics and bounded trend buckets for the selected window.
- At most five recent incident opening, confirmation, and recovery timestamps.

The projection excludes internal IDs, private monitor and incident names, destination
URLs, owner/account/session information, configuration, checks, assertion definitions
or expected values, evidence snapshots, response bodies/headers, and email deliveries.
It does not reuse the authenticated dashboard or incident response models. Private
API routes still require authentication and ownership. All demo responses use
`Cache-Control: no-store`; reads issue no cookies and create no sessions. Client
parameters cannot expand the publication list. Invalid windows are rejected.

Metrics reuse the established [analytics definitions](dashboard.md): successful
completed scheduled runs divided by successful plus failed completed scheduled runs,
with retries counted once. Manual runs do not enter the query; incomplete, cancelled,
blocked, and infrastructure-failed runs are excluded from uptime. Latency uses final
attempts that received an HTTP response. No observations yield null metrics, never
100%. The view exposes counts, observation range, partial history, gaps, freshness,
and UTC timestamps. It makes no time-weighted availability or SLA claim.

Polling uses the shared visibility-aware 15-second reader with 30/60/120-second error
backoff. The public view hides previously loaded data after a failed refresh and
provides retry. Changing the window does not carry data from another window.

## Actual screenshots and controlled data

The landing assets are real, unedited browser captures of `/demo`:

- `frontend/public/screenshots/demo-desktop.png` (1280px viewport).
- `frontend/public/screenshots/demo-mobile.png` (360px viewport).

Captured on 2026-09-28 at approximately 21:20 UTC with local Chromium.

- `demo-desktop.png`: 1280 × 1758, SHA-256 `89f90a70436f720de47ecd5fa0c939b2bb34610424404ccdd657211dc8802dcd`.
- `demo-mobile.png`: 360 × 2944, SHA-256 `4a9ff583422afedf9012a437c33dd821bc8c68d2b22c391aef0ad30bd0954dbf`.

The on-page captions identify them as static local controlled-test captures, not a
live availability report. The fixture uses an isolated random PostgreSQL schema in
`devpulse_test`, a disposable verified fixture account, and an exact non-production
loopback HTTP destination. It runs the shared pending-run, fenced-lease, HTTP probe,
attempt persistence, and incident transition pipeline against real HTTP responses:
503 three times, 200 once, then 503 three times. Only retry clocks are accelerated;
no outcomes, latency, incident evidence, or timestamps are fabricated. These seven
attempts produce three completed scheduled runs (one successful and two failed),
one resolved incident, and one open incident. The limited observed uptime is 33.33%,
explicitly labeled as a controlled failure exercise. No long-running history is implied.

The fixture exits after probing; its endpoint is not a continuing monitoring service.
The browser server publishes only that fixture through the same restricted API used
by the product. Its schema is removed when the browser runner exits. Production
continues to reject loopback fixture exceptions. This milestone neither seeds nor
publishes development-account data, and requires no new database migration.

## Accessibility and validation

Public pages reuse the established contrast-tested tokens and visible focus styles.
They have one main landmark, a keyboard skip link, labeled controls, text accompanying
health colors, reduced-motion support, wrapping mobile navigation, and an accessible
observation table alongside the charts. Table overflow stays within a focusable
region at 360px. Screenshot alternatives and captions describe the actual content.
Signup uses the existing accessible validation and error handling.

Run from the existing project environment:

```bash
# backend/; .env.test points only to the dedicated _test database and test Redis.
set -a
. ./.env.test
set +a
../.venv/bin/python -m pytest --run-integration tests/test_demo_settings.py tests/integration/test_demo.py -q
../.venv/bin/ruff check app tests
../.venv/bin/mypy app
```

From `frontend/`, with Linux Node 24 on PATH:

```bash
npm run api:check
npm run check
npm run build
# Load ../backend/.env.test first; local Mailpit must listen on 1025 and 8025.
TEST_DEMO_FIXTURES=1 npm run test:e2e -- demo.spec.ts
```

Install Chromium into a project-local cache from `frontend/`:

```bash
export PLAYWRIGHT_BROWSERS_PATH="$PWD/../.cache/playwright"
npx --no-install playwright install chromium
```

Chromium also requires its platform runtime libraries. Use a machine or runner
that supplies them; see [browser setup](account-ui.md#browser-tests).

The browser flow checks real public metrics and private API denial, desktop/mobile
layout, keyboard skip/table navigation, reduced motion, read-only refresh, and the
landing CTA through registration, real Mailpit delivery, verification, sign-in, and
access to monitor creation. Screenshots are written to the test's `test-results`
output directory. Refresh checked-in screenshot assets only after reviewing the
captures for fixture provenance and private data; copying captures does not edit them.

## Recorded validation (2026-09-28)

- Full backend regression: 316 passed and one existing WSL-sensitive retry timing
  assertion failed. UTC logs showed the expected delay while the fixture's monotonic
  clock diverged. The test now compares persisted UTC attempt start/finish times,
  keeping the original minimum-delay threshold and asserting three actual HTTP hits.
- Targeted rerun: 11 passed, including both real Celery retry/restart/recovery cases
  and all nine new demo settings/integration tests. The complete suite contains 317
  distinct tests; no backend tests were skipped in the full run. The two existing
  Starlette/AnyIO deprecation warnings remain.
- Frontend: all 107 tests passed; formatting, ESLint, strict TypeScript, generated API
  contract drift check, and the production build passed.
- Final real-browser demo/signup flow passed with screenshot loading, 1280px/360px
  layouts, keyboard access, private API denial, and Mailpit verification.
- Ruff check/format passed (114 Python files); mypy passed (67 application files);
  project-local Python dependency consistency passed.
- Desktop and mobile demo captures and the completed landing page were reviewed.
  No new dependencies, migrations, development-account publications, machine-level
  installations, or Git operations were needed.

Current container and CI workflows are documented in [containers](containers.md)
and [performance](performance.md). Deployment remains unapproved.
