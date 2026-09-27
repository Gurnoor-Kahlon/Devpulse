# Response assertions

Milestone 15 adds owned assertion definitions, an editor at
`/monitors/[id]/assertions`, and bounded evaluation in the existing probe worker.
Check history and opening, confirmation, and recovery incident evidence display
captured definitions and results. Milestone 16 notification delivery and retention
jobs remain deferred.

## Definitions and API

A GET monitor supports at most ten ordered assertions. Every assertion and the
expected HTTP status must pass for the attempt to succeed. Supported kinds:

| Kind | Configuration | Pass condition |
| --- | --- | --- |
| `text_contains` | Nonempty `expected` string; `pointer` empty | Case-sensitive substring in the strictly decoded UTF-8 body |
| `json_equals` | `pointer` and scalar `expected` | The selected JSON value has the same JSON type and value |

Expected JSON values may be strings, finite numbers, booleans, or `null`.
Objects and arrays are not expected values. Numbers compare numerically (`1`
equals `1.0`); boolean `true`, number `1`, and string `"1"` are distinct. Missing
paths fail even when the expected value is `null`. Empty strings are valid JSON
expected values, but not text-containment needles. String comparisons do not
normalize Unicode or case.

Pointers use the string representation from [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901):
an empty pointer selects the root, `/a/0` selects an array element, `~1` encodes
`/`, and `~0` encodes `~`. URI fragments, invalid tilde escapes, array indexes
with leading zeroes, and the append token `-` are not accepted/resolved.
Definitions reject invalid Unicode and NUL. Pointers are limited to 512 characters
and 32 segments; expected strings to 1,024 characters. Expected numbers are
bounded to ±9,007,199,254,740,991 for browser interoperability.

- `GET /api/v1/monitors/{id}/assertions` returns `monitor_id`, the current
  `configuration_version`, `method`, and ordered `items` with UUID IDs.
- `PUT /api/v1/monitors/{id}/assertions` replaces the entire ordered list atomically.
  Send the current `configuration_version` and `items` without IDs. An empty list
  removes all definitions. Unchanged definitions keep their IDs and version;
  a changed list receives new IDs and increments the monitor configuration version.
- Both routes require the owner's authenticated session. Inaccessible or archived
  monitors return 404. Writes require the existing CSRF token and Origin checks.
  Stale versions return 409; invalid definitions return sanitized 422 errors.
- Body assertions require GET. Remove them before changing a monitor to HEAD.
  HEAD monitors can read or save an empty definition list.

Example replacement body:

```json
{
  "configuration_version": 3,
  "items": [
    { "kind": "json_equals", "pointer": "/health/ok", "expected": true },
    { "kind": "text_contains", "pointer": "", "expected": "healthy" }
  ]
}
```

The editor accepts raw text for containment, or a JSON scalar literal for equality
(for example `true`, `null`, `42`, or `"healthy"`). Saves do not initiate probes.
An edit makes an enabled monitor due for the existing dispatcher and clears its
scheduled-observation freshness. Paused monitors remain paused. Conflicts preserve
unsaved edits; the explicit reload action replaces them with saved definitions.
The editor does not poll and overwrite an active draft.

## Execution and limits

Claims capture immutable definition snapshots under the same monitor lock used
by configuration writes. Database sessions close before DNS/HTTP work. Changes
invalidate queued work; an already executing old version may retain its historical
attempt but cannot update current health or incidents. Existing lease tokens still
fence duplicate or expired workers.

Bodies remain bounded independently to 1 MiB on the wire and after decoding.
Identity, gzip, and zlib-wrapped deflate retain their existing streaming limits.
Only probes with assertions collect body bytes for evaluation. Text requires strict
UTF-8. JSON is parsed only when a JSON assertion is configured; invalid JSON alone
does not fail status-only or matching text-only probes.

JSON evaluation is deliberately restricted: preflight rejects nesting above 32
levels and more than 10,000 opening-bracket/comma/colon structural characters
outside strings. Duplicate object keys are invalid. Number tokens are limited to
64 characters, must be finite, and have a decimal adjusted exponent between -100
and 100. Parsing occurs once per response. These bounds limit synchronous work;
the total probe deadline includes evaluation, and an elapsed deadline cannot
produce a successful result. Complex but otherwise valid JSON can fail these
limits. There are no regular expressions, JSONPath queries, scripts, coercions,
header assertions, or request-body features.

Each snapshot result has `definition`, `status` (`passed`, `failed`, or
`not_evaluated`) and a fixed `reason`. Reasons include `matched`, `text_not_found`,
`pointer_missing`, `value_mismatch`, `invalid_json`, `invalid_utf8`,
`evaluation_limit`, and `response_unavailable`. Complete responses evaluate all
assertions, including when HTTP status differs. An unexpected HTTP status takes
precedence over assertion failure as the attempt error. If status matches and any
assertion fails, the attempt records `assertion_failed`. Transport/body failures
retain definitions with `not_evaluated` results when no complete body was evaluated.

