# DevPulse

Reliability at a glance.

DevPulse is an API monitoring and reliability platform in development.

## Current status

Milestone 1 establishes the development foundation: a minimal Next.js page,
an importable FastAPI application, locked dependencies, and code-quality tools.
Authentication, monitoring, persistence, and the product interface are not implemented yet.

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

Development proceeds one explicitly authorized milestone at a time. Repository
operations and commits remain with the repository owner.
