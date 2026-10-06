# Release audit — milestone 20

This is the historical 2026-10-02 audit. See the [current portfolio release report](portfolio-release.md) for the latest results and local portfolio status.

**Milestone 20's local audit is complete.** Its cloud design study is retained as optional historical engineering work, not a portfolio completion requirement. No cloud resource, paid service, image publication, public DNS or deployment was created. No repository operations were performed. Audit evidence was gathered on 2026-10-01/02 in Ubuntu 24.04 WSL2 using Python 3.13.15, Node 24.21.0, PostgreSQL 18 and real Redis/Celery workers.

The package consists of this audit, [AWS topology/cost proposal](deployment-proposal.md), [release/operations runbook](release-runbook.md), [actual screenshot gallery](release-screenshots.md), and sanitized [validation](evidence/m20-validation.json), [dependency](evidence/m20-dependency-audit.json), [image](evidence/m20-image-audit.json), [cost](evidence/m20-cost-model.json) and [source manifest](evidence/m20-source-manifest.json) evidence. This completes preparation; it does not certify production security, cloud capacity, accessibility compliance or availability.

## Release changes and regression evidence

The audit found that authenticated server-rendered layouts always fetched `127.0.0.1:8000`. Inside the separate frontend container that is the wrong network namespace. Public pages and the browser proxy worked, hiding the failure until sign-in. The server now selects the fixed internal `http://api:8000` only in container mode, retaining native loopback otherwise. The runtime image sets the same container-mode flag as the build. Fetches still use no-store, a timeout, no redirects and the validated session cookie. No arbitrary backend origin was introduced.

A real browser regression reproduces the failure against the previous image, then passes against the fixed image: create a disposable account, sign in, render Overview, reload the full page and navigate to Monitors. Both container browser tests passed again against the final hardened images.

The runtime images no longer contain unused Python pip/ensurepip or Node npm/Corepack/Yarn installers. Build/test stages retain required tooling; locked application dependencies are unchanged. Final image scans removed six Python installer-vendor advisory matches and nineteen npm-vendor matches. Runtime imports, migrations, workers, backup/restore and UI still pass. This reduces shipped attack surface; it does not resolve OS findings below.

## Local validation results

| Check | Result and scope |
| --- | --- |
| Backend full container suite | **317 passed**, no skips, 310.03 seconds; real PostgreSQL, Redis, prefork Celery and Mailpit |
| Operational safeguards | **20 passed**; backup/restore, stack isolation and benchmark safeguards |
| Frontend | **107 passed**; Prettier, ESLint, strict TypeScript and generated API contract drift passed |
| Builds | Native Next.js production build and backend/frontend/test container builds passed |
| Native Chromium feature suites | **12 passed**, no skips: six account/monitor flows, plus incidents, dashboard, history, assertions, notifications and public demo |
| Final container Chromium | **2 passed**, no skips; public desktop/mobile/API/assets and authenticated SSR reload/navigation |
| Final stack smoke | **10 passed**; migration/head/drift, real scheduler/retries/incidents/email, stopped-worker pending recovery, Redis recovery, DB outage/readiness, all-table restore fingerprints, overwrite refusal, AOF/data persistence and full restart |
| Ruff | Backend 115 files and operations/fixture 9 files passed lint/format |
| mypy | 67 application source files passed |
| CI syntax | actionlint 1.7.12 passed; no hosted Actions run was triggered |
| Dependency consistency | Project `pip check` passed; hashed Python locks and npm lock advisory audits found zero known application dependency advisories |
| Runtime hardening | Non-root UID10001, read-only app services, private service ports, singleton Beat; no runtime installers or private `.env` files |

Current migration is `f16b4d8e302a`; fresh volumes applied the complete chain, including fenced leases `b31d8e0c6a10`. All ten final stack checks ran after the runtime-installer removal. The full backend suite covered unchanged application code; final runtime smoke covered the subsequent installer-only hardening. An initial native browser attempt lacked a persistent Mailpit process and failed setup; after starting the local prerequisite, all seven feature-suite invocations passed. The two existing Starlette/AnyIO deprecation warnings remain; they are not test failures.

The [milestone 19 evidence](performance.md) remains the historical 100-monitor/10,000-real-probe performance result (12.628 completed probes/second in that workload). It was not rerun or relabeled as a milestone 20/cloud benchmark. No backend probe/analytics code changed in this audit. Local browser coverage is Chromium at tested desktop/mobile sizes, with contrast/component keyboard/focus checks and visible layout review. It is not a screen-reader audit or proof of Safari/Firefox support.

## Reviewed behavior and evidence boundaries

