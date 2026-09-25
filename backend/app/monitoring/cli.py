import argparse
import json
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, load_settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine
from app.monitoring.runs import RunError, run_monitor


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded probe for an enabled saved monitor."
    )
    parser.add_argument("monitor_id", type=UUID, help="Saved monitor UUID; URLs are not accepted.")
    args = parser.parse_args()
    try:
        settings = load_settings()
        configure_logging(settings.log_level)
        engine = create_database_engine(settings)
        try:
            run_id, check_id, result = run_monitor(engine, settings, args.monitor_id)
        finally:
            engine.dispose()
        print(
            json.dumps(
                {
                    "run_id": str(run_id),
                    "check_id": str(check_id) if check_id else None,
                    "outcome": result.outcome,
                    "http_status": result.http_status,
                    "duration_ms": result.duration_ms,
                    "error_code": result.error_code,
                }
            )
        )
        return 0 if result.outcome == "success" else 1
    except (ConfigurationError, RunError) as exc:
        print(str(exc))
        return 2
    except SQLAlchemyError:
        print("Probe persistence is unavailable. Inspect the saved run before retrying.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
