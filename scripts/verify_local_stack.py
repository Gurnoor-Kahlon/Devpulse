"""Real Compose smoke/restart/backup-restore test, isolated from all existing projects."""

import argparse
import hashlib
import json
import re
import secrets
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from local_stack import DEFAULT_ENV, ROOT, Stack, StackError, backup, initialize, restore


def require(value, message):
    if not value:
        raise StackError(message)


def eventually(predicate, message, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (httpx.HTTPError, StackError):
            pass
        time.sleep(1)
    raise StackError(message)


def control(stack, action, *args):
    # -c runs in /app so the runtime package is available to the mounted fixture script.
    code = "import runpy; runpy.run_path('/fixtures/control.py', run_name='__main__')"
    output = stack.command("run", "--rm", "--no-deps", "api", "python", "-c", code, action, *args)
    return json.loads(output)


def run(args):
    suffix = secrets.token_hex(4)
    project = f"devpulse-smoke-{suffix}"
    initialize(args.env_file)
    stack = Stack(project, args.env_file, test=True, ports=(args.web_port, args.mail_port))
    artifact = ROOT / ".cache" / project
    artifact.mkdir(parents=True)
    report = {"project": project, "started_at": datetime.now(UTC).isoformat(), "checks": []}
    print(f"Validating isolated project {project}", flush=True)
    require(not stack.command("ps", "--all", "--quiet").strip(), "Test project already exists.")

    def passed(name):
        report["checks"].append(name)
        print(f"PASS: {name}", flush=True)

    def fixture_status(status):
        code = (
            "from urllib.request import Request,urlopen; "
            f"urlopen(Request('http://127.0.0.1:8081/control/{status}',method='POST'),timeout=3)"
        )
        stack.command("exec", "-T", "probe-worker", "python", "-c", code)

    try:
        stack.command("up", "--detach", "--wait", "--wait-timeout", "180")
        require(
            stack.sql("devpulse_test", "SELECT version_num FROM alembic_version") == "f16b4d8e302a",
            "Migration head differs from the milestone 18 baseline.",
        )
        stack.command("run", "--rm", "--no-deps", "migrate", "python", "-m", "alembic", "check")
        passed("fresh volume startup, readiness, migration head and schema drift")
        for service in ("api", "probe-worker", "maintenance-worker", "beat"):
            uid = stack.command(
                "exec", "-T", service, "python", "-c", "import os; print(os.getuid())"
            )
            require(
                uid.strip() == "10001",
                "Application service is not running as the expected non-root user.",
            )
        require(
            stack.command(
                "exec", "-T", "frontend", "node", "-e", "console.log(process.getuid())"
            ).strip()
            == "10001",
            "Frontend must run as non-root.",
        )
        require(
            len(stack.command("ps", "--quiet", "beat").splitlines()) == 1,
            "Exactly one Beat is required.",
        )
        config = json.loads(stack.command("config", "--format", "json"))
        for service in (
            "postgres",
            "redis",
            "api",
            "probe-worker",
            "maintenance-worker",
            "beat",
            "fixtures",
        ):
            require(
                not config["services"][service].get("ports"),
                "Private service has a published host port.",
            )
        for service in ("frontend", "mailpit"):
            require(
                all(p["host_ip"] == "127.0.0.1" for p in config["services"][service]["ports"]),
                "A user interface is exposed beyond loopback.",
            )
        passed("non-root application services, single Beat and loopback-only host ports")

        origin = f"http://localhost:{args.web_port}"
        with (
            httpx.Client(base_url=origin, timeout=15, trust_env=False) as client,
            httpx.Client(
                base_url=f"http://127.0.0.1:{args.mail_port}", timeout=10, trust_env=False
            ) as mail,
        ):
            require(client.get("/").status_code == 200, "Landing page unavailable.")
            require(
                client.get("/screenshots/demo-desktop.png").status_code == 200,
                "Screenshot missing from runtime.",
            )
            require(
                client.get("/api/v1/monitors").status_code == 401,
                "Private API is accessible anonymously.",
            )
            require(
                client.get("/api/v1/demo").json()["monitors"] == [],
                "Default publication must be empty.",
            )

            def write(path, data, method="POST"):
                token = client.get("/api/v1/auth/csrf", headers={"Origin": origin}).json()[
                    "csrf_token"
                ]
                response = client.request(
                    method, path, json=data, headers={"Origin": origin, "X-CSRF-Token": token}
                )
                require(response.is_success, "Authenticated fixture API request failed.")
                return response

            email = f"container-{suffix}@example.com"
            password = secrets.token_urlsafe(24)
            write("/api/v1/auth/register", {"email": email, "password": password})

            def email_code():
                for message in mail.get("/api/v1/messages").json().get("messages", []):
                    if any(to["Address"] == email for to in message["To"]):
                        detail = mail.get(f"/api/v1/message/{message['ID']}").json()
                        found = re.search(r"[A-Za-z0-9_-]{43}", detail["Text"])
                        if found:
                            return found.group()
                return None

            token = eventually(email_code, "Verification email was not received.")
            write("/api/v1/auth/verify-email", {"token": token})
            write("/api/v1/auth/login", {"email": email, "password": password})
            owner = client.get("/api/v1/auth/me").json()
            require(owner["email_verified_at"], "Email verification did not persist.")
            preferences = client.get("/api/v1/notifications/preferences").json()
            write(
                "/api/v1/notifications/preferences",
                {
                    "configuration_version": preferences["configuration_version"],
                    "enabled": True,
                    "on_open": True,
                    "on_recovery": True,
                },
                "PUT",
            )
            passed("same-origin proxy, private API denial, signup and real SMTP verification")
            mid = control(stack, "seed", owner["id"])["monitor_id"]

            def monitor():
                response = client.get(f"/api/v1/monitors/{mid}")
                require(response.is_success, "Fixture monitor is unavailable.")
                return response.json()

            eventually(
                lambda: monitor()["current_state"] == "operational",
                "Beat did not schedule a successful real probe.",
            )
            fixture_status(503)
            control(stack, "due", mid)
            eventually(
                lambda: monitor()["current_state"] == "down",
                "Real failures did not confirm an incident.",
            )
            fixture_status(200)
            control(stack, "due", mid)
            eventually(
                lambda: monitor()["current_state"] == "operational",
                "Real recovery did not resolve the incident.",
            )

            def delivered():
                rows = client.get("/api/v1/notifications/deliveries").json()["items"]
                return len(rows) == 2 and all(row["status"] == "sent" for row in rows)

            eventually(delivered, "Incident emails were not accepted by local SMTP.")
            metrics = client.get(f"/api/v1/monitors/{mid}/analytics").json()["metrics"]
            require(
                metrics["observations"] == 3 and metrics["failed_runs"] == 1,
                "Controlled run metrics do not match the actual three-run lifecycle.",
            )
            report["controlled_observations"] = metrics["observations"]
            report["controlled_failed_runs"] = metrics["failed_runs"]
            passed(
                "Beat to real Redis/prefork probes, durable retries, "
                "incident recovery and email delivery"
            )

            stack.command("stop", "fixtures", "probe-worker")
            pending = control(stack, "pending", mid)["run_id"]
            require(
                control(stack, "run", pending)["state"] == "pending",
                "Pending work was not durable.",
            )
            stack.command("start", "probe-worker", "fixtures")
            eventually(
                lambda: control(stack, "run", pending)["state"] == "completed",
                "Worker restart did not recover pending work.",
            )
            passed("pending run persists while probe worker is stopped and completes after restart")

            stack.command("stop", "redis")
            pending = control(stack, "pending", mid)["run_id"]
            require(
                control(stack, "run", pending)["state"] == "pending",
                "Broker outage lost durable work.",
            )
            stack.command("start", "redis")
            eventually(
                lambda: control(stack, "run", pending)["state"] == "completed",
                "Broker recovery did not reconcile pending work.",
            )
            passed("Redis outage and reconnect reconcile PostgreSQL pending work")

            stack.command("stop", "postgres")
            code = (
                "import httpx; "
                "print(httpx.get('http://127.0.0.1:8000/health/ready').status_code); "
                "print(httpx.get('http://127.0.0.1:8000/health/live').status_code)"
            )
            require(
                stack.command("exec", "-T", "api", "python", "-c", code).split() == ["503", "200"],
                "Readiness must fail while liveness survives database loss.",
            )
            stack.command("start", "postgres")
            eventually(
                lambda: client.get("/api/v1/auth/me").status_code == 200,
                "API did not reconnect to PostgreSQL.",
            )
            passed("database outage reports not-ready without losing API liveness and reconnects")

        # Stop all writers before comparing complete row fingerprints and taking the backup.
        stack.command(
            "stop", "beat", "fixtures", "probe-worker", "maintenance-worker", "frontend", "api"
        )
        before = control(stack, "snapshot")
        stack.command(
            "exec", "-T", "redis", "redis-cli", "SET", "devpulse:smoke:persistence", suffix
        )
        archive = artifact / "devpulse_test.dump"
        backup(stack, "devpulse_test", archive)
        restored_db = f"devpulse_restore_{suffix}_test"
        restore(stack, archive, restored_db)
        require(
            control(stack, "snapshot", "--database", restored_db) == before,
            "Restored rows differ from the source snapshot.",
        )
        try:
            restore(stack, archive, restored_db)
        except StackError:
            pass
        else:
            raise StackError("Restore overwrote an existing database.")
        passed(
            "Backup restores all row fingerprints and migration; "
            "existing restore target is rejected"
        )
        stack.command("down", "--timeout", "60")
        stack.command("up", "--detach", "--wait", "--wait-timeout", "90", "postgres", "redis")
        require(
            control(stack, "snapshot") == before,
            "Named PostgreSQL volume did not preserve all rows.",
        )
        marker = stack.command(
            "exec", "-T", "redis", "redis-cli", "GET", "devpulse:smoke:persistence"
        ).strip()
        require(marker == suffix, "Redis AOF volume did not survive container recreation.")
        passed("Full container recreation preserves PostgreSQL rows and Redis AOF")
        stack.command("up", "--detach", "--wait", "--wait-timeout", "180")
        with httpx.Client(base_url=origin, timeout=15, trust_env=False) as client:
            require(
                client.get("/api/v1/demo").status_code == 200,
                "Recreated frontend/API proxy failed.",
            )
        passed("complete stack restarts against retained data with idempotent migrations")
        report["snapshot"] = before
        report["backup_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        report["status"] = "passed"
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        (artifact / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if args.keep:
            print(
                f"Retained test project {project}; "
                f"isolated test ports {args.web_port}/{args.mail_port}.",
                flush=True,
            )
        else:
            # This unique project was created here and contains only disposable test data.
            stack.command("down", "--volumes", "--timeout", "60")
    print(f"Evidence: {artifact.relative_to(ROOT)}/report.json", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--web-port", type=int, default=13000)
    parser.add_argument("--mail-port", type=int, default=18025)
    parser.add_argument(
        "--keep", action="store_true", help="Keep the disposable stack for inspection."
    )
    args = parser.parse_args()
    require(
        1024 <= args.web_port <= 65535 and 1024 <= args.mail_port <= 65535,
        "Choose unprivileged local ports.",
    )
    run(args)


if __name__ == "__main__":
    try:
        main()
    except (
        StackError,
        httpx.HTTPError,
        OSError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        # Never print HTTP bodies, credentials, response headers, tokens, or raw subprocess output.
        message = str(exc) if isinstance(exc, StackError) else type(exc).__name__
        print(f"Container validation failed: {message}", flush=True)
        raise SystemExit(1) from None
