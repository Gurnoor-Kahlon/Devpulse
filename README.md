# DevPulse

Reliability at a glance.

DevPulse is an API monitoring and reliability platform in development.

## Current status

Milestone 3 adds a configurable FastAPI application factory, process health
endpoints, consistent errors, request IDs, and structured logging. The frontend
has a dark-first shell with accessible controls and feedback states; its Overview
page remains an interface preview without simulated monitoring results.
Authentication, monitoring, and persistence are not implemented yet.

## Local development

Use Node.js 24 and Python 3.13 in WSL2 Ubuntu. See the
[development guide](docs/development.md) for installation, startup, validation,
and dependency-update commands.

The frontend and backend currently run independently. PostgreSQL, Redis, Docker,
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
