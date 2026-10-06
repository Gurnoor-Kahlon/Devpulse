"""Configure disposable monitors; never insert/update checks, runs or incidents."""

import json
import os
import sys
from uuid import UUID

from app.core.config import load_settings
from app.core.security import now_utc
from app.db.session import create_database_engine
from app.factory import create_app  # noqa: F401 -- register persisted models
from app.models.assertion import Assertion
from app.models.auth import User
from app.models.check import Check, CheckRun
from app.models.incident import Incident
from app.models.monitor import Monitor
from app.models.notification import NotificationDelivery
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

MONITORS = {
    "catalog": "Catalog API · healthy",
    "search": "Search API · slower response",
    "billing": "Billing API · controlled outage",
    "inventory": "Inventory API · JSON assertion",
    "checkout": "Checkout API · recovery scenario",
}


def main(action, owner):
    settings = load_settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        os.environ.get("DEVPULSE_SHOWCASE") != "1"
        or settings.environment != "test"
        or url.host != "postgres"
        or url.database != "devpulse_test"
    ):
        raise ValueError("A disposable Docker showcase database is required.")
    engine = create_database_engine(settings)
    try:
        with Session(engine) as db, db.begin():
            user = db.get(User, UUID(owner))
            if user is None or user.email != "portfolio@example.com" or not user.email_verified_at:
                raise ValueError("Verified synthetic showcase account required.")
            monitors = list(db.scalars(select(Monitor)))
            if action == "seed":
                if monitors or db.scalar(select(CheckRun.id)) is not None:
                    raise ValueError("Showcase requires an empty database.")
                for path, name in MONITORS.items():
                    monitor = Monitor(
                        user_id=user.id,
                        name=name,
                        url=f"http://127.0.0.1:8081/{path}",
                        interval_seconds=86400,
                        next_due_at=now_utc(),
                    )
                    db.add(monitor)
                    db.flush()
                    if path == "inventory":
                        db.add(
                            Assertion(
                                monitor_id=monitor.id,
                                position=0,
                                kind="json_equals",
                                pointer="/available",
                                expected=True,
                            )
                        )
                return {"seeded": len(MONITORS)}
            if len(monitors) != 5 or any(
                m.user_id != user.id or m.name not in MONITORS.values() for m in monitors
            ):
                raise ValueError("Only the five disposable showcase monitors are accepted.")
            if action == "due":
                if db.scalar(select(CheckRun.id).where(CheckRun.state.in_(["pending", "running"]))):
                    raise ValueError("Wait for current runs before scheduling the next round.")
                for monitor in monitors:
                    monitor.next_due_at = now_utc()
                return {"due": 5}
            if action != "snapshot":
                raise ValueError("Unknown showcase action.")
            runs = list(db.scalars(select(CheckRun).order_by(CheckRun.scheduled_at)))
            checks = list(db.scalars(select(Check).order_by(Check.started_at)))
            incidents = list(db.scalars(select(Incident).order_by(Incident.started_at)))
            deliveries = list(db.scalars(select(NotificationDelivery)))
            return {
                "monitors": {
                    m.url.rsplit("/", 1)[1]: {
                        "id": str(m.id),
                        "name": m.name,
                        "state": m.current_state,
                    }
                    for m in monitors
                },
                "runs": [
                    {
                        "id": str(r.id),
                        "monitor_id": str(r.monitor_id),
                        "trigger": r.trigger,
                        "state": r.state,
                        "outcome": r.final_outcome,
                        "attempts": r.attempt_count,
                        "scheduled_at": r.scheduled_at,
                        "completed_at": r.completed_at,
                    }
                    for r in runs
                ],
                "checks": [
                    {
                        "run_id": str(c.run_id),
                        "attempt": c.attempt_number,
                        "started_at": c.started_at,
                        "finished_at": c.finished_at,
                        "outcome": c.outcome,
                        "http_status": c.http_status,
                        "duration_ms": c.duration_ms,
                        "assertions": c.assertion_results,
                    }
                    for c in checks
                ],
                "incidents": [
                    {
                        "id": str(i.id),
                        "monitor_id": str(i.monitor_id),
                        "started_at": i.started_at,
                        "confirmed_at": i.confirmed_at,
                        "resolved_at": i.resolved_at,
                    }
                    for i in incidents
                ],
                "deliveries": [
                    {"transition": d.transition, "status": d.status, "attempts": d.attempt_count}
                    for d in deliveries
                ],
            }
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(main(*sys.argv[1:]), default=str))
    except Exception:
        raise SystemExit("Showcase control failed; private values were not logged.") from None
