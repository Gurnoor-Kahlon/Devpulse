"""Container process/dependency checks; actual job execution is verified by smoke tests."""

import os
import sys
from pathlib import Path
from urllib.request import urlopen

from redis import Redis
from sqlalchemy import text

from app.core.config import load_settings
from app.db.session import create_database_engine


def main() -> int:
    try:
        role = sys.argv[1]
        if role == "api":
            with urlopen("http://127.0.0.1:8000/health/ready", timeout=4) as response:
                return 0 if response.status == 200 else 1
        pid = int(Path(f"/tmp/{role}.pid").read_text())
        os.kill(pid, 0)
        settings = load_settings()
        with Redis.from_url(
            settings.broker_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
        ) as broker:
            if not broker.ping():
                return 1
        engine = create_database_engine(settings)
        try:
            with engine.connect() as connection:
                return 0 if connection.scalar(text("SELECT 1")) == 1 else 1
        finally:
            engine.dispose()
    except Exception:
        print("Container process or dependency is unavailable.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
