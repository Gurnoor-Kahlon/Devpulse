# Local development

## Current prerequisites

The supported development environment is Ubuntu under WSL2, with Node.js 24,
npm 11, and Python 3.13 including `venv` and `pip`. Supply these prerequisites
before following the commands below. Docker Desktop's internal WSL distribution
is not an Ubuntu development environment.

Use Linux executables inside WSL. Check `node --version`, `npm --version`, and
`python3.13 --version`; `command -v node` and `command -v npm` should identify
Linux tools, not executables under `/mnt/c/Program Files/`.

No global package installation, shell-profile edit, repository ownership change,
or system-permission adjustment is part of project setup. PostgreSQL, Redis,
Mailpit, Docker, and AWS are not needed for milestones 1–3. They are introduced only
when their features are implemented.

The examples use the existing project location:

```bash
cd /mnt/c/Users/mail2/vs-code-workspace/devpulse
```

Do not share `node_modules`, Python virtual environments, or `.next` output
between Windows and Linux. If switching platforms, first stop the project
processes and remove only those generated directories before reinstalling with
the destination platform's tools. Dependency lockfiles are shared source files
and should be retained. Never change file ownership to address setup problems.

## Frontend

From the project root:

```bash
cd frontend
npm ci --cache ../.cache/npm
npm run dev
```

Open <http://localhost:3000>. The root redirects to `/dashboard`, which shows
the application shell and an honest empty state. Only Overview is available in
navigation. The development server listens on loopback.

Optionally copy the root `.env.example` to `frontend/.env.local` to disable
Next.js telemetry. Next.js loads that frontend-local file; neither application
automatically loads a root `.env`. Optional backend configuration belongs in
`backend/.env`, based on `backend/.env.example`.
Never put credentials in variables prefixed with `NEXT_PUBLIC_`.

Validation, from `frontend/`:

```bash
npm run check
npm run build
```

`check` runs Prettier, ESLint with zero tolerated warnings, strict TypeScript
checking, and Vitest component tests. `typecheck` generates Next.js route types first, so it also works before
the first development server or build. Linting runs independently of the build.

To check the production entrypoint after a successful build:

```bash
npm run start
```

Stop the development server first because both commands use port 3000. Use
`npm run format` when intentionally formatting frontend files.

Run `npm run test` for the component and contrast tests, or `npm run test:watch`
while editing. Tests exercise keyboard interaction, dialog focus, mobile menu
dismissal, labeled fields, feedback announcements, and palette contrast. They
run locally in jsdom without an API server or external websites. Browser-based
responsive and focus checks remain necessary because jsdom does not lay out CSS.

The initial Windows checks do not replace a WSL validation run. Ubuntu/WSL was
not available during the foundation work. Continue to keep platform-specific
dependency directories separate.

## Backend

In a separate WSL terminal, from the project root:

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock --cache-dir ../.cache/pip
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000/docs> for the API documentation. Both
<http://localhost:8000/health/live> and <http://localhost:8000/health/ready>
return `{"status":"ok"}` after startup. Readiness currently checks application
lifecycle only; no database or queue is connected. The frontend still runs
independently of the API.

The application factory is `app.factory.create_app`; `app.main:app` keeps the
existing Uvicorn entrypoint. Settings load from `backend/.env` regardless of the
working directory, and process environment variables take precedence. Defaults
work without creating an environment file. Invalid configuration stops startup
without printing supplied values. See the [API foundation](api.md) for details.

Validation, from `backend/` with its virtual environment active:

```bash
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
python -c "from app.main import app; print(app.title)"
```

The final command should print `DevPulse`. Ruff handles Python linting and
formatting; mypy checks application code in strict mode. Run `python -m ruff
format .` when intentionally formatting Python files.

`requirements.lock` contains only runtime dependencies. `requirements-dev.lock`
contains the same runtime versions plus development tools. Both include hashes
and platform markers from a universal Python 3.13 resolution, supporting WSL
Linux and Windows without maintaining separate version lists.

The backend tests cover configuration, lifecycle health, OpenAPI, safe errors,
request-ID concurrency, and log privacy. Test-only routes are attached to fresh
factory instances; they are not application endpoints. These tests do not need
PostgreSQL, Redis, or network access. HTTPX is currently a development dependency
for in-process API tests; outbound monitoring is not implemented.

The locked Starlette test client currently emits upstream deprecation warnings
for its HTTPX adapter and an AnyIO portal alias. Tests still pass. Keep these
visible when evaluating a later coordinated dependency update; do not suppress
them or replace the monitoring HTTP stack merely to silence warnings.

## Dependency changes

Only change dependencies when the active milestone requires them. Frontend
direct dependencies are saved as exact versions, and `package-lock.json` pins
the resolved dependency tree. Use `npm ci` for an existing checkout.

ESLint 9 is pinned because the current Next.js React and accessibility plugins
declare support through ESLint 9. npm reports its upstream deprecation. Upgrade
the lint stack together once those plugins support the maintained ESLint major;
do not bypass peer-dependency checks with forced installation.

Backend dependency intent lives in `pyproject.toml`. The development environment
includes a pinned `uv` CLI solely for compiling the requirements files. After
changing dependencies, run these commands from `backend/`:

```bash
python -m uv pip compile pyproject.toml --python-version 3.13 --universal --generate-hashes --no-header --output-file requirements.lock --cache-dir ../.cache/uv
python -m uv pip compile pyproject.toml --extra dev --constraint requirements.lock --python-version 3.13 --universal --generate-hashes --no-header --output-file requirements-dev.lock --cache-dir ../.cache/uv
python -m pip install --require-hashes -r requirements-dev.lock --cache-dir ../.cache/pip
```

These commands preserve existing compatible pins by default. An intentional
upgrade should use `--upgrade-package PACKAGE` for the affected package when
compiling, followed by the relevant checks. Do not edit generated lockfiles by
hand. After removing dependencies, validate installation in a fresh virtual
environment so leftover packages cannot hide missing requirements.

## Troubleshooting

- **WSL reports access denied or only lists Docker Desktop:** supply a working
  Ubuntu WSL2 environment before attempting the Linux setup. Do not develop
  inside Docker Desktop's internal distribution.
- **Python 3.13 or `venv` is missing:** the machine prerequisite is incomplete;
  do not install dependencies into system Python as a workaround.
- **Port already in use:** stop the existing project process, or pass another
  port explicitly. Do not terminate unrelated services.
- **A native package fails after switching platforms:** recreate that platform's
  generated dependency directory using the checked-in lockfile.
- **Package downloads fail:** inspect connectivity to npm or PyPI. Keep TLS
  verification enabled and avoid running project setup as an administrator.
