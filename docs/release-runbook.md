# Release and operations runbook

Milestone 20, 2026-10-02. This is an **unexecuted cloud runbook**. Only local validation was performed; see the [current container release evidence](container-release.md) and the [historical audit](release-audit.md). Publishing, resource creation, production migrations and public DNS require separate authorization. The [proposal](deployment-proposal.md) defines the resources and costs; current development Compose is not a production manifest.

## Release gate and inventory

A release operator owns the checklist and a second reviewer should review security/network and restore evidence before public launch. Record actual names, timestamps and evidence; no reviewers or approvals are implied here.

1. Resolve the deployment blockers in the audit. Update vulnerable base packages/images and rescan **all** selected runtime images, including the eventual ingress/host. For each residual finding record package, advisory, reachability, vendor status, mitigation, accountable owner and expiry; never suppress a severity globally. Reject unreviewed critical/high findings. Also review interpreter and embedded-library vendor advisories against actual runtime versions/linkage: package scans missed CPython and bundled OpenSSL findings in the [October 5 review](container-release.md).
2. Choose domain, account, region, budget and operator. Validate AWS engine/class availability, SES production access and alarm delivery. Review IAM grants, production configuration and data retention. No fixture exceptions, test credentials, test database initializer or Mailpit.
3. Build locked dependencies and scanned base digests; record source SHA-256 manifest, image content IDs and migration head. Record the previous compatible image digest before publishing. Scan the final images after build, not just lockfiles. ECR tags are immutable; deploy digests. Publishing remains disabled until authorized.
4. Run the local checks below, then staged cloud probes for real DNS/TLS, metadata/private-target rejection, redirects, deadlines, client-IP trust, cookie flags, Origin/CSRF rejection, auth ownership, SES, pending reconciliation and worker replacement. Do not use customer targets without permission. Verify host/task limits and database connection headroom.
5. Prove encrypted backup and isolated restore, including account/session/monitor/run/incident/delivery integrity and migration head. Confirm recipient of a real test alarm. The local restore result does not prove S3/IAM/AMI recovery.
6. Record a change window and rollback decision, release digests, backup object/version/checksum, old/new schema versions and explicit authorization. No successful hosted CI run, public endpoint, capacity claim or SLA may be asserted without its evidence.

## Repeat the local release checks

