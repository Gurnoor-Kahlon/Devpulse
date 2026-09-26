from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import load_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import create_database_engine
from app.models import (
    auth,  # noqa: F401 -- register model metadata for autogeneration
    check,  # noqa: F401 -- register probe metadata
    incident,  # noqa: F401 -- register retained incident metadata
    monitor,  # noqa: F401 -- register model metadata for autogeneration
)


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    if context.is_offline_mode():
        context.configure(
            url=settings.database_url.get_secret_value(),
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    elif (connection := context.config.attributes.get("connection")) is not None:
        migrate(connection)
    else:
        engine = create_database_engine(settings)
        try:
            with engine.connect() as connection:
                migrate(connection)
        finally:
            engine.dispose()


try:
    run()
except SQLAlchemyError:
    raise SystemExit(
        "Database migration failed. Check connectivity and migration definitions."
    ) from None