| Area | Finding / evidence |
| --- | --- |
| Authentication and ownership | Database-backed hashed opaque sessions, Argon2id, verified-monitor creation, token expiry/single use, reset revocation, CSRF plus Origin, owner-scoped 404s; real account/browser and DB tests pass. Frontend protection is UX; API is the boundary. |
| Production cookies/config | Secure host-only `__Host-` cookies and HTTPS origin/SMTP constraints exist; fixture destinations rejected in production. Actual public TLS/proxy/client-IP behavior still needs staged validation. |
| SSRF and bounds | Every DNS answer checked; public numeric address pinned, original TLS hostname verified; private/mixed/metadata/transition addresses rejected, no redirects or environment proxies; wire/decoded/header/time bounds tested. Cloud network defense remains unimplemented. |
| Queue correctness | PostgreSQL authoritative pending/retry/delivery state, fenced leases, duplicate-safe effects, no transaction held over probe I/O; real worker loss, broker/DB failures, outdated configurations and reconciliation covered by integration/worker/smoke tests. |
| Monitoring semantics | Three failed attempts confirm incidents; recovery/evidence retained. Scheduled metrics exclude manual and excluded outcomes, show denominators/gaps and nullable latency; completed observations do not imply time-weighted uptime or an SLA. |
| Assertions / mail | Bounded assertions and immutable snapshots; transactional delivery and retry state; preferences and real SMTP acceptance tested. Provider acceptance is not inbox delivery. SES bounce/complaint integration is not implemented. |
| Quotas / retention | 10 monitors/account, 100 enabled globally; bounded scheduling, 30-day raw checks, retained incidents/evidence; tests cover locking and retention relationships. Long-running cloud storage growth is unmeasured. |
| Demo / UI | Publication is opt-in per owner/monitor/configuration version, fail-closed, read-only, hides URL/account/evidence. Actual local controlled observations are labeled; no live deployment or customer history claimed. Mobile layout, labels, keyboard/focus and contrast tests pass within stated coverage. |
| Logs / errors | Fixed safe error codes, request/job identifiers, no raw bodies/headers/query strings, DB statement/parameter logging suppressed; safe failure-path tests. Future ingress/agent logs need independent redaction checks. |
| Packaging / CI | Allowlisted build contexts exclude local secrets; runtime packages are locked, bases digest-pinned, API contract generated, CI Actions pinned/read-only with no publishing/deployment job. Remote execution is unverified. |
| Service health | API readiness checks startup/DB; worker health checks process/DB/broker, not completed-work freshness. Per-monitor stale state exists. The handoff's planned authenticated monitoring-service-status endpoint is **absent**; no endpoint or aggregate heartbeat exporter is claimed. |

## Historical image findings — remediated October 5

Trivy 0.75.0, database updated 2026-10-02T01:05:41Z, scanned final local image filesystems. Counts below are package/advisory occurrences, **not unique CVEs or demonstrated exploits**. Vendor statuses and fixed versions are retained per match in [image evidence](evidence/m20-image-audit.json). Raw descriptions, secrets, response data and environment configuration are excluded.

| Image | Critical | High | Medium | Low | Unknown | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Backend (Debian 12.15) | 5 | 58 | 115 | 91 | 2 | 271 |
| Frontend (Debian 12.15) | 4 | 53 | 99 | 75 | 2 | 233 |
| PostgreSQL (Debian 12.15 plus packaged helper) | 16 | 102 | 210 | 163 | 6 | 497 |
| Redis (Alpine 3.21.8) | 0 | 4 | 14 | 2 | 0 | 20 |

The backend/frontend final language-package findings are zero; this is separate from the clean application lockfile audits. Fix versions were reported for 13 backend, one frontend, 59 PostgreSQL and all 20 Redis occurrences. Other matches have affected/deferred/will-not-fix statuses. For example, Debian SQLite/Perl/zlib matches include critical vendor advisories; scanner severity alone does not establish that DevPulse exercises the vulnerable path. No finding was accepted, suppressed or declared unreachable in this audit.

The follow-up image work below was completed in the [October 5 validation](container-release.md). The October 2 recommendation was to refresh selected patched base/database/broker pins, rebuild and rerun relevant regression tests, rescan final artifacts, then perform per-finding vendor/reachability review for residual matches. Do not install unpinned OS upgrades during runtime or silently change database major versions to clear scanner output. Record fixed-version verification, remaining risks, owner and expiry. The local Mailpit and fixture images are development-only, excluded from the proposed deployment. Host AMI, Caddy, managed-service patch levels and cloud policies do not yet exist and therefore were not scanned. This audit is not a penetration test or supply-chain attestation.

## Optional hosting considerations (historical design study)

| Gate | Required disposition before public deployment |
| --- | --- |
| Image advisories | Remediate available fixes; reviewed disposition for every residual critical/high match. Completed for the four local runtime images on October 5. |
| Production ingress/isolation | Implement/review TLS, request limits/security headers, trusted client-IP forwarding, host/task metadata and private-network egress rejection; prove with staged adversarial requests. |
| Operational detection | Implement aggregate freshness/lease/pending/delivery/backup/Beat metrics and tested alarm delivery; readiness alone is inadequate. Decide whether to implement the planned authenticated service-status endpoint or formally accept its omission. |
| Cloud restore and load | Time an isolated encrypted restore; measure chosen instance/task sizes, worker replacement and realistic external DNS/TLS/failure load; verify DB connection headroom. |
| Identity/email/domain | Owner-selected account/domain/operator, SES production access and bounce/complaint procedure, public signup abuse review, runtime/migration DB roles and broker ACLs, secret rotation. |
| Budget / risk | Approve single-host failure risk or managed alternative, region/data retention, monthly budget and overages; proposal estimates $112.23 / $424.36 USD at stated assumptions. |
| Publishing / live URL | Separate explicit approval, approved immutable image digests, staged smoke results and rollback record. No live URL currently exists. |

These conditional hosting considerations are outside current portfolio scope, not work performed on cloud resources or implied authorization for another milestone. Existing native services and unrelated containers were preserved; disposable validation stacks and the audit's Mailpit process were removed after checks. The repository owner handles all repository operations.

Suggested commit message: `chore: complete release audit and deployment approval package`.
