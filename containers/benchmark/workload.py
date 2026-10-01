"""Disposable, accelerated scheduled-run benchmark. No observations are fabricated."""

import argparse
import json
import logging
import math
import platform
import secrets
import threading
import time
from collections import Counter, defaultdict
from datetime import timedelta
from importlib.metadata import version

import httpx
from app.core.config import load_settings
from app.core.security import now_utc, password_hasher
from app.db.session import create_database_engine
from app.factory import create_app  # noqa: F401 -- register persisted models
from app.jobs.dispatcher import dispatch_runs
from app.models.auth import User
from app.models.monitor import Monitor
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

STATS = """
SELECT xact_commit, xact_rollback, blks_read, blks_hit, tup_returned, tup_fetched,
       tup_inserted, tup_updated, tup_deleted, conflicts, temp_files, temp_bytes, deadlocks
FROM pg_stat_database WHERE datname = current_database()
"""


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"samples": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "samples": len(ordered),
        "p50_ms": round(ordered[math.ceil(len(ordered) * 0.50) - 1], 3),
        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
        "max_ms": round(ordered[-1], 3),
    }


def guard(settings, empty):
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment != "test"
        or url.host != "postgres"
        or url.database != "devpulse_test"
        or not empty
    ):
        raise ValueError("Benchmark requires an empty disposable Compose test database.")


def database_stats(engine):
    with engine.connect() as db:
        return dict(db.execute(text(STATS)).mappings().one())


def measure_api(client, paths, stop, samples, statuses):
    # One in-flight request, one request every >=250 ms; cycles evenly across paths.
    while not stop.is_set():
        for label, path in paths.items():
            if stop.is_set():
                return
            start = time.monotonic()
            try:
                response = client.get(path)
                statuses[str(response.status_code)] += 1
            except httpx.HTTPError:
                statuses["transport_error"] += 1
            samples[label].append((time.monotonic() - start) * 1000)
            stop.wait(0.25)


