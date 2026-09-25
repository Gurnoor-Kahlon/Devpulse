import argparse
import json
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine
from app.jobs.publisher import publish_run
from app.monitoring.runs import RunError, create_pending_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Queue a saved monitor or republish a durable run."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("enqueue", help="Create and publish one manual run").add_argument(
        "id", type=UUID
    )
    commands.add_parser(
        "publish", help="Republish the same run after a failure or lost message"
    ).add_argument("id", type=UUID)
    args = parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        engine = create_database_engine(settings)
        try:
            run_id = create_pending_run(engine, args.id) if args.command == "enqueue" else args.id
            # Emit durable identity before publication so interruption cannot hide how to recover.
            print(json.dumps({"run_id": str(run_id)}), flush=True)
            published = publish_run(engine, settings, run_id)
            print(json.dumps({"run_id": str(run_id), "published": published}))
            return 0 if published else 1
        finally:
            engine.dispose()
    except (ConfigurationError, RunError) as exc:
        print(str(exc))
        return 2
    except SQLAlchemyError:
        print("Job persistence is unavailable. Inspect existing runs before retrying.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
