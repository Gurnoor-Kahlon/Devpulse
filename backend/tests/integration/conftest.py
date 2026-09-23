import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import Settings
from app.db.session import create_database_engine


@pytest.fixture(scope="session")
def database_settings() -> Settings:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.fail("Set TEST_DATABASE_URL to a dedicated PostgreSQL database ending in _test.")
    try:
        settings = Settings(environment="test", database_url=SecretStr(value), _env_file=None)
    except ValueError:
        pytest.fail("TEST_DATABASE_URL must be a valid PostgreSQL psycopg URL.", pytrace=False)
    from sqlalchemy.engine import make_url

    if not (make_url(value).database or "").endswith("_test"):
        pytest.fail("Integration databases must end in _test; development databases are rejected.")
    return settings


@pytest.fixture
def database_engine(database_settings: Settings) -> Iterator[Engine]:
    """Only a newly created random schema is ever dropped; the database is retained."""
    admin = create_database_engine(database_settings)
    schema = f"test_{uuid4().hex}"
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
    except SQLAlchemyError:
        admin.dispose()
        pytest.fail("Cannot create isolated schema in TEST_DATABASE_URL.", pytrace=False)
    engine = create_engine(
        database_settings.database_url.get_secret_value(),
        hide_parameters=True,
        connect_args={
            "connect_timeout": 3,
            "options": f"-c search_path={schema} -c timezone=UTC -c statement_timeout=5000",
        },
    )
    try:
        yield engine
    finally:
        engine.dispose()
        try:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        finally:
            admin.dispose()


@pytest.fixture
def database_session(database_engine: Engine) -> Iterator[Session]:
    with database_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with Session(connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()
