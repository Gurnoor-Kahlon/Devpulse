from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.api.health import router as health_router
from app.core.config import Settings, load_settings
from app.core.errors import ErrorResponse, http_exception_handler, validation_exception_handler
from app.core.logging import configure_logging, logger
from app.core.middleware import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else load_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        application.state.ready = True
        logger.info(
            "application_started",
            extra={"event": "application_started", "environment": settings.environment},
        )
        try:
            yield
        finally:
            application.state.ready = False
            logger.info("application_stopped", extra={"event": "application_stopped"})

    expose_docs = settings.api_docs_enabled and settings.environment != "production"
    application = FastAPI(
        title="DevPulse",
        description=(
            "Reliability at a glance. Every HTTP response includes a server-generated "
            "X-Request-ID. Errors use a consistent error object and matching request_id. "
            "Only process health is implemented at this stage."
        ),
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if expose_docs else None,
        responses={
            422: {"model": ErrorResponse, "description": "Invalid request values."},
            500: {"model": ErrorResponse, "description": "Unexpected internal error."},
        },
    )
    application.state.settings = settings
    application.state.ready = False
    application.add_middleware(RequestContextMiddleware)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.include_router(health_router)
    return application
