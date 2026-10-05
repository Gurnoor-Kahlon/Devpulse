# Portfolio release report

**2026-10-05 — NOT READY FOR PUBLIC RELEASE.** Runtime image remediation and local Docker validation are complete. The remaining release blocker is the unimplemented/unapproved production deployment and public URLs. No deployment, image push, cloud resource creation or public DNS change was performed.

## Release blockers

1. **Resolved — critical/high production runtime image advisories.** Fresh baseline scans found 241 critical/high package-advisory matches (54 distinct IDs). Pinned Alpine bases, PostgreSQL helper replacement and vendor library patches remove them. Direct vendor review also found and fixed three critical/high CPython advisory IDs plus embedded OpenSSL occurrences missed by the scanner. All four final runtime images report **zero findings at every severity**, without suppression. [Every advisory, cause and remediation](container-release.md#image-findings-and-remediation).
2. **Resolved — Docker validation.** Docker 29.2.0 and Compose 5.0.2 are accessible from Ubuntu WSL. All runtime/test images built from scratch; 317 backend tests, two container browser tests, ten full-stack checks and default Compose startup/restart passed. The 100-monitor/10,000-probe benchmark below uses the final scanned images.
3. **Open — production deployment and public URLs.** Current Compose is local development configuration. Production ingress/TLS, trusted client-IP handling, network/metadata isolation, cloud alarms, encrypted restore drills, domain/email identity and authorization remain gates in the [proposal](deployment-proposal.md). No public URL exists. Deployment was explicitly outside this pass.

[October 5 container release evidence](container-release.md) supersedes the earlier unavailable-Docker and runtime-image findings. Redis's current Alpine 3.21 base remains supported through **2026-11-01**; rebase and revalidate before that date. Existing Debian PostgreSQL volumes need logical backup/restore into a new Alpine cluster, not direct reuse. Only disposable validation volumes were created here.

The [October 4 source manifest](evidence/portfolio-source-manifest-2026-10-04.json) and native validation remain historical records. The [October 5 source manifest](evidence/container-source-manifest-2026-10-05.json) identifies current reviewed public files without repository metadata. Temporary validation stacks were removed; native PostgreSQL/Redis and private configuration were preserved.

## Changes made

- Rebased Python/Node/PostgreSQL runtime images, patched Redis libraries, and replaced PostgreSQL's vulnerable bundled Go helper. Added minimal PostgreSQL/Redis Dockerfiles and explicit build-context allowlists; Python is patched to 3.13.16; Node, PostgreSQL, Redis and application dependency versions are retained. Two container-only locks pin the psycopg C extension and its build tools.
- Updated CI/build commands and benchmark source fingerprints for all four images. Corrected the outage smoke assertion's timeout for Docker DNS and reran the entire fresh-volume suite. [Diagnosis and complete results](container-release.md#container-validation).

Earlier October 4 portfolio work, retained as history:

- Rewrote the root [README](../README.md) around the product, actual architecture, screenshots, local setup, reliability/security decisions, measured tests and clearly dated benchmark evidence. No live links, CI badges, customers, availability claims or deployment claims were invented.
- Updated current descriptions of account flows, dashboard, monitoring, worker execution, assertions, notifications and the demo. Removed personal machine paths/usernames and stale statements that implemented features were still pending. Retained useful dated engineering records, with a link to this current report.
- Corrected fresh-checkout Python environment instructions and runbook examples, including a valid lowercase disposable Compose project name and the explicit Ruff configuration for operational scripts.
- Expanded artifact exclusions for local cloud credentials, editor settings, environment variants, database files/backups and key bundles. Removed a workspace-specific editor setting. Existing private environment files were preserved.
- Made incident and monitor-list timestamps explicitly UTC, matching dashboard/history and removing ambiguous local-time displays. The existing incident component regression checks timezone normalization.
- Reviewed real desktop/mobile product captures. Browser capture steps now scroll to the top before full-page screenshots, preventing off-viewport fixed controls appearing in the middle of stitched images. Added blank-login and resolved-incident captures to existing real browser flows. No redesign, invented observations or major product functionality was added.

## Final validation

| Check | Current result |
| --- | --- |
| Backend Pytest | **317 passed, 0 failed, 0 skipped**, 374.13 seconds in the final Alpine container, Python 3.13.16 (October 5) |
| PostgreSQL integration | Real PostgreSQL 18.6; each test uses a disposable random schema in the dedicated test database |
| Redis/Celery | Real Redis and prefork workers; **17 worker/scheduler/incident-delivery/notification-worker tests** included in the 317 |
| Scheduler | Real Beat → maintenance queue → dispatcher → probe queue → worker and durable results verified; pending/republication/lease recovery tests pass |
| Migrations/schema drift | Empty-schema upgrade, head `f16b4d8e302a`, Alembic current/check, idempotent upgrade, downgrade/re-upgrade and data-preservation tests passed |
| API health | Healthy container startup; PostgreSQL outage returns readiness 503/liveness 200; reconnection passed |
| Frontend components | **107 passed** across 19 test files |
| Native browser E2E | **12 passed, 0 skipped** on October 4, all seven fixture configurations; real database, HTTP probes and local SMTP |
| Operational safeguards | **20 passed** for backup/restore/stack/benchmark safeguards; real Docker smoke validation also passed |
| Ruff | Lint and format passed: 115 backend files, 9 operational/fixture files |
| mypy | Strict checking passed for 67 application files |
| Frontend static checks | Prettier, ESLint, strict TypeScript and generated OpenAPI contract check passed |
| Production build | Fresh final container Next.js production build passed October 5; native build passed October 4 |
| Dependency consistency | Python `pip check` passed; both hashed Python locks had zero known advisories in the October 4 audit; final runtime scan is clean October 5 |
| npm audit | Production dependencies: **0**; full development tree: **5 high package entries from one unpatched braces advisory** |
| CI | actionlint 1.7.12 passed; hosted Actions execution was not triggered or claimed |
| Docker/runtime rebuilds | **Passed**: four runtime images and backend test image, `--no-cache --pull` |
| Container browser / stack smoke | **2 browser tests and 10 stack checks passed**; separate default Compose startup/restart also passed |
| Full benchmark | **Passed October 5**: 100 monitors, 10,000 successful real HTTP probes, zero failed |

October 5 container/static results are in the [sanitized validation record](evidence/container-validation-2026-10-05.json). October 4 native browser, secret review and lock audits retain their [original evidence](evidence/portfolio-validation-2026-10-04.json). Existing Starlette/AnyIO deprecation warnings remain. No application behavior or schema changed. Existing application locks are unchanged; two container-only locks pin the source-built psycopg extension and its build tools.

## Real user flow review

The following coverage uses the actual application code and database. Native browser fixture setup executes real loopback probes through the executor but accelerates test retry clocks; independent prefork-worker tests exercise Redis/Beat and real durable delays. This is complementary coverage, not a claim that fixture setup is a deployed background service.

| Flow | Evidence |
| --- | --- |
| Register, verify, sign in, reload, reset, sign out | Account and demo browser workflows, actual PostgreSQL sessions and Mailpit codes |
| Create/edit/pause/resume/archive monitor | Monitor browser/API flows; saved configuration and concurrency behavior checked |
| Due monitor → scheduler → Redis → worker → PostgreSQL | Real Beat/worker integration tests; no eager Celery substitute |
| Dashboard/history/response times | Browser and query tests using real completed HTTP attempts, weighted denominators and unknown gaps |
| Failure retries → confirmed incident → recovery | Real prefork/dispatcher tests and retained-evidence browser flow; three failed attempts and successful recovery checked |
| Assertions | Real bounded body/JSON evaluation, API/editor persistence and immutable historical snapshots |
| Notifications | Preferences, durable delivery workers, retry isolation, real local SMTP acceptance and delivery-history UI |
| Cross-account isolation | Owned monitor/history/analytics/assertion/incident/notification API tests deny other users; default demo remains private |
| Public demo | Explicit owner/monitor/version publication, real controlled observations, GET-only access and private-field exclusion |

The visual review covers landing/demo, blank login, registration validation, account feedback, dashboard/charts, monitor list/edit/detail, assertions, incident evidence and notification preferences/history at desktop/mobile widths. Monitor creation shares the validated editor. There is no separate general Settings page or analytics page: monitor settings, notification preferences, dashboard and detail analytics are the implemented surfaces. No dead Settings link was added. Loading, empty, failure and stale-data behavior is covered by component and browser tests. Chromium and keyboard/contrast checks do not amount to a full screen-reader or cross-browser accessibility certification.

## Security and public-file review

On October 4, a filesystem secret scan was run against an explicitly filtered copy of public candidate files. It excluded repository metadata, local credential directories, environments, dependencies, caches and generated outputs. **No secret scanner matches were found.** Known private configuration values were also compared without printing them; the only initial matches were the intentionally public unauthenticated loopback Redis default, not credentials. No credential rotation was indicated by these findings. `.env.example` files contain placeholders/local defaults only.

This establishes the inspected working-file result, **not Git history or index safety**. Repository metadata was neither read nor changed. Ignore rules do not remove an already tracked file or an old secret from history; the owner must review the eventual publication contents/history before making the repository public. Screenshots show disposable example.com fixture accounts and controlled loopback endpoints, not personal data or production targets. Captures contain no passwords, codes, cookies or response bodies.

Authentication/session/CSRF and per-resource ownership boundaries were reviewed and regression-tested. The SSRF review covered unsafe schemes, URL credentials, local/private/metadata addresses, all DNS answers, mapped/transition addresses, numeric connection pinning, TLS verification, disabled redirects/proxies and bounded bodies/deadlines. No fixture exception or protection was widened. Production fixture exceptions remain rejected. Operational logs use sanitized event/identifier fields; deployment ingress logging still needs its own review.

The development-only [braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) had no patched version in the October 4 review; the October 5 npm audit still reports the same five high dependency-tree entries, with zero production dependency findings. The installed chain is `eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces 3.0.3`; these are development tools, absent from the production npm dependency audit. Do not feed untrusted glob patterns to these tools. No application input is passed to this chain. npm's suggested fix is a framework tooling downgrade to version 14; it was not applied to a Next 16 application or used to hide the issue. Keep the finding open until a compatible upstream fix is available. No audit findings were suppressed.

[Historical October 4 security summary](evidence/portfolio-security-2026-10-04.json) distinguishes production dependencies, development advisories, exact pinned infrastructure images and the unselected OS candidate. The [earlier app-image scan](evidence/m20-image-audit.json) remains historical evidence. The [October 5 final image inventory](evidence/container-security-2026-10-05.json) records the clean scans of the exact rebuilt images, with every former critical/high match traced to its cause and remediation.

## Performance evidence and limits

The **2026-10-05 controlled local benchmark** used the final scanned runtime images:

| Measurement | Recorded result |
| --- | ---: |
| Simulated monitors / fixture accounts | 100 / 10 |
| Completed real HTTP probes / successful / failed | 10,000 / 10,000 / 0 |
| Probe worker concurrency / prefetch | 2 / 1 |
| Workload duration / throughput | 531.17 s / 18.826 completed probes/s |
| Dashboard API p50 / p95 | 33.264 / 49.364 ms, 383 samples |
| Queue lag p50 / p95 / maximum | 1951.342 / 3610.25 / 4975.61 ms |
| Sampled peak DB connections / active / pending-or-running | 7 / 4 / 74 |
| Recent-check query execution | 2.272 ms |

The fixture independently counted 10,000 completed HTTP responses. The fixture
returned 36 bytes after a 10 ms delay. Runs became due in accelerated batches
through the real dispatcher/Redis/prefork pipeline; one API client sampled reads
through the frontend proxy. This is controlled local test traffic, not customer
usage, typical internet latency, an SLA or a maximum capacity claim. Database
peaks are sampled lower bounds. Other validation stacks and heavy test/build
workloads were stopped before timing. The disposable benchmark project was removed.
[Full report, exact images, source hashes and hardware](evidence/container-performance-2026-10-05.json).

## Portfolio recommendations

Suggested repository description: **API monitoring with scheduled checks, response assertions, incident recovery, and historical analytics.**

Suggested topics: `nextjs`, `react`, `typescript`, `fastapi`, `python`, `postgresql`, `redis`, `celery`, `docker`, `playwright`, `monitoring`, `observability`.

Four resume bullets, grounded in the evidence above:

- Built an API monitoring platform with Next.js, TypeScript, FastAPI and PostgreSQL, supporting scheduled HTTP checks, response assertions, incident recovery and historical analytics.
- Implemented Redis/Celery background processing with durable retries and fenced leases; validated backend behavior with 317 tests, including 17 real worker and scheduler tests.
- Executed a controlled local benchmark of 10,000 HTTP probes across 100 simulated monitors, measuring 18.826 probes/second and 49.364 ms dashboard API p95 latency on the final container images.
- Developed a responsive monitoring dashboard, opt-in email notifications and a restricted read-only demo, validated with 107 component tests and 12 browser workflows using real database and SMTP fixtures.

The README is prepared for a public repository with honest current status; it must not be described as a live deployed project yet. No project license was added or changed. Upstream Node license notices are retained inside the runtime image. Remaining product limits include one monitoring location, email-only delivery, 30-day raw history, run-weighted uptime and possible duplicate external effects after ambiguous worker/SMTP failures. Cloud resilience and security controls remain deployment work, not implemented features.

Suggested commit message: `fix: remediate runtime images and verify container release`.
