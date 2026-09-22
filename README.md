# DevPulse

Reliability at a glance.

DevPulse is an API monitoring and reliability platform in development.

## Current status

Milestone 2 adds a dark-first application shell, responsive navigation,
accessible shared controls, and loading, empty, and error states. The Overview
page is an interface preview; it does not display simulated monitoring results.
Authentication, monitoring, and persistence are not implemented yet.

## Local development

Use Node.js 24 and Python 3.13 in WSL2 Ubuntu. See the
[development guide](docs/development.md) for installation, startup, validation,
and dependency-update commands.

The frontend and backend currently run independently. PostgreSQL, Redis, Docker,
and cloud services are not required for this milestone.

## Project layout

- `frontend/`: Next.js App Router, React, TypeScript, and Tailwind CSS.
- `backend/`: Python and the minimal FastAPI entrypoint.
- `docs/`: development instructions.

See the [design system](docs/design-system.md) for tokens, component behavior,
and accessibility checks. Run `npm run check` in `frontend/` for formatting,
linting, type checking, and component tests; run `npm run build` separately.

Development proceeds one explicitly authorized milestone at a time. Repository
operations and commits remain with the repository owner.
