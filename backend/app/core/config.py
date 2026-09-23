from pathlib import Path
from typing import Literal

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DEVPULSE_",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_docs_enabled: bool = True
    database_url: SecretStr = SecretStr("postgresql+psycopg://devpulse@127.0.0.1:5432/devpulse")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
            valid = (
                url.drivername == "postgresql+psycopg"
                and bool(url.host and url.database and url.username)
                and (url.port is None or 1 <= url.port <= 65535)
            )
        except (ArgumentError, ValueError):
            valid = False
        if not valid:
            raise ValueError("Use a PostgreSQL psycopg URL with host, database, and username.")
        return value


class ConfigurationError(ValueError):
    """Startup configuration is invalid; the message never includes supplied values."""


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        fields = sorted(
            {
                str(error["loc"][0])
                for error in exc.errors()
                if error["loc"] and error["loc"][0] in Settings.model_fields
            }
        )
        suffix = (
            f" Check: {', '.join(fields)}." if fields else " Check backend environment settings."
        )
        raise ConfigurationError(f"Invalid backend configuration.{suffix}") from None
    except SettingsError:
        raise ConfigurationError("Unable to parse backend environment settings.") from None
