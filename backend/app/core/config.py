from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator, model_validator
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
    app_origin: str = "http://localhost:3000"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_mode: Literal["plain", "starttls", "tls"] = "plain"
    smtp_username: SecretStr | None = None
    smtp_password: SecretStr | None = None
    mail_from: EmailStr = "devpulse@localhost.localdomain"

    @field_validator("app_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.path not in {"", "/"}
            or parts.query
            or parts.fragment
            or parts.port == 0
        ):
            raise ValueError("Use an HTTP(S) origin without credentials, path, query, or fragment.")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_mail_security(self) -> "Settings":
        if bool(self.smtp_username) != bool(self.smtp_password):
            raise ValueError("SMTP username and password must be configured together.")
        if self.smtp_mode == "plain" and self.smtp_username:
            raise ValueError("SMTP authentication requires TLS.")
        if self.environment == "production" and (
            not self.app_origin.startswith("https://") or self.smtp_mode == "plain"
        ):
            raise ValueError("Production requires an HTTPS origin and TLS SMTP.")
        return self

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