Assertion failures use the existing scheduled lifecycle: ten-second retries,
three failed attempts to confirm an incident, and one successful scheduled attempt
to recover. Workers do not sleep between retries. Manual diagnostics retain results
but do not change incident state or aggregate uptime. Retry attempts still count
as one completed scheduled run in analytics; HTTP 200 can now belong to a failed run.

## Evidence, privacy, and migration

Configured expected values are private configuration and are intentionally copied
into per-check and retained incident evidence. Avoid placing secrets in them.
Bodies, headers, and actual extracted response values are never saved or logged.
API validation errors, worker logs, and operator output do not echo definitions or
responses. Historical evidence uses its captured definitions, even after a later
edit, removal, archive, or raw-run deletion. Incident snapshots survive raw history
pruning; automatic pruning is still milestone 16.

Migration `e15a9c7d204f` follows `d93f8b2e015c`. It adds the ordered `assertions`
table and `checks.assertion_results` JSONB column. Existing checks receive `[]`;
legacy incident JSON receives an empty list on read. Historical assertions are
not invented. Downgrading removes assertion configuration and per-check results;
retained incident JSON is not rewritten. Stop old API/executor/worker processes,
upgrade, and restart all processes with the new code so old workers cannot ignore
new definitions. From the activated backend environment:

```bash
python -m alembic upgrade head
python -m alembic current --check-heads
python -m alembic check
```

## Validation

Use the existing Python 3.13 `.venv`, Linux Node 24, PostgreSQL 18, and Redis.
No dependency or lockfile changes are required. Backend tests use disposable
schemas in a dedicated `_test` database. From `backend/`:

```bash
../.venv/bin/python -m ruff check .
../.venv/bin/python -m ruff format --check .
../.venv/bin/python -m mypy app
../.venv/bin/python -m pip check
../.venv/bin/python - <<'PY'
import os
import pytest
from dotenv import dotenv_values
os.environ.update({k: v for k, v in dotenv_values('.env.test').items() if v is not None})
raise SystemExit(pytest.main(['--run-integration', '--run-worker']))
PY
```

From `frontend/`, with the private `TEST_DATABASE_URL` loaded and a Linux Chromium
installation available through `PLAYWRIGHT_BROWSERS_PATH`:

```bash
npm run api:check
npm run check
npm run build
TEST_ASSERTION_FIXTURES=1 npm run test:e2e -- assertions.spec.ts
```

The opt-in browser fixture uses real loopback responses and real persistence in a
new temporary schema. It produces HTTP 200 assertion failures, recovery, and a
second incident. Only fixture retry timestamps are accelerated. Real Celery tests
separately exercise persisted ten-second retries and worker restart through Redis.
Nothing seeds or fabricates development monitoring history.

## Verified milestone 15 result — 2026-09-27

- Backend: **282 passed, 1 skipped**, including real PostgreSQL schemas, migrations,
  Redis/Celery prefork workers, ten-second assertion retries, restart/recovery,
  ownership/CSRF, concurrent writes, stale configurations, parser bounds, and
  retained evidence. The skipped test is optional Mailpit authentication-email
  delivery; it was not needed for this milestone. Existing Starlette/AnyIO
  deprecation warnings remain.
- Frontend: **92 tests passed**; formatting, ESLint, strict TypeScript, generated
  API contract drift, and production build passed.
- Chromium: the assertion editor/history/incident workflow passed, including
  1280px and 360px layouts without horizontal overflow or browser page errors.
  Real fixture screenshots are saved locally in `.cache/ui-review/m15/`.
- Ruff lint and formatting passed for **94 Python files**; mypy passed for
  **55 application files**; Python dependency consistency passed.
- Development PostgreSQL is at `e15a9c7d204f`; head and schema-drift checks passed.
  Test schemas verified downgrade/upgrade and preservation of old checks with
  empty assertion snapshots. No development monitoring history was seeded.
- No Git commands, machine installations, permission/ownership changes, deployment,
  or milestone 16 implementation were performed.

The previous temporary runtime/browser caches were absent. Validation restored
Node 24.21.0 from its checksum-verified official Linux archive, Linux Chromium,
and unpacked browser support libraries in this project's `.cache/` only.
To reuse these local validation assets from the repository root:

```bash
export PATH="$PWD/.cache/node24/node-v24.21.0-linux-x64/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright-linux"
export LD_LIBRARY_PATH="$PWD/.cache/browser-libs/extracted/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
```

Suggested commit message: `feat: add bounded response assertions and retained evidence`.
Milestone 15 is complete. Stop before milestone 16.
