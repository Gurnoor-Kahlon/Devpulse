# Runtime image remediation and Docker validation

Release blockers 1 and 2, **2026-10-05**. This work concerns local release artifacts
and validation. It does not deploy the application, publish images, create cloud
resources, or establish public URLs. Production deployment remains a separate gate.

## Image findings and remediation

Docker access was restored in Ubuntu 24.04 WSL2: client/server **29.2.0**, Compose
**5.0.2**. All four production-intended runtime images are rebuilt using
`--no-cache --pull`; the backend test target was also rebuilt. API, migrations,
probe/maintenance workers and Beat share one backend runtime image. Mailpit and
the test/build targets are development tooling, outside production runtime scope.

Fresh Trivy **0.75.0** scans of the old images identified **241 critical/high
package-advisory matches representing 54 distinct advisory IDs**. Counts include
repeated matches for the same advisory across packages/images. They do not prove
that each finding was exploitable through DevPulse.

| Runtime image | Before critical | Before high | After critical | After high | After all severities |
| --- | ---: | ---: | ---: | ---: | ---: |
| Backend / Celery / Beat / migrations | 5 | 58 | 0 | 0 | 0 |
| Frontend | 4 | 53 | 0 | 0 | 0 |
| PostgreSQL | 16 | 101 | 0 | 0 | 0 |
| Redis | 0 | 4 | 0 | 0 | 0 |

[The complete scanner critical/high inventory](evidence/container-security-2026-10-05.json)
identifies **every** matched advisory ID, package/version, source image or binary,
vendor status/fixed version where reported, reference URL and remediation. It
also records scanner database timestamps, exact image IDs, raw-report hashes and
all installed packages detected in the final images. Direct binary/library checks
supplement that package inventory below. Earlier dated reports are retained
as history; their counts can differ as the vulnerability database changes.

- **Backend and frontend:** replaced Debian 12 bases with digest-pinned official
  Alpine 3.24 images, using Python **3.13.16**, Node **24.21.0** and the existing
  application lockfiles. The affected Debian util-linux, Perl, ncurses, zlib and
  other OS packages are replaced by the new base's package set. This does not
  claim the old Debian packages received fixes. Application installers (`pip` and `npm`)
  remain absent from the final runtime; Alpine package metadata is retained.
- **PostgreSQL:** moved PostgreSQL **18.6** to its pinned Alpine 3.24 image. The
  bundled `gosu` executable contained Go **1.24.6**, responsible for **22**
  critical/high matches. It is removed and the official entrypoint now invokes
  packaged `su-exec 0.3-r0`, preserving direct privilege-drop and exec semantics.
  Patched `nghttp2-libs` from **1.69.0-r0** to **1.70.0-r0** also removes the
  candidate image's medium `CVE-2026-58055` finding.
- **Redis:** retained Redis **7.4.11** and its pinned official base. Updated
  `libcrypto3` and `libssl3` from **3.3.7-r1** to **3.3.7-r2**, fixing high
  `CVE-2026-75804` and `CVE-2026-84782` in both packages, plus their lower-severity
  matches.

The package scan alone missed interpreter and bundled-library vulnerabilities.
A direct vendor review additionally identified these CPython 3.13.15 findings,
all fixed by **3.13.16**: **CVE-2026-19445 (critical), CVE-2026-19553 (high), and
CVE-2026-82049 (high)**. Together with the scanner inventory, this is **57 distinct
critical/high advisory IDs**. The release also fixes five lower-severity Python CVEs.
The host `.venv` remains Python 3.13.15 as requested; the container interpreter
is patched. This pass does not certify the host interpreter or development/build
tooling as advisory-free.

The OpenSSL advisory **CVE-2026-84782** also affected Node's statically embedded
OpenSSL **3.5.8** and the candidate Alpine PostgreSQL libraries. Psycopg's binary
wheel bundled **3.5.7**, affected by that advisory and **CVE-2026-75804**. These
OpenSSL IDs overlap the scanner's Redis findings, but the bundled occurrences
were missing from its results. Final remediation includes:

- Build Node **24.21.0** from its SHA-256-checked upstream source with
  `--shared-openssl`, and install OpenSSL **3.5.9-r0** in the minimal runtime.
  The image retains upstream Node and bundled third-party license notices.
- Build psycopg's **3.3.6 C extension** against system libpq **18.6-r0**, remove
  the binary-wheel distribution and its bundled libraries, and require
  `PSYCOPG_IMPL=c`. Both runtime and test images use this same implementation.
  Two hashed container-only locks pin the C extension and its build tooling.
- Pin PostgreSQL's OpenSSL libraries to **3.5.9-r0** too. OS packages and Node's
  shared library bindings remain visible for inspection and scanning.