Use the existing Python `.venv`, Node 24/npm 11, Docker, and project-local browser dependencies. No machine installation or repository commands are needed. From root:

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/ruff check --config backend/pyproject.toml scripts containers
.venv/bin/ruff format --check --config backend/pyproject.toml scripts containers
(cd backend && ../.venv/bin/mypy app)
.venv/bin/python -m pytest scripts/tests -q
(cd frontend && npm run check && npm run api:check && npm run build)
BUILDX_GIT_INFO=false docker compose --env-file .cache/compose.env build --no-cache --pull api frontend postgres redis
BUILDX_GIT_INFO=false docker compose --env-file .cache/compose.env -f compose.yaml -f compose.test.yaml build --no-cache --pull backend-tests
.venv/bin/python scripts/verify_local_stack.py
```

The full backend container suite uses the explicit test overlay and isolated project, as documented in [containers](containers.md). It must include `--run-integration --run-worker --run-mailpit`, not just the default skipped integration set. Native browser commands/fixture flags are documented in the account, dashboard, history, assertion, notification and demo guides; execute each feature suite with its required real fixtures. Run `tests/e2e/containers.spec.ts` separately with `TEST_CONTAINER_ORIGIN` pointing at a disposable local stack. Both tests must run, not skip. Do not save traces containing accounts or tokens. For a browser run following `verify_local_stack.py --keep`, remove only the printed isolated project/volumes afterward.

Application audits: run `pip-audit --require-hashes --disable-pip --no-deps` against each Python lock using an isolated local scanner environment, and `npm audit --json` against the frontend lock. Scan final OCI filesystems separately. Runtime installers are deliberately absent; `python -m pip check` belongs in the project/test environment, not the hardened backend runtime. Database dumps and private scanner/cache contents are not release attachments; publish only reviewed sanitized evidence.

## Deployment sequence after a separate approval

Prepare the approved production manifest and exact environment privately. Verify ingress/network denies, encrypted volume mounting, secrets and backup access before accepting public traffic. Runtime app roles have no schema mutation privileges. A migration role performs changes once; do not run concurrent migrations or roll out workers before schema readiness.

For a schema-changing release: take and verify a fresh backup; enter maintenance, stop Beat and new writes, drain bounded active work, then stop workers. Stop old executors before any lease-model change. Run `python -m alembic current`, review expected head, then `python -m alembic upgrade head` and `python -m alembic check` in the one-shot approved backend image with the migration role. Current local head is `f16b4d8e302a`. A migration failure stops rollout; retain the old stack and evidence, do not blindly downgrade.

Start database/broker, API, frontend, probe/maintenance workers and finally one Beat. Check process readiness plus **new durable scheduled completions**, lease recovery and delivery state. Expose HTTPS only after private validation. Confirm real signup/verification, sign-in/full page reload, owner-only CRUD, a controlled successful probe, three-failure incident and recovery, preferences, one email for each enabled transition, opt-in demo redaction, mobile pages and backup alarm. Public publication requires an explicit owner-controlled monitor/configuration-version allowlist; default empty is safe. Remove disposable staged accounts using a reviewed procedure; never relabel their observations as customer data.

## Backup and restore

Proposed host schedule: daily at 02:00 UTC, PostgreSQL 18 `pg_dump --format=custom --no-owner --no-acl` to an exclusive new file. A successful dump is transactionally consistent; capture version and checksum without logging its contents. Upload to the encrypted private S3 prefix with object versioning. Retain seven daily and four weekly generations; lifecycle rules must also expire noncurrent versions according to the approved retention. 100 GB is a budget assumption, not a proven retention footprint. Do not count Redis AOF or a crash-consistent disk snapshot as the authoritative database backup. Save image/configuration manifests and Caddy certificate state separately, never plaintext credentials in the evidence package.

Monthly, restore the latest backup to a **new isolated database/host**, using matching PostgreSQL major version and the recorded application image. Deny outbound probe/email delivery during restoration; do not start Beat. Validate archive format/checksum, restore transaction success, Alembic head, all-table counts/fingerprints and critical relationships, and application read paths. Existing `scripts/local_stack.py restore` deliberately requires a new `devpulse_restore_<name>_test` database and rejects overwrite. Example against an explicitly disposable local stack:

```bash
.venv/bin/python scripts/local_stack.py --project devpulse-local-test backup .cache/new-release-backup.dump
.venv/bin/python scripts/local_stack.py --project devpulse-local-test restore .cache/new-release-backup.dump --database devpulse_restore_release_test
```

The helper is local-only and does not upload or select production targets. The cloud implementation must preserve these refusal/transaction guarantees. Never run `pg_restore --clean` against the live database. Keep restored schedules paused and notifications isolated until an operator approves their reconciliation. Old sessions and consumed tokens may be present in an older backup: revoke restored sessions/auth tokens using a reviewed transactional maintenance procedure before reopening accounts. Check delivery state before resuming notifications to avoid unexpected repeat emails.

For disaster recovery, record the recoverable timestamp and accepted data loss, restore to a new encrypted disk/database, verify it privately, then switch the application connection and resume workers/Beat under observation. Raw check retention is 30 days; incidents and compact evidence persist indefinitely. Backup retention is separate and can preserve data beyond active-table deletion. The proposed 24-hour RPO/4-hour RTO is not achieved until a timed cloud drill proves it.

## Rollback

If the schema is unchanged and compatible, stop Beat/new writes, drain/stop workers, replace app images with the previously approved digests, start workers and one Beat, then verify pending work and auth/HTTP smoke. Preserve database and Redis volumes. Do not roll back only one writer while incompatible writers remain active.

If schema changes are incompatible, prefer a forward fix. Restoring the pre-release database into a new target is a data-loss operation requiring an explicit recovery decision and communication of lost writes. Do not automatically run Alembic downgrade. Verify the restored schema against the old image, revoke restored credentials as above, and switch only after inspection. Keep the failed state quarantined for investigation within the approved retention. Never use `down --volumes` for a production rollback.

## Alarms and incident response

The following is the proposed **15 standard alarm-metric budget**, evaluated every minute unless noted. Ten custom aggregate metrics are budgeted: memory, disk, API errors, oldest due pending age, expired leases, stale monitor count, oldest notification age, backup age, certificate days remaining and Beat heartbeat age. Use low-cardinality deployment-level metrics, not per-monitor/account/URL dimensions. Batch one publication/minute (~44,000 calls/month). EC2 CPU/status, RDS metrics and Route 53 health provide service metrics. Exporters, heartbeat collection and cloud alarms are not implemented in this repository; all must be provisioned/tested before launch. Missing operational telemetry is alarming, never interpreted as healthy.

| # | Alarm trigger (initial threshold) | First response |
| --- | --- | --- |
| 1 | Host status check failed for 2 periods | Check host/AZ, preserve volumes; invoke restore path if needed |
| 2 | CPU >80% for 10 minutes | Inspect bounded queue/load; reduce admissions, no blind worker scaling |
| 3 | Memory >85% for 5 minutes | Inspect process limits and OOM events; preserve DB headroom |
| 4 | Data disk >80% for 5 minutes | Verify retention/backups; alert urgent at >90%; never delete DB/AOF files |
| 5 | API 5xx >5% for 5 minutes, at least 20 requests | Inspect sanitized request IDs, DB readiness and recent release |
| 6 | External HTTPS health failed for 3 checks | Separate ingress/certificate/host/API causes; maintenance notice |
| 7 | Oldest eligible pending age >120 seconds for 3 minutes | Check broker, worker process and due reconciliation; do not delete runs |
| 8 | Expired lease count >0 for 5 minutes | Check worker death/reclaim and stale fencing; never force-finalize a stale lease |
| 9 | Stale monitor count >0 for 5 minutes | Correlate schedule/queue and observation freshness; process health is insufficient |
| 10 | Oldest due notification >300 seconds for 5 minutes | Check SES/TLS/credentials/delivery retries; never print email or tokens |
| 11 | Latest verified backup age >26 hours | Diagnose job/S3 access; take fresh backup and prove restore |
| 12 | Certificate <14 days remaining | Repair renewal/DNS; never disable certificate validation |
| 13 | Beat heartbeat missing >120 seconds | Confirm singleton and DB/Redis reachability before restart |
| 14 | Actual monthly spend crosses selected budget | Owner reviews resource inventory and usage; alert is not a spending cap |
| 15 | Forecast monthly spend crosses selected budget | Owner revises load/retention or approves spend; no automatic destructive shutdown |

Spend alarms can be implemented as account billing/Budgets notifications; the model conservatively reserves standard alarm charges for all 15. Cost recipient and service-health recipient may differ but both must be confirmed. Managed replacement needs ECS service/task health and RDS/Redis failover/CPU/memory alarms; recompute the alarm/metric budget if these exceed the allocation. No promise that one monitor captures every failure.

For Redis loss, restore broker connectivity and let PostgreSQL pending reconciliation republish. Lost broker data is not lost monitoring history. Duplicate messages are expected; fencing and unique effects must remain enabled. Do not insert fabricated checks to conceal a gap. For database loss, readiness fails while liveness can remain up; stop admissions/writers until it recovers. For SMTP failure, monitoring continues independently; inspect safe delivery status/backoff and fix transport before reattempting. Provider acceptance is not proof of inbox delivery.

For suspected credential exposure: restrict ingress/affected service, preserve only redacted incident evidence, rotate the narrow affected secret, revoke sessions as appropriate, restart dependents and test recovery. Database rotation uses a temporary second login so connections can drain; broker ACL rotation must retain task compatibility until consumers reconnect. Rotate SES credentials separately and verify sender health. IAM credentials should be temporary roles; do not introduce static cloud access keys. No request bodies, authorization/cookie headers, URL query strings, SQL bound values or email contents in application, ingress, database or collector logs.

## Removal after a separate approval

Inventory resources by approved DevPulse tags/account/region. Obtain owner decision for final backup retention and permanent data deletion. Stop signup/writes, Beat and workers; take/verify final backup; remove DNS and observe TTL; revoke SES/secret access; stop workloads. Only then remove the named DevPulse compute, ALB/NAT/Elastic IP resources and their routes/security groups, ECR images, secret versions and observability resources as authorized. Delete data volumes, RDS snapshots and **all S3 object versions** only after explicit retention/deletion approval. Retained disks, IPs, snapshots, buckets, zones, secrets and logs can continue billing even when the application is down. Verify the bill/resource inventory afterward. Never remove shared VPC/zone/account resources or another project's containers.
