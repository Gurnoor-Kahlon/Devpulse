# PostgreSQL and migrations

Milestone 4 established synchronous SQLAlchemy sessions and Alembic migrations.
Revision `0001` records an empty baseline in `alembic_version`. Milestone 5 adds
revision `a4c16df5c2ab` with users, sessions, auth tokens, and rate-limit buckets.
Monitoring tables remain deferred.

## Local setup

Use a user-provided PostgreSQL 18 server and its `psql` client in WSL2. The
commands below assume it listens on loopback port 5432. This project does not
install PostgreSQL, change service configuration, or require Docker.

Connect as your local database administrator (adjust the admin role as needed):

```bash
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres -W
```

On a fresh setup, create separate development and test roles/databases:

```sql
CREATE ROLE devpulse LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password devpulse
CREATE DATABASE devpulse OWNER devpulse;
CREATE ROLE devpulse_test_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password devpulse_test_owner
CREATE DATABASE devpulse_test OWNER devpulse_test_owner;
\q
```

The password prompts avoid putting passwords into SQL files or shell history.
If these names already exist, inspect their purpose before reusing them; do not
drop an existing database to repeat setup. The database-owning roles can run
local migrations without superuser or cluster-wide database-creation privileges.

Copy `backend/.env.example` to the ignored `backend/.env` and replace the database
password placeholder. Percent-encode URL-special characters in credentials.
The URL must use `postgresql+psycopg://`, with an explicit host, username, and
database. The default URL has no password and only works when local authentication
already permits it; it is not a provisioned account. Never use an administrator
URL for application processes. Keep the database listener private.

## Migration workflow

From `backend/`, with the project virtual environment active:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Run migrations explicitly before starting the API. Startup never calls
`create_all` or applies migrations automatically. Alembic reads the same
validated configuration as the API; no URL or password belongs in `alembic.ini`.
Connection and SQL errors exit unsuccessfully with a sanitized message.

When a later authorized feature adds models, derive them from `app.db.base.Base`
and import their modules in `migrations/env.py` before autogeneration. Then:

```bash
python -m alembic revision --autogenerate -m "Describe the schema change"
python -m ruff check migrations --fix
python -m ruff format migrations
python -m alembic upgrade head
python -m alembic check
```

Review generated migrations, especially data changes and constraint names.
Primary keys, foreign keys, unique constraints, and indexes receive deterministic
names. Explicitly name check constraints; the convention includes that name.
Use UUID identifiers and timezone-aware timestamps when feature models arrive.

To inspect baseline SQL without connecting:

```bash
python -m alembic upgrade head --sql
```

`python -m alembic downgrade base` removes all current feature tables and the baseline version record. Only
rehearse downgrades on a disposable database; future revisions may remove data.
Validate downgrade and re-upgrade before publishing each future migration.

## Engine and session lifecycle

Each API lifespan creates its own lazy connection pool and session factory,
then disposes the pool on shutdown. No connection opens during module import.
The pool allows five retained connections and five overflow connections per
process, with a three-second checkout timeout and pre-ping on checkout.
Connections use a three-second connection timeout, a five-second statement
timeout, a three-second lock timeout, and UTC timezone.

`get_session` yields a fresh synchronous session and always closes it, rolling
back unfinished transactions. Service code owns explicit transaction/commit
boundaries. Successful HTTP handling does not implicitly commit. Run synchronous
database work in synchronous FastAPI handlers/dependencies so it uses the thread
pool. Never keep transactions open across external network requests, or share
sessions/pools across worker processes.

`/health/live` stays available during database outages. `/health/ready` performs
`SELECT 1` and returns a safe `503` if startup is incomplete, a connection cannot
be checked out, or PostgreSQL cannot answer. It checks connectivity, not schema
version; the explicit migration check above is still required. It does not check
Redis or workers. SQL echo is disabled and bound parameters are hidden; HTTP
responses and application logs never expose database URLs or driver exceptions.

## Integration tests

Use only the dedicated test role and database. In the activated backend terminal,
set `TEST_DATABASE_URL` without saving its value in shell history:

```bash
read -rs -p 'Test database URL: ' TEST_DATABASE_URL
printf '\n'
export TEST_DATABASE_URL
python -m pytest --run-integration
unset TEST_DATABASE_URL
```

Enter a URL shaped like
`postgresql+psycopg://devpulse_test_owner:REPLACE_ME@127.0.0.1:5432/devpulse_test`.
This variable is test-only, not an application setting. Do not add it to the
backend `.env` file. Default `python -m pytest` skips integration tests explicitly;
`--run-integration` fails if the URL is missing, invalid, or unavailable.

The database name must end in `_test`. Each schema-based test creates a randomly
named schema and uses a search path containing only that schema. Cleanup drops
only the schema it created, including its test objects, and never drops the
database or existing schemas. Separate test processes therefore do not share
tables. Use a dedicated test database even with this isolation: never point
tests at production.

The session fixture uses an outer transaction and SQLAlchemy's
`join_transaction_mode="create_savepoint"`. Test code can commit or roll back
without escaping the enclosing rollback. Migration tests use their own isolated
schema because they must exercise real DDL commits. The suite covers clean-schema
upgrade, current revision, autogenerate drift checks, downgrade/re-upgrade,
connection settings, readiness, session cleanup, and rollback isolation.

On an interrupted run, an orphaned `test_<random UUID>` schema may remain in the
dedicated test database. Inspect it before manual removal; there is no broad
automatic cleanup of schemas from previous runs.

## Validation environment

Milestone 4 was validated on Windows with Python 3.13 and PostgreSQL 18 using a
temporary cluster in ignored project cache on loopback port 55434, separate
non-superuser development/test roles, and separate databases. The existing
PostgreSQL service was not changed. The temporary cluster was stopped afterward.
Its loopback trust authentication was only for this disposable validation run;
normal setup uses the password prompts above. WSL2 Ubuntu remains the development
target and still needs a Linux validation run once supplied.

References: [SQLAlchemy transaction test isolation](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites),
[Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), and
[constraint naming](https://alembic.sqlalchemy.org/en/latest/naming.html).