[Python's security release](https://www.python.org/downloads/release/python-31316/),
[September OpenSSL advisory](https://openssl-library.org/news/secadv/20260929.txt),
and [psycopg's production installation guidance](https://www.psycopg.org/psycopg3/docs/basic/install.html#local-installation)
explain the interpreter fixes, patched library version and supported system-library
build. This review demonstrates why a zero package-scanner count is insufficient
by itself. Final evidence includes direct binary version/linkage verification and a real
certificate-validated TLS 1.3 request from the final Node runtime (HTTP 200).

No advisory ignore file, severity/status suppression, package-database removal,
or accepted-risk exception was used. Final images have **zero reported findings
at every severity** in this scan. That is a dated scanner result, not a promise
against unknown vulnerabilities or a substitute for deployment security checks.
The separate development-only braces advisory recorded in the
[portfolio report](portfolio-release.md#security-and-public-file-review) is not
part of these runtime images.

Alpine uses musl rather than glibc; official Node images document that compatibility
tradeoff. The full container checks must accompany this base change. Existing
Debian PostgreSQL volumes require a separately planned logical backup/restore
migration; see [container operations](containers.md). None were converted here.
Redis's Alpine 3.21 main support ends **2026-11-01**: rebase and repeat these checks
before that date. Alpine 3.24 main support runs through **2028-06-01**.

Upstream references: [Python images](https://hub.docker.com/_/python),
[Node image variants](https://github.com/nodejs/docker-node),
[PostgreSQL images](https://hub.docker.com/_/postgres),
[su-exec behavior](https://github.com/ncopa/su-exec),
[Alpine support dates](https://alpinelinux.org/releases/).

## Reproduction

Use the existing project environment and Docker integration; no host package or
permission changes are needed. Keep the private Compose environment file intact.

```bash
python3 scripts/local_stack.py init
BUILDX_GIT_INFO=false docker compose --env-file .cache/compose.env \
  -f compose.yaml -f compose.test.yaml build --no-cache --pull \
  api frontend postgres redis backend-tests
# With the reviewed Trivy version on PATH; retain complete JSON, not only high findings:
trivy image --scanners vuln --format json --output backend-scan.json devpulse-backend:local
trivy image --scanners vuln --format json --output frontend-scan.json devpulse-frontend:local
trivy image --scanners vuln --format json --output postgres-scan.json devpulse-postgres:local
trivy image --scanners vuln --format json --output redis-scan.json devpulse-redis:local
```

Verify the interpreter and linked libraries too; an OS/package scan alone missed
these components during the first candidate review:

```bash
docker run --rm devpulse-backend:local python -c \
  'import sys, ssl, psycopg; print(sys.version.split()[0], ssl.OPENSSL_VERSION, psycopg.pq.__impl__, psycopg.pq.version())'
docker run --rm devpulse-frontend:local node -p \
  'JSON.stringify({node:process.versions.node,openssl:process.versions.openssl,shared:process.config.variables.node_shared_openssl})'
```

Expected: Python **3.13.16**, OpenSSL **3.5.9**, psycopg implementation **c** and
libpq **180006**; Node **24.21.0**, OpenSSL **3.5.9**, shared OpenSSL **true**.

Raw scanner output can include image configuration. Review/sanitize before sharing;
the published evidence uses an allowlist and contains no interpolated credentials.
Cold frontend builds compile Node from source with two compiler jobs to bound
local memory use. The verified cold Node compile/install step took **11,683.8
seconds (about 195 minutes)** on this machine. Unchanged rebuilds reuse that
compiled stage; first builds can take several hours. CI stack/performance jobs
allow 240 minutes for cold compilation
and validation; no hosted run was triggered.

Full stack/backend/browser instructions are in [containers](containers.md), and
the 100-monitor/10,000-probe workload is in [performance](performance.md).

## Container validation

- **317 backend tests passed, zero failures/skips**, in **374.13 seconds** inside
  the rebuilt Python 3.13.16 Alpine test image with the psycopg C driver. Real PostgreSQL, Redis, prefork workers,
  scheduler/fenced-lease recovery and Mailpit SMTP were enabled. Two existing
  Starlette/AnyIO deprecation warnings remain.
- **10/10 stack checks passed** from fresh volumes: readiness and migrations;
  UID/port/single-Beat controls; signup and real SMTP verification; scheduled
  HTTP probes with durable retries, incident and recovery emails; pending work
  across worker loss; Redis outage recovery; PostgreSQL outage health/reconnect;
  full-row backup/restore fingerprints and overwrite refusal; PostgreSQL/Redis
  persistence across container recreation; and full restart/idempotent migrations.
- **2/2 Chromium container tests passed**, covering desktop/mobile public UI and
  assets, same-origin API, sign-in, protected rendering and full-page reload.
- A **separate default Compose stack without test overlays** passed clean startup,
  migration head `f16b4d8e302a`/schema drift, Redis PONG, healthy workers/Beat/API/
  frontend, private API denial and shutdown/recreation. PostgreSQL and Redis
  server processes ran as non-root UIDs 70 and 999 respectively.
- **107 frontend tests** and **20 operational safeguards** passed. Ruff lint and
  format, mypy (67 files), frontend format/lint/types, generated API contract,
  image production build, test-image `pip check` and actionlint passed.
- All four production runtime images and the backend test image built from
  scratch. A subsequent fresh frontend runtime-stage build added the upstream
  license notices, reusing only the Node source stage compiled in this same pass.
  Existing Python/npm application locks and application source were unchanged;
  container-only build locks were added. Updated CI
  and reproduction commands build the new PostgreSQL/Redis Dockerfiles too;
  benchmark source hashes now include those build inputs.

The first smoke attempt stopped at the PostgreSQL-outage assertion: the default
five-second HTTP client timeout expired during Docker DNS's approximately
five-second lookup failure. A diagnostic call returned readiness **503 after
5.073 seconds**, while liveness returned **200**. The harness now allows a bounded
15 seconds for the outage assertion and three seconds for liveness. The full
fresh-volume rerun passed; application health behavior and its container timeout
were not relaxed. A separate native operational test initially lacked sandbox
socket permission and passed when rerun with loopback access.

All created validation projects use isolated test data and are removed after
validation. No existing database volume, host service or private configuration
was migrated or altered. Native browser coverage from 2026-10-04 remains separately
dated; it is not relabeled as a new run.

## Final benchmark and disposition

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

**Blockers 1 and 2 are resolved as of October 5.** The only remaining release
blocker is production deployment/public URLs, which this work did not begin.
[Build/test evidence](evidence/container-validation-2026-10-05.json) and
[current source manifest](evidence/container-source-manifest-2026-10-05.json).
