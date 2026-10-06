"""Capture a real Docker/Beat/worker showcase using existing local runtime images."""

import argparse
import hashlib
import json
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from local_stack import DEFAULT_ENV, ROOT, Stack, StackError, initialize
from verify_local_stack import eventually, require


def run(args):
    project = f"devpulse-showcase-{secrets.token_hex(4)}"
    initialize(args.env_file)
    stack = Stack(project, args.env_file, test=True, ports=(args.web_port, args.mail_port))
    stack.prefix += ["-f", str(ROOT / "compose.showcase.yaml")]
    stack.env["BUILDX_GIT_INFO"] = "false"
    require(not stack.command("ps", "--all", "--quiet").strip(), "Project must be new.")
    artifact = ROOT / ".cache" / project
    artifact.mkdir()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "project": project,
        "pipeline": "Beat → Redis → maintenance dispatcher → Redis → prefork probes → PostgreSQL",
        "configuration_only_seed": True,
        "history_timestamps_modified": False,
        "runtime_images_rebuilt": False,
        "rounds": [],
    }
    origin = f"http://localhost:{args.web_port}"
    email, password = "portfolio@example.com", secrets.token_urlsafe(24)

    def control(action, owner):
        code = "import runpy; runpy.run_path('/showcase/control.py', run_name='__main__')"
        return json.loads(stack.command("exec", "-T", "api", "python", "-c", code, action, owner))

    def phase(value):
        code = (
            "from urllib.request import Request,urlopen; "
            f"urlopen(Request('http://127.0.0.1:8081/control/{value}',method='POST'),timeout=3)"
        )
        stack.command("exec", "-T", "probe-worker", "python", "-c", code)

    def capture(snapshot, stage):
        payload = {
            "origin": origin,
            "email": email,
            "password": password,
            "snapshot": snapshot,
            "stage": stage,
            "output": str(output),
        }
        result = subprocess.run(
            ["node", str(ROOT / "scripts/capture_showcase.mjs")],
            input=json.dumps(payload).encode(),
            cwd=ROOT,
            env=stack.env,
            capture_output=True,
            check=False,
        )
        require(result.returncode == 0, "Browser capture failed; credentials were not logged.")
        report.setdefault("captures", []).extend(json.loads(result.stdout))

    try:
        print(f"Starting {project} with existing images; no builds.", flush=True)
        stack.command(
            "up", "--no-build", "--pull", "never", "--detach", "--wait", "--wait-timeout", "180"
        )
        report["migration"] = stack.sql("devpulse_test", "SELECT version_num FROM alembic_version")
        require(report["migration"] == "f16b4d8e302a", "Unexpected migration head.")
        stack.command("run", "--rm", "--no-deps", "migrate", "python", "-m", "alembic", "check")
        report["images"] = {}
        for service in ("api", "frontend", "postgres", "redis"):
            cid = stack.command("ps", "--quiet", service).strip()
            report["images"][service] = subprocess.check_output(
                ["docker", "inspect", "--format", "{{.Image}}", cid], text=True
            ).strip()
        with (
            httpx.Client(base_url=origin, timeout=20, trust_env=False) as client,
            httpx.Client(
                base_url=f"http://127.0.0.1:{args.mail_port}", timeout=10, trust_env=False
            ) as mail,
        ):

            def write(path, data, method="POST"):
                csrf = client.get("/api/v1/auth/csrf", headers={"Origin": origin}).json()[
                    "csrf_token"
                ]
                response = client.request(
                    method, path, json=data, headers={"Origin": origin, "X-CSRF-Token": csrf}
                )
                require(response.is_success, "Showcase account API request failed.")
                return response

            write("/api/v1/auth/register", {"email": email, "password": password})

            def verification():
                for message in mail.get("/api/v1/messages").json().get("messages", []):
                    if any(to["Address"] == email for to in message["To"]):
                        body = mail.get(f"/api/v1/message/{message['ID']}").json()["Text"]
                        token = re.search(r"[A-Za-z0-9_-]{43}", body)
                        if token:
                            return token.group()
                return None

            write(
                "/api/v1/auth/verify-email",
                {"token": eventually(verification, "No verification email.")},
            )
            write("/api/v1/auth/login", {"email": email, "password": password})
            owner = client.get("/api/v1/auth/me").json()["id"]
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
            control("seed", owner)

            def completed(expected):
                snapshot = control("snapshot", owner)
                if len(snapshot["runs"]) == expected and all(
                    r["state"] == "completed" and r["trigger"] == "scheduled"
                    for r in snapshot["runs"]
                ):
                    return snapshot
                return None

            def wait_round(number, label):
                snapshot = eventually(
                    lambda: completed(number * 5),
                    "Beat/worker round did not complete.",
                    timeout=180,
                )
                report["rounds"].append(
                    {"round": number, "phase": label, "completed_at": datetime.now(UTC).isoformat()}
                )
                print(
                    f"Round {number}: {label}; {len(snapshot['runs'])} real scheduled runs.",
                    flush=True,
                )
                return snapshot

            # Normal retry clocks are untouched. Only the next due configuration is accelerated.
            for number in range(1, 5):
                if number > 1:
                    control("due", owner)
                wait_round(number, "healthy baseline")
            phase("incident")
            control("due", owner)
            snapshot = wait_round(5, "HTTP 503 and HTTP 200 assertion failures")
            require(len(snapshot["incidents"]) == 3, "Expected three real confirmed incidents.")
            capture(snapshot, "incident")
            phase("recovery")
            for number in (6, 7):
                control("due", owner)
                snapshot = wait_round(number, "checkout recovered; billing/inventory remain down")

            def delivered():
                current = control("snapshot", owner)
                if len(current["deliveries"]) == 4 and all(
                    d["status"] == "sent" for d in current["deliveries"]
                ):
                    return current
                return None

            snapshot = eventually(delivered, "Expected three open and one recovery email.")
            require(
                sum(i["resolved_at"] is not None for i in snapshot["incidents"]) == 1,
                "Checkout recovery was not persisted.",
            )
            require(len(snapshot["checks"]) == 49, "Unexpected real attempt count.")
            require(
                sum(r["outcome"] == "success" for r in snapshot["runs"]) == 28,
                "Unexpected scheduled outcome count.",
            )
            report["snapshot"] = snapshot
            report["dashboard"] = client.get("/api/v1/dashboard").json()
            capture(snapshot, "recovery")
            report["status"] = "passed"
            if args.keep:
                # Sensitive local access only; .cache is excluded from public artifacts.
                (artifact / "access.json").write_text(
                    json.dumps({"origin": origin, "email": email, "password": password}, indent=2)
                    + "\n"
                )
    finally:
        report["finished_at"] = datetime.now(UTC).isoformat()
        if args.keep:
            print(f"Retained {project}; access details in .cache/{project}/access.json", flush=True)
        else:
            stack.command("down", "--volumes", "--timeout", "60")
            report["disposable_stack_removed"] = True
        for item in report.get("captures", []):
            item["sha256"] = hashlib.sha256((output / item["file"]).read_bytes()).hexdigest()
        (artifact / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if report.get("status") == "passed":
            (output / "showcase-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Evidence: .cache/{project}/report.json", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--output", type=Path, default=ROOT / ".cache/showcase-output")
    parser.add_argument("--web-port", type=int, default=13000)
    parser.add_argument("--mail-port", type=int, default=18025)
    parser.add_argument("--keep", action="store_true", help="Retain this disposable local stack.")
    args = parser.parse_args()
    require(
        1024 <= args.web_port <= 65535
        and 1024 <= args.mail_port <= 65535
        and args.web_port != args.mail_port,
        "Choose distinct unprivileged ports.",
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
        print(f"Showcase failed: {str(exc) if isinstance(exc, StackError) else type(exc).__name__}")
        raise SystemExit(1) from None
