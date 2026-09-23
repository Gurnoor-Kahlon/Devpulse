# DevPulse

Reliability at a glance.

DevPulse is an API monitoring and reliability platform in development.

## Current status

Milestone 4 adds PostgreSQL connection/session handling, database readiness,
an Alembic migration baseline, and isolated database integration tests. The frontend
has a dark-first shell with accessible controls and feedback states; its Overview
page remains an interface preview without simulated monitoring results.
Authentication and monitoring are not implemented yet; no feature tables exist.

## Local development

Use Node.js 24 and Python 3.13 in WSL2 Ubuntu. See the
[development guide](docs/development.md) for installation, startup, validation,
and dependency-update commands.

The frontend and backend currently run independently. PostgreSQL 18 is required
for API readiness and database integration tests. See the
[database guide](docs/database.md) for local setup and migrations. Redis, Docker,
and cloud services are not required for this milestone.

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
