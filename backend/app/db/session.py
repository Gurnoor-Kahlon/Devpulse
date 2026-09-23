from collections.abc import Iterator
from typing import cast

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    """Create a lazy, process-local pool; construction does not connect."""
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=3,
        hide_parameters=True,
        echo=False,
        connect_args={
            "connect_timeout": 3,
            "options": "-c timezone=UTC -c statement_timeout=5000 -c lock_timeout=3000",
        },
    )


def get_session(request: Request) -> Iterator[Session]:
    """Close and roll back unfinished work; services explicitly own commits."""
    factory = cast(sessionmaker[Session], request.app.state.session_factory)
    with factory() as session:
        yield session


def database_is_ready(request: Request) -> bool:
    if not request.app.state.ready:
        return False
    engine = cast(Engine, request.app.state.engine)
    try:
        with engine.connect() as connection:
            return bool(connection.scalar(text("SELECT 1")) == 1)
    except SQLAlchemyError:
        # Driver exceptions can contain hostnames, SQL, and credentials.
        return False
