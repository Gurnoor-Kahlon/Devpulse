# Dockerized local stack (milestone 18)

This is a local development and validation stack. It does not provision cloud
resources or publish a site. Use the Docker CLI from the Ubuntu workspace, not
Docker Desktop's internal WSL distribution. An existing Docker Engine and Compose
are prerequisites; no machine installation, host permission, ownership, or shell
configuration changes are needed.

## Start and stop

From the project root:

```bash
python3 scripts/local_stack.py init
docker compose --env-file .cache/compose.env config --quiet
docker compose --env-file .cache/compose.env up --build -d --wait
```

The initializer creates a random URL-safe local database password in
`.cache/compose.env`, never prints it, and preserves an existing file. Keep that
file with the stack's volumes; regenerating it does not reset PostgreSQL's existing
password. Do not share resolved `docker compose config` output or container
inspection output containing environment values. `config --quiet` validates
without printing them. Host `backend/.env` and `.venv` are not used by containers.

Open <http://localhost:3000> and Mailpit at <http://localhost:8025>. Register and
use the real verification code in Mailpit before creating monitors. The default
public demo remains unpublished. Database, broker, SMTP, API, and worker ports
are not published to the host. Only the frontend and Mailpit UI bind to host
loopback. Existing host PostgreSQL/Redis and unrelated Docker projects are untouched.

Choose another pair of ports if these are in use; preserve these values for later
Compose commands. The browser Origin setting follows the frontend port:

```bash
DEVPULSE_WEB_PORT=13000 DEVPULSE_MAIL_PORT=18025 \
  docker compose --env-file .cache/compose.env up --build -d --wait
```

Use the `localhost` URL so CSRF Origin validation matches. Browser API calls remain
same-origin `/api/v1`. A container build uses the fixed `http://api:8000` rewrite;
a native build retains the fixed `http://127.0.0.1:8000` rewrite. No arbitrary proxy
origin or client-visible backend URL is introduced. The container frontend uses
[Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output)
and includes the static files and actual screenshots.

```bash
docker compose --env-file .cache/compose.env ps --all
docker compose --env-file .cache/compose.env logs --tail=100 api probe-worker maintenance-worker beat
# Remove containers/networks, retaining database and broker volumes:
docker compose --env-file .cache/compose.env down
# Recreate them against the same retained volumes:
docker compose --env-file .cache/compose.env up -d --wait
```

Do not add `--volumes` to normal shutdown: it deletes this project's database and
broker data. Never use global prune commands or remove another project's resources.

## Services and persistence

| Service | Responsibility | Durable storage |
| --- | --- | --- |
| frontend | Standalone Next server, same-origin forwarding | Build artifacts in image |
| api | FastAPI, sessions, CRUD, stored-result reads | PostgreSQL |
| postgres | PostgreSQL 18; application and separate test databases | `postgres-data` |
| redis | Celery broker; AOF with every-second fsync | `redis-data` |
| migrate | One-shot `alembic upgrade head` | PostgreSQL schema |
| probe-worker | Real prefork worker; `probes`, concurrency 2 | PostgreSQL run/lease/check state |
| maintenance-worker | `maintenance,notifications`, concurrency 2 | PostgreSQL scheduler/outbox state |
| beat | One dispatcher scheduler per Compose project | Business due times in PostgreSQL |
| mailpit | Development SMTP capture and local web UI | Ephemeral capture database in `/tmp` |

