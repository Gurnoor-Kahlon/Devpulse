# Reproducible local showcase

The portfolio captures use the actual Next.js, FastAPI, PostgreSQL, Redis, Celery prefork workers and Celery Beat stack. No UI statistics, checks, run outcomes, incidents or observation timestamps are seeded. These are controlled demo endpoints, not external services or production traffic.

## Scenario

| Endpoint | Baseline | Failure phase | Recovery phase |
| --- | --- | --- | --- |
| Catalog API | HTTP 200, about 25 ms server delay | Healthy | Healthy |
| Search API | HTTP 200, varying 480–820 ms server delay | Healthy, slower | Healthy, slower |
| Billing API | HTTP 200 | HTTP 503 | Remains down |
| Inventory API | HTTP 200, `/available` equals `true` | HTTP 200, `/available` equals `false` | Assertion still fails |
| Checkout API | HTTP 200 | HTTP 503 | Returns HTTP 200; incident resolves |

The script registers and verifies a synthetic `portfolio@example.com` account through the actual API and local Mailpit. It enables email notifications through the API. A mounted test-only control seeds five monitor configurations and one JSON assertion into a new, isolated `devpulse_test` database. It refuses another environment, database host/name, account, populated workspace or active run when scheduling a new round.

Four healthy rounds are followed by one failure round and two recovery rounds. The control sets only `next_due_at` to the current time; Beat and the maintenance dispatcher create scheduled runs and publish them through Redis. The unmodified probe worker performs real HTTP requests. Normal retry deadlines, fenced leases, incident transitions and notification workers remain active. The saved 86,400-second interval prevents extra unsolicited rounds during capture; the showcase explicitly accelerates due scheduling, not probe timing or historical timestamps.

Expected result: **35 completed scheduled runs, 28 successful and 7 failed; 49 real HTTP attempts including retries; three confirmed incidents, one recovered and two still open; four incident/recovery emails accepted by local SMTP.** Retries count once toward observed uptime, giving an 80% run-weighted ratio for this deliberately failure-heavy exercise. SMTP acceptance does not prove inbox delivery.

The run lasts minutes, so latency history occupies one hourly bucket rather than a fabricated multi-day trend. Actual per-attempt durations and timestamps remain available in check history. Loopback target URLs are masked at screenshot capture; no metric or evidence is replaced. The synthetic email is not a personal address. Screenshots contain neither credentials nor browser chrome.

## Reproduce

Prerequisites: Docker with Compose; the four runtime images built using the [local setup](../README.md#run-locally); Python 3.13 with the project's `.venv` dependencies; Node 24/npm 11 with `npm ci` completed in `frontend/`; and a Playwright Chromium installation. No cloud account or hosted backend is needed.

From the project root:

```bash
# Install only the browser into a project-local cache if it is not already present.
(cd frontend && PLAYWRIGHT_BROWSERS_PATH=../.cache/playwright npx playwright install chromium)
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/playwright"
.venv/bin/python scripts/showcase.py
```

Chromium needs its normal Linux shared libraries. On a minimal WSL environment, use an existing compatible browser/dependency setup; the showcase does not install machine packages. For this capture pass, Chromium and extracted browser libraries were already available in project-local caches.

The command uses ports **13000/18025**, a random `devpulse-showcase-…` project and fresh named volumes. It explicitly uses `--no-build --pull never`; missing images are an error, not an implicit rebuild. It checks migration head/schema drift, registers the account, drives the real scenario, verifies outcomes, and captures the UI. Output defaults to `.cache/showcase-output/`, so reproduction does not overwrite the reviewed portfolio artifacts. On normal completion or failure it removes only its own disposable stack and volumes.

Optional arguments:

```bash
.venv/bin/python scripts/showcase.py --web-port 13001 --mail-port 18026
.venv/bin/python scripts/showcase.py --keep
```

`--keep` retains the stack for inspection at the printed local port. Its random account password is stored only in the printed `.cache/devpulse-showcase-…/access.json` path. Keep that file private. When finished, use the exact project name printed by the script:

```bash
read -r -p 'Showcase project name printed by the script: ' SHOWCASE_PROJECT
docker compose --env-file .cache/compose.env --project-name "$SHOWCASE_PROJECT" \
  -f compose.yaml -f compose.test.yaml -f compose.showcase.yaml down --volumes
```

Do not apply the test/showcase overlays to your normal monitoring project. They are disposable local tools, mounted read-only and excluded from runtime image build contexts. The fixture binds only the probe worker's loopback namespace; the existing exact-address test exception is unchanged and production mode continues to reject it.

## Captures and evidence

[Gallery](release-screenshots.md) · [Sanitized real-run evidence](assets/showcase-evidence.json).

The evidence records actual timestamps, scheduled runs, attempts, assertion snapshots, incidents, notification states and exact image IDs. No account credentials, tokens, environment values or response bodies are exported. The animation is a compact sequence of actual browser frames: dashboard → latency history → the earlier open checkout incident → its later recovery. This is a navigation tour assembled from two phases, not a continuous recording or a claim that the dashboard snapshot predates the incident.

To refresh public artifacts deliberately, pass `--output docs/assets`. To regenerate the optional GIF, install Pillow into a project-local tools directory and run `scripts/showcase_gif.py` as described in that script. Browser captures require no Pillow dependency. Runtime dependencies and image definitions are unchanged by these tools, so the existing dated image validation remains the applicable evidence.
