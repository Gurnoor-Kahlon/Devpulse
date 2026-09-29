# DevPulse

Reliability at a glance.

DevPulse is an API monitoring and reliability platform in development.

## Current status

Milestone 17 adds the public landing page and a read-only demo backed by explicitly
published monitoring observations. The demo exposes restricted summaries, honest
empty/stale states, and labeled controlled failures. The landing page includes actual
local browser screenshots and working signup with email verification. Publication is
empty by default; existing account data stays private. See the
[public demo guide](docs/public-demo.md) for publication, screenshot provenance, and
validation. Docker and deployment remain deferred.

## Local development

Use Node.js 24 and Python 3.13 in WSL2 Ubuntu. See the
[development guide](docs/development.md) for installation, startup, validation,
and dependency-update commands.

The frontend forwards `/api/v1` to the local backend. PostgreSQL 18 is required
for API readiness and database integration tests. See the
[database guide](docs/database.md) for local setup and migrations, and the
[authentication guide](docs/authentication.md) for Mailpit and an API walkthrough.
The [account UI guide](docs/account-ui.md) covers browser flows and tests.
The [monitor API guide](docs/monitors.md) covers configuration, quotas, and editing.
The [monitor UI guide](docs/monitor-ui.md) covers browser workflows and validation.
The [probe guide](docs/probes.md) covers manual execution, security boundaries,
controlled tests, and current limitations.
Redis is required for worker execution. See the [job execution guide](docs/jobs.md)
for worker behavior and the [scheduler guide](docs/scheduling.md) for Beat startup,
automatic recovery, freshness, and validation. The [incident guide](docs/incidents.md)
covers retries, retained evidence, APIs, and browser views. The [dashboard guide](docs/dashboard.md)
explains metric definitions, coverage, polling, and validation. The [monitor history guide](docs/monitor-history.md)
covers detail views and safe check evidence. The [assertion guide](docs/assertions.md)
covers definitions, limits, and retained snapshots. The [notification guide](docs/notifications.md)
covers email preferences, delivery/retry semantics, retention, and migration
`f16b4d8e302a`. Docker and
cloud services remain deferred.

## Project layout

- `frontend/`: Next.js App Router, React, TypeScript, and Tailwind CSS.
- `backend/`: FastAPI application, health router, configuration, and tests.
- `docs/`: development instructions.

See the [design system](docs/design-system.md) for tokens, component behavior,
and accessibility checks. Run `npm run check` in `frontend/` for formatting,
linting, type checking, and component tests; run `npm run build` separately.

See the [API foundation](docs/api.md) for health semantics, configuration,
error responses, and logging. Run `python -m pytest` in the activated backend
environment for the backend tests.

Development proceeds one explicitly authorized milestone at a time. Repository
operations and commits remain with the repository owner.
