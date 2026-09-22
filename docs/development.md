# Local development

## Milestone 1 prerequisites

The supported development environment is Ubuntu under WSL2, with Node.js 24,
npm 11, and Python 3.13 including `venv` and `pip`. Supply these prerequisites
before following the commands below. Docker Desktop's internal WSL distribution
is not an Ubuntu development environment.

Use Linux executables inside WSL. Check `node --version`, `npm --version`, and
`python3.13 --version`; `command -v node` and `command -v npm` should identify
Linux tools, not executables under `/mnt/c/Program Files/`.

No global package installation, shell-profile edit, repository ownership change,
or system-permission adjustment is part of project setup. PostgreSQL, Redis,
Mailpit, Docker, and AWS are not needed for milestone 1. They are introduced only
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

Open <http://localhost:3000>. The page currently contains only the product name
and tagline. The development server listens on loopback.

Optionally copy the root `.env.example` to `frontend/.env.local` to disable
Next.js telemetry. Next.js loads that frontend-local file; neither application
automatically loads a root `.env`. The backend needs no environment file yet.
Never put credentials in variables prefixed with `NEXT_PUBLIC_`.

Validation, from `frontend/`:

```bash
npm run check
npm run build
```

`check` runs Prettier, ESLint with zero tolerated warnings, and strict TypeScript
checking. `typecheck` generates Next.js route types first, so it also works before
the first development server or build. Linting runs independently of the build.

To check the production entrypoint after a successful build:

```bash
npm run start
```

Stop the development server first because both commands use port 3000. Use
`npm run format` when intentionally formatting frontend files.

## Backend

In a separate WSL terminal, from the project root:

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-dev.lock --cache-dir ../.cache/pip
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://localhost:8000/docs> to inspect the minimal application. No product
or health routes exist yet, so `/` returns 404. The frontend does not call the
backend in this milestone.

Validation, from `backend/` with its virtual environment active:

```bash
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -c "from app.main import app; print(app.title)"
```

The final command should print `DevPulse`. Ruff handles Python linting and
formatting; mypy checks application code in strict mode. Run `python -m ruff
format .` when intentionally formatting Python files.

`requirements.lock` contains only runtime dependencies. `requirements-dev.lock`
contains the same runtime versions plus development tools. Both include hashes
and platform markers from a universal Python 3.13 resolution, supporting WSL
Linux and Windows without maintaining separate version lists.

There are no behavioral test suites in milestone 1: there is no product behavior
yet. The checks above validate the entrypoints and toolchain. Tests are added
with the functionality they exercise rather than as placeholder test cases.

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
