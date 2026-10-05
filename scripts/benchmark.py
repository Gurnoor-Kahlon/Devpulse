"""Run a bounded real-HTTP benchmark in a fresh, disposable Compose project."""

import argparse
import hashlib
import json
import platform
import secrets
import subprocess
import sys
from pathlib import Path

from local_stack import DEFAULT_ENV, ROOT, Stack, StackError, initialize


def source_fingerprint():
    """Hash only reviewable source/build inputs, never environment files or runtime data."""
    paths = []
    for directory in ("backend/app", "backend/migrations", "backend/container", "containers"):
        paths.extend((ROOT / directory).rglob("*.py"))
    for name in (
        "compose.yaml",
        "compose.test.yaml",
        "compose.benchmark.yaml",
        "backend/Dockerfile",
        "frontend/Dockerfile",
        "containers/postgres/Dockerfile",
        "containers/redis/Dockerfile",
        "backend/requirements.lock",
        "backend/requirements-dev.lock",
        "backend/requirements-container.lock",
        "backend/requirements-container-build.lock",
        "frontend/package-lock.json",
        "scripts/benchmark.py",
        "scripts/local_stack.py",
    ):
        paths.append(ROOT / name)
    for path in (ROOT / "frontend/src").rglob("*"):
        if path.is_file() and path.suffix in {".ts", ".tsx", ".css"}:
            paths.append(path)
    hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(set(paths))
    }
    return {"algorithm": "sha256", "files": hashes}


def docker_metadata():
    # Never inspect full container configurations: they include interpolated credentials.
    template = (
        '{"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}},'
        '"engine":"{{.ServerVersion}}","os":"{{.OperatingSystem}}",'
        '"architecture":"{{.Architecture}}"}'
    )
    result = subprocess.run(
        ["docker", "info", "--format", template], capture_output=True, check=True, text=True
    )
    return json.loads(result.stdout)


def run(args):
    project = "devpulse-benchmark-" + secrets.token_hex(4)
    initialize(args.env_file)
    stack = Stack(project, args.env_file, test=True, ports=(args.web_port, args.mail_port))
    stack.prefix += ["-f", str(ROOT / "compose.benchmark.yaml")]
    destination = args.output or ROOT / ".cache" / project / "report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Do not overwrite evidence. Reserve the destination before creating any containers.
    with destination.open("x") as stream:
        stream.write("{}\n")
    report = {"passed": False, "milestone_19_volume_met": False}
    owned = False
    try:
        if stack.command("ps", "--all", "--quiet").strip():
            raise StackError("Refusing to reuse an existing project.")
        owned = True
        print(f"Starting disposable benchmark {project}", flush=True)
        stack.command("up", "--detach", "--wait", "--wait-timeout", "180")
        hardware = docker_metadata()
        hardware["client_system"] = platform.system()
        hardware["client_kernel"] = platform.release()
        images = {}
        for service in ("api", "frontend", "postgres", "redis", "mailpit"):
            container = stack.command("ps", "--quiet", service).strip()
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.Image}}", container],
                capture_output=True,
                text=True,
                check=True,
            )
            images[service] = result.stdout.strip()
        code = "import runpy; runpy.run_path('/benchmark/workload.py', run_name='__main__')"
        command = [
            *stack.prefix,
            "exec",
            "-T",
            "probe-worker",
            "python",
            "-c",
            code,
            "--rounds",
            str(args.rounds),
        ]
        with subprocess.Popen(
            command,
            cwd=ROOT,
            env=stack.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                # Only accept the harness protocol; never echo arbitrary container output.
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if "progress_completed_runs" in item:
                    print(
                        f"Completed {int(item['progress_completed_runs'])} real probes", flush=True
                    )
                if "report" in item:
                    report = item["report"]
            code = process.wait()
        report.update(hardware=hardware, images=images, source=source_fingerprint())
        report.setdefault("settings", {})["container_resource_limits"] = (
            "none; shared Docker engine budget"
        )
        if code or not report["passed"]:
            report["passed"] = False
            report["milestone_19_volume_met"] = False
            raise StackError("Benchmark did not satisfy correctness checks.")
        label = destination.relative_to(ROOT) if destination.is_relative_to(ROOT) else destination
        print(f"Sanitized evidence: {label}", flush=True)
        return report["passed"]
    finally:
        if owned:
            try:
                stack.command("down", "--volumes", "--remove-orphans", "--timeout", "30")
                report["disposable_project_removed"] = True
            except StackError:
                report["disposable_project_removed"] = False
                report["passed"] = False
                report["milestone_19_volume_met"] = False
                print(f"Cleanup failed for owned project {project}.", file=sys.stderr)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        if owned and not report.get("disposable_project_removed"):
            raise StackError("Disposable project cleanup failed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rounds",
        type=int,
        choices=range(1, 1001),
        default=100,
        metavar="1..1000",
        help="100 required for milestone 19; 1 for harness smoke",
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--web-port", type=int, default=23000)
    parser.add_argument("--mail-port", type=int, default=28025)
    args = parser.parse_args()
    try:
        if not run(args):
            raise StackError("Benchmark failed.")
    except (StackError, OSError, ValueError, KeyError, subprocess.SubprocessError):
        print(
            "Benchmark failed; inspect the sanitized report and local service status.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