PostgreSQL 18 mounts `/var/lib/postgresql` (the versioned data directory is inside),
as required by the [official image](https://hub.docker.com/_/postgres). Initialization
creates `devpulse` and the separate `devpulse_test` database. The init script runs
only for a fresh volume. This local role initializes the cluster and can create
test schemas/databases; it is not a proposed production role/privilege model.

The database and Redis are on an internal network. The frontend, probe worker,
and Mailpit also join a bridge network: the probe worker needs outbound monitoring
access, and the two UIs need their loopback port publication to work. Probe SSRF
validation still rejects private/special destinations. Redis persists its broker
state, but PostgreSQL remains authoritative; reconciliation handles ambiguous/lost
publication. Redis AOF is not a replacement for database backups.

Application processes run as UID/GID 10001 with read-only roots, dropped capabilities,
and `no-new-privileges`; temporary runtime files use container tmpfs. The backend
image defines that account inside the image. No host ownership or permission is
changed. Image build contexts use allowlists excluding `.env`, caches, virtual
environments, node_modules, test artifacts, and repository internals. Runtime
images contain neither developer test code nor the controlled fixture scripts.
The separate test target adds test code and the hashed development dependencies.

PostgreSQL query/parameter/error-detail logging is disabled to keep private row
values out of container logs; application logs retain their existing safe format.

Base images are pinned by immutable registry digest. Python runtime dependencies
use `pip --require-hashes`; frontend dependencies use `npm ci` with the existing
lockfile. No project dependency update is part of this milestone. Updating an
image pin is an explicit future maintenance change followed by these checks.

## Readiness, migrations and restart semantics

[Compose startup conditions](https://docs.docker.com/compose/how-tos/startup-order/)
wait for healthy PostgreSQL, then a successful migration exit, before starting
application services. Redis and Mailpit health are also prerequisites. The frontend
waits for API readiness. A failed migration prevents application startup. Migrations
are explicit in their own service, never run independently by every replica.
Current migration head remains `f16b4d8e302a`; this milestone adds no migration.

API health checks call `/health/ready`, which requires PostgreSQL. `/health/live`
remains available during database loss. Worker/Beat checks verify their PID and
bounded database/broker connectivity. These checks do not certify that tasks are
being consumed; the smoke flow below proves real execution end to end. Compose
startup gates do not continuously restart dependents when a dependency becomes
unhealthy. Existing application reconnect/reconciliation behavior handles outages.
`unless-stopped` restarts crashed long-running services, not merely unhealthy ones.

A per-project container name prevents scaling Beat to multiple replicas. Do not
launch another Beat against the same database/broker. Its schedule/PID files live
in `/tmp`, safely recreated after restart; PostgreSQL owns durable due times. Workers
get 60 seconds for warm shutdown, exceeding their existing 45-second hard task limit.
Do not scale the local services before revisiting database pool/resource budgets.

For later code/schema updates, stop application writers first, build, and run the
one-shot migration before bringing them back. Preserve the volume and take a backup:

```bash
docker compose --env-file .cache/compose.env stop beat probe-worker maintenance-worker api frontend
docker compose --env-file .cache/compose.env build
docker compose --env-file .cache/compose.env run --rm migrate
docker compose --env-file .cache/compose.env up -d --wait
```

## Backup and isolated restore

The helper streams a custom-format `pg_dump` through the container's PostgreSQL 18
client. It never installs a host database client, echoes connection credentials,
or overwrites an existing backup file. Dumps contain private account/configuration
and monitoring data; keep them local and protected. No uploads are performed.

```bash
python3 scripts/local_stack.py backup .cache/backups/devpulse-before-change.dump
python3 scripts/local_stack.py restore .cache/backups/devpulse-before-change.dump \
  --database devpulse_restore_review_test
```

Restore creates a **new** `devpulse_restore_<name>_test` database and uses
`pg_restore --single-transaction --exit-on-error --no-owner --no-acl`. It rejects
existing targets and application database names. It never drops or replaces the
source database. A failed restore leaves the isolated target for diagnosis. Review
restored data before any separately planned cutover; the helper performs no cutover.
For another Compose project, place `--project NAME` before the subcommand. Backup
accepts `--database devpulse_test` for disposable test data.

## Controlled fixtures and validation

`compose.test.yaml` is an explicit test-only overlay; it points application services
to `devpulse_test`. Its loopback fixture shares the probe worker's network namespace,
listens only on `127.0.0.1:8081`, and can return controlled 200/503 responses. Only the
probe worker gets an exact host/port/address exception. No Docker subnet allowlist
or production policy relaxation is added; production settings still reject fixture
exceptions. Fixture scripts are mounted read-only only by the test overlay.

The fixture and probe worker share a namespace: stop/start both together when
restarting or recreating the worker. Never use this overlay for personal monitoring
data, published monitoring data, or production. The fixture-control script refuses
non-test environments and databases other than the disposable test/restore targets.
It creates a clearly labeled saved monitor for an account registered and verified
through the real API. Monitoring outcomes, attempts, metrics, and incidents are
produced by real Celery/HTTP/SMTP execution. Only fixture due times are advanced
between phases; the actual ten-second retry deadlines remain intact.

Build the runtime/test images and run the dedicated, uniquely named smoke project:

```bash
python3 scripts/local_stack.py init
docker compose --env-file .cache/compose.env build api frontend
docker compose --env-file .cache/compose.env -f compose.yaml -f compose.test.yaml build backend-tests
.venv/bin/python scripts/verify_local_stack.py
```

The smoke script uses ports 13000/18025 by default (overridable), creates its own
random Compose project/volumes, and never reuses the user's normal stack. It verifies:

- Fresh readiness, migration head/drift, non-root identities and host-port boundaries.
- Same-origin account signup, SMTP verification, private API denial and static assets.
- Beat dispatch, real Redis/prefork HTTP probes, confirmation retries, recovery and emails.
- Pending work while workers are stopped, broker outage recovery, and database readiness.
- Backup/restore with matching per-table row hashes and rejection of existing targets.
- PostgreSQL/Redis persistence across full container removal/recreation and a full restart.

Safe summary evidence and the test backup go to `.cache/devpulse-smoke-*/`. The script
removes only its own disposable containers/volumes on exit. `--keep` retains them
for inspection; its output gives the exact project name for targeted cleanup.
No global resource cleanup runs. A normal host interruption may require cleaning
that reported test project manually.

Run the full backend suite in a separate disposable project (it creates random test
schemas and Redis key prefixes), then remove only that project:

```bash
DEVPULSE_MAIL_PORT=28025 docker compose --env-file .cache/compose.env --project-name devpulse-tests \
  -f compose.yaml -f compose.test.yaml run --rm backend-tests
# Only for this disposable test project:
docker compose --env-file .cache/compose.env --project-name devpulse-tests \
  -f compose.yaml -f compose.test.yaml down --volumes
.venv/bin/python -m pytest scripts/tests -q
.venv/bin/ruff check backend
.venv/bin/ruff check --config backend/pyproject.toml containers scripts
(cd backend && ../.venv/bin/mypy app)
(cd frontend && npm run check && npm run api:check && npm run build)
```

To check a running stack in Chromium without starting native test servers, run from
`frontend/` (use the actual frontend URL):

```bash
TEST_CONTAINER_ORIGIN=http://localhost:3000 npx playwright test containers.spec.ts
```

Use the existing project-local Chromium and Linux shared-library paths when required
by this workspace, as described in the [public demo guide](public-demo.md).

Container backend tests share Mailpit's network namespace so existing loopback SMTP
and real prefork HTTP fixtures work without host services. Test services are opt-in;
the default stack has no fixture destination exceptions. The native Ubuntu workflow
continues to work and is documented separately in [development](development.md).

## Verified milestone 18 result — 2026-09-30

- Both runtime images and the separate backend test image built from the locked
  dependencies and pinned bases. Running versions: Python 3.13.15, Node 24.21.0,
  PostgreSQL 18.6, Redis 7.4.11, Mailpit 1.31.2.
- The default fixture-free stack passed fresh startup, migration/head, readiness,
  anonymous/public routing and private API denial checks.
- The complete smoke flow passed all ten checks: real signup/verification,
  scheduled probes/retries/incidents/emails, stopped-worker and broker recovery,
  database outage readiness/reconnection, all-table backup/restore fingerprints,
  overwrite rejection, full container recreation with retained PostgreSQL/Redis
  data, and final stack restart with idempotent migrations.
- Controlled scheduled observations were two successes and one confirmed failed run,
  with real delayed retries, one resolved incident, and two SMTP-accepted incident
  emails. No monitoring evidence was synthesized.
- The full backend suite passed **317 tests inside containers**, including real
  PostgreSQL, Redis/Celery workers and Mailpit, with no skips. The existing two
  Starlette/AnyIO deprecation warnings remain.
- Backup/restore/initialization safeguards passed **10 additional tests**, including
  preservation of existing files/databases and the child process's archive offset.
- Frontend: **107 tests**, formatting, ESLint, strict TypeScript, API contract drift,
  and both native/container builds passed. The container Chromium flow passed with
  real image loading, desktop/mobile layout, same-origin API and accessible signup
  validation.
- Ruff lint/format passed for 115 backend Python files and five container/operations
  Python files; mypy passed for 67 application files.
- The smoke summary and test dump are retained locally in
  `.cache/devpulse-smoke-4ed1fbec/`; browser captures are in `.cache/ui-review/m18/`.
  Disposable validation containers/volumes were removed after verification. Existing
  Trackline containers and host PostgreSQL/Redis were not changed.

Suggested commit: `feat: add reproducible local Docker stack and restore checks`.

Milestone 18 is complete. CI/performance infrastructure (milestone 19), release
preparation and deployment (milestone 20) are not included.

## Milestone 20 release audit follow-up

The final runtime images omit unused pip/ensurepip and npm/Corepack/Yarn installers;
build and backend test stages retain their development tools. Run dependency
consistency checks in the project or test environment, not with pip inside the
hardened runtime. Authenticated frontend server rendering now uses fixed
`http://api:8000` in container mode; native development keeps loopback. The runtime
sets `DEVPULSE_CONTAINER_BUILD=1` consistently with the build. Both public and
authenticated-reload Chromium container tests pass.

The final ten-check stack validation passed again after these changes. See the
[release audit](release-audit.md) for current evidence, remaining image advisories
and deployment blockers. This Compose file remains a development configuration.
