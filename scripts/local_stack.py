"""Local Compose initialization and safe PostgreSQL backup/restore. No host installs."""

import argparse
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV = ROOT / ".cache/compose.env"


class StackError(Exception):
    pass


def initialize(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print("Existing container environment retained; no values printed.")
        return
    with path.open("x") as stream:
        stream.write("DEVPULSE_LOCAL_DB_PASSWORD=" + secrets.token_hex(24) + "\n")
    print("Created project-local container environment; no values printed.")


class Stack:
    def __init__(self, project="devpulse", env_file=DEFAULT_ENV, test=False, ports=None):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,60}", project):
            raise StackError("Invalid Compose project name.")
        self.project = project
        self.env = dict(os.environ)
        if ports:
            self.env.update(DEVPULSE_WEB_PORT=str(ports[0]), DEVPULSE_MAIL_PORT=str(ports[1]))
        self.prefix = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "--project-name",
            project,
            "-f",
            str(ROOT / "compose.yaml"),
        ]
        if test:
            self.prefix += ["-f", str(ROOT / "compose.test.yaml")]

    def command(self, *args, input=None, stdout=None):
        result = subprocess.run(
            [*self.prefix, *args],
            check=False,
            cwd=ROOT,
            env=self.env,
            input=input,
            stdout=stdout if stdout is not None else subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            # Compose errors/config can contain interpolated credentials; do not echo them.
            raise StackError(
                f"Compose {args[0]} failed (exit {result.returncode}). Inspect service status."
            )
        return result.stdout.decode() if stdout is None else None

    def sql(self, database, statement):
        return self.command(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "devpulse",
            "-d",
            database,
            "-At",
            "-c",
            statement,
        ).strip()


def database_name(value):
    if not re.fullmatch(r"devpulse(?:_[a-z0-9]+)*", value):
        raise StackError("Only DevPulse database names are accepted.")
    return value


def backup(stack, database, destination):
    database_name(database)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents overwriting an earlier backup.
    with destination.open("xb") as stream:
        try:
            stack.command(
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "devpulse",
                "-d",
                database,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                stdout=stream,
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    print("PostgreSQL backup written successfully.")


def restore(stack, source, database):
    if not re.fullmatch(r"devpulse_restore_[a-z0-9]+_test", database):
        raise StackError("Restore requires a NEW devpulse_restore_<name>_test database.")
    if stack.sql("postgres", f"SELECT 1 FROM pg_database WHERE datname = '{database}'"):
        raise StackError("Restore target already exists; refusing to overwrite it.")
    # Read before creating the target; never remove or overwrite any existing database.
    # Unbuffered: the child must see byte zero after header validation/seek.
    with source.open("rb", buffering=0) as stream:
        header = stream.read(5)
        if header != b"PGDMP":
            raise StackError("Expected a PostgreSQL custom-format backup.")
        stream.seek(0)
        stack.sql("postgres", f'CREATE DATABASE "{database}" OWNER devpulse')
        result = subprocess.run(
            [
                *stack.prefix,
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                "devpulse",
                "-d",
                database,
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
            ],
            cwd=ROOT,
            env=stack.env,
            stdin=stream,
            capture_output=True,
            check=False,
        )
    if result.returncode:
        raise StackError("Restore failed; the isolated target is retained for inspection.")
    print("Backup restored into a new isolated database.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--project", default="devpulse")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    b = commands.add_parser("backup")
    b.add_argument("file", type=Path)
    b.add_argument("--database", default="devpulse")
    r = commands.add_parser("restore")
    r.add_argument("file", type=Path)
    r.add_argument("--database", required=True)
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.env_file)
        return
    stack = Stack(args.project, args.env_file)
    if args.command == "backup":
        backup(stack, args.database, args.file)
    else:
        restore(stack, args.file, args.database)


if __name__ == "__main__":
    try:
        main()
    except (StackError, OSError, ValueError):
        print(
            "Local stack operation failed. Check file paths, service status, and target names.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