def run(rounds):
    settings = load_settings()
    engine = create_database_engine(settings)
    stop = threading.Event()
    thread = None
    client = httpx.Client(base_url="http://frontend:3000", timeout=10, trust_env=False)
    # The runtime logger stays enabled in workers; the harness emits only allowlisted JSON.
    logging.getLogger("devpulse").disabled = True
    started_at = now_utc().isoformat()
    try:
        with Session(engine) as db:
            empty = db.scalar(select(User.id)) is None
        guard(settings, empty)
        password = secrets.token_urlsafe(32)
        hashed = password_hasher.hash(password)
        with Session(engine) as db, db.begin():
            for account in range(10):
                user = User(
                    email=f"benchmark-fixture-{account}@example.com",
                    password_hash=hashed,
                    email_verified_at=now_utc(),
                )
                db.add(user)
                db.flush()
                for number in range(10):
                    monitor = Monitor(
                        user_id=user.id,
                        name=f"Benchmark fixture {account * 10 + number + 1:03}",
                        url="http://127.0.0.1:8081/probe",
                        interval_seconds=86400,
                        next_due_at=now_utc() + timedelta(days=1),
                    )
                    db.add(monitor)
                    db.flush()
                    if account == 0 and number == 0:
                        first_monitor = str(monitor.id)
        origin = str(settings.app_origin).rstrip("/")
        csrf = client.get("/api/v1/auth/csrf", headers={"Origin": origin})
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "benchmark-fixture-0@example.com", "password": password},
            headers={"Origin": origin, "X-CSRF-Token": csrf.json()["csrf_token"]},
        )
        if response.status_code != 200:
            raise ValueError("Fixture login failed.")
        del password, hashed
        paths = {
            "dashboard": "/api/v1/dashboard",
            "monitors": "/api/v1/monitors",
            "monitor_analytics": f"/api/v1/monitors/{first_monitor}/analytics",
            "monitor_checks": f"/api/v1/monitors/{first_monitor}/checks",
            "incidents": "/api/v1/incidents",
        }
        # Verify every route before timing; do not save bodies, tokens, or identifiers.
        if any(client.get(path).status_code != 200 for path in paths.values()):
            raise ValueError("Fixture API preflight failed.")
        samples, statuses = defaultdict(list), Counter()
        before = database_stats(engine)
        with engine.connect() as db:
            size_before = db.scalar(text("SELECT pg_database_size(current_database())"))
        thread = threading.Thread(target=measure_api, args=(client, paths, stop, samples, statuses))
        start = time.monotonic()
        thread.start()
        peak_connections = peak_active = peak_pending = 0
        for batch in range(rounds):
            with engine.begin() as db:
                # No past observations: only make the 100 disposable configurations due now.
                db.execute(text("UPDATE monitors SET next_due_at = clock_timestamp()"))
            for _ in range(4):  # Production dispatcher bounds each reservation to 25 monitors.
                dispatch_runs(engine, settings)
            round_deadline = time.monotonic() + 180
            while True:
                with engine.connect() as db:
                    completed, active, failed = db.execute(
                        text("""
                        SELECT count(*) FILTER (WHERE state = 'completed'),
                               count(*) FILTER (WHERE state IN ('pending', 'running')),
                               count(*) FILTER (WHERE
                                   state IN ('cancelled', 'infrastructure_failed')
                                   OR final_outcome IS NOT NULL AND final_outcome <> 'success')
                        FROM check_runs
                    """)
                    ).one()
                    connections, working = db.execute(
                        text("""
                        SELECT count(*), count(*) FILTER (WHERE state = 'active')
                        FROM pg_stat_activity WHERE datname = current_database()
                    """)
                    ).one()
                peak_connections = max(peak_connections, connections)
                peak_active = max(peak_active, working)
                peak_pending = max(peak_pending, active)
                if failed:
                    raise ValueError("Unexpected terminal probe outcome.")
                if completed == (batch + 1) * 100 and active == 0:
                    break
                if time.monotonic() > round_deadline or time.monotonic() - start > 2400:
                    raise ValueError("Workload exceeded bounded completion deadline.")
                time.sleep(0.25)
            if (batch + 1) % 10 == 0 or batch + 1 == rounds:
                print(json.dumps({"progress_completed_runs": completed}), flush=True)
        duration = time.monotonic() - start
        stop.set()
        thread.join(timeout=15)
        if thread.is_alive():
            raise ValueError("API sampler did not stop.")
        # Let PostgreSQL backend statistics flush; sampling uses a new transaction each time.
        time.sleep(2)
        after = database_stats(engine)
        with engine.connect() as db:
            checks, successes, monitors, attempts = db.execute(
                text("""
                SELECT count(*), count(*) FILTER (WHERE c.outcome = 'success'
                                                       AND c.http_status = 200),
                       count(DISTINCT r.monitor_id), max(r.attempt_count)
                FROM checks c JOIN check_runs r ON r.id = c.run_id
            """)
            ).one()
            lag = list(
                db.scalars(
                    text("""
                SELECT extract(epoch FROM (c.started_at - r.scheduled_at)) * 1000
                FROM checks c JOIN check_runs r ON r.id = c.run_id WHERE c.attempt_number = 1
            """)
                )
            )
            probe_times = list(db.scalars(text("SELECT duration_ms FROM checks")))
            size_after = db.scalar(text("SELECT pg_database_size(current_database())"))
            rows = {
                table: db.scalar(text(f"SELECT count(*) FROM {table}"))
                for table in ("users", "monitors", "check_runs", "checks", "incidents")
            }
            migration = db.scalar(text("SELECT version_num FROM alembic_version"))
            pg_version = db.scalar(text("SHOW server_version"))
            errors = dict(
                db.execute(
                    text("""
                SELECT coalesce(error_code, 'none'), count(*) FROM checks GROUP BY error_code
            """)
                )
                .tuples()
                .all()
            )
            # Fixed known query, no private predicates or parameters are saved.
            plan = db.scalar(
                text("""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                SELECT * FROM checks WHERE run_id IN (
                    SELECT id FROM check_runs ORDER BY scheduled_at DESC LIMIT 50)
            """)
            )
        with httpx.Client(trust_env=False) as fixture:
            counted = fixture.get("http://127.0.0.1:8081/stats").json()["completed_responses"]
        success = (
            checks == successes == counted == rounds * 100
            and monitors == 100
            and attempts == 1
            and set(statuses) == {"200"}
            and all(len(values) > 0 for values in samples.values())
        )
        report = {
            "schema_version": 1,
            "started_at": started_at,
            "finished_at": now_utc().isoformat(),
            "passed": success,
            "milestone_19_volume_met": success and checks >= 10000,
            "versions": {
                "python": platform.python_version(),
                "postgresql": pg_version,
                **{name: version(name) for name in ("celery", "redis", "sqlalchemy", "httpx")},
            },
            "settings": {
                "fixture_accounts": 10,
                "monitors": 100,
                "rounds": rounds,
                "probe_worker_concurrency": 2,
                "prefetch": 1,
                "fixture_delay_ms": 10,
                "fixture_body_bytes": 36,
                "stored_interval_seconds": 86400,
                "schedule": "accelerated due-now batches; production dispatcher and workers",
                "api_concurrency": 1,
                "api_pause_seconds": 0.25,
                "api_path": "HTTP through frontend same-origin proxy",
                "database_sample_interval_seconds": 0.25,
            },
            "duration_seconds": round(duration, 3),
            "completed_probes_per_second": round(checks / duration, 3),
            "real_http_completed_responses": counted,
            "completed_successful_http_checks": successes,
            "distinct_probed_monitors": monitors,
            "max_attempt_count": attempts,
            "probe_errors": errors,
            "api_status_counts": dict(statuses),
            "api_latency": {key: distribution(values) for key, values in samples.items()},
            "queue_lag": distribution([float(value) for value in lag]),
            "queue_lag_definition": (
                "first attempt started_at minus run scheduled_at; includes claim time"
            ),
            "probe_duration": distribution(probe_times),
            "database": {
                "migration": migration,
                "rows": rows,
                "size_before_bytes": size_before,
                "size_after_bytes": size_after,
                "statistics_delta": {key: after[key] - before[key] for key in before},
                "peak_connections_sampled": peak_connections,
                "peak_active_connections_sampled": peak_active,
                "peak_pending_or_running_sampled": peak_pending,
                "recent_checks_query_plan": plan,
            },
        }
        print(json.dumps({"report": report}), flush=True)
        return success
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=15)
        client.close()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=100, choices=range(1, 1001))
    args = parser.parse_args()
    try:
        passed = run(args.rounds)
    except Exception:
        print(json.dumps({"error": "Benchmark failed; private details suppressed."}), flush=True)
        raise SystemExit(1) from None
    raise SystemExit(0 if passed else 1)
