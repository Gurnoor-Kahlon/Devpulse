"""Trusted disposable-test controls; never included in the runtime image or public API."""

import argparse
import hashlib
import json
from datetime import timedelta
from uuid import UUID

from app.core.config import load_settings
from app.core.security import now_utc
from app.db.base import Base
from app.db.session import create_database_engine
from app.factory import create_app  # noqa: F401 -- registers all persisted models
from app.models.auth import User
from app.models.check import CheckRun
from app.models.monitor import Monitor
from app.monitoring.runs import create_pending_run
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "due", "pending", "run", "snapshot"))
    parser.add_argument("identifier", nargs="?")
    parser.add_argument("--database")
    args = parser.parse_args()
    settings = load_settings()
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment != "test" or url.database != "devpulse_test":
        raise ValueError("Controls require the disposable container test database.")
    if args.database:
        import re

        from pydantic import SecretStr

        if not re.fullmatch(r"devpulse_restore_[a-z0-9]+_test", args.database):
            raise ValueError("Only isolated restore-test database names are accepted.")
        settings = settings.model_copy(
            update={
                "database_url": SecretStr(
                    url.set(database=args.database).render_as_string(hide_password=False)
                )
            }
        )
    engine = create_database_engine(settings)
    try:
        if args.action == "snapshot":
            result = {}
            with engine.connect() as db:
                for table in Base.metadata.sorted_tables:
                    rows = [
                        dict(row)
                        for row in db.execute(
                            select(table).order_by(*table.primary_key.columns)
                        ).mappings()
                    ]
                    result[table.name] = {
                        "rows": len(rows),
                        "sha256": hashlib.sha256(
                            json.dumps(rows, default=str, sort_keys=True).encode()
                        ).hexdigest(),
                    }
                result["migration"] = db.scalar(text("SELECT version_num FROM alembic_version"))
            return result
        identifier = UUID(args.identifier)
        if args.action == "pending":
            return {"run_id": str(create_pending_run(engine, identifier))}
        with Session(engine) as db, db.begin():
            if args.action == "seed":
                user = db.get(User, identifier)
                if user is None or user.email_verified_at is None:
                    raise ValueError("A verified fixture account is required.")
                if db.scalar(select(Monitor.id)) is not None:
                    raise ValueError("Fixture seeding requires an empty test workspace.")
                monitor = Monitor(
                    user_id=identifier,
                    name="Controlled container fixture",
                    url="http://127.0.0.1:8081/controlled",
                    interval_seconds=86400,
                    next_due_at=now_utc(),
                )
                db.add(monitor)
                db.flush()
                return {"monitor_id": str(monitor.id)}
            if args.action == "due":
                monitor = db.get(Monitor, identifier)
                if monitor is None or monitor.name != "Controlled container fixture":
                    raise ValueError("Only the disposable fixture may be made due.")
                monitor.next_due_at = now_utc() - timedelta(seconds=1)
                return {"due": True}
            run = db.get(CheckRun, identifier)
            return {"state": run.state, "outcome": run.final_outcome} if run else {"state": None}
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(main()))
    except Exception:
        raise SystemExit(
            "Disposable fixture operation failed; no private values were logged."
        ) from None
