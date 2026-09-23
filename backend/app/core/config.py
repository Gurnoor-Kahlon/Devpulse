from pathlib import Path
from typing import Literal

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError


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
