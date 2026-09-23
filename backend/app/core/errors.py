from collections.abc import Mapping
from http import HTTPStatus

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


class FieldError(BaseModel):
    field: str
    code: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    fields: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str


class ApiError(Exception):
    """Only use fixed, safe messages and codes, never exception or input values."""

    def __init__(
        self, status: int, code: str, message: str, headers: Mapping[str, str] | None = None
    ) -> None:
        self.status, self.code, self.message, self.headers = status, code, message, headers


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(
        request.state.request_id, exc.status, exc.code, exc.message, headers=exc.headers
    )


async def database_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        request.state.request_id,
        503,
        "service_unavailable",
        "The service is temporarily unavailable. Try again later.",
    )


def error_response(
    request_id: str,
    status_code: int,
    code: str,
    message: str,
    *,
    fields: list[FieldError] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, fields=fields), request_id=request_id
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers={**(headers or {}), "X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    try:
        status = HTTPStatus(exc.status_code)
        code, message = status.name.lower(), status.phrase
    except ValueError:
        code, message = "http_error", "The request could not be completed."
    return error_response(
        request.state.request_id, exc.status_code, code, message, headers=exc.headers
    )


_VALIDATION_MESSAGES = {
    "missing": "This field is required.",
    "string_type": "Enter a string.",
    "int_parsing": "Enter an integer.",
    "int_type": "Enter an integer.",
    "bool_parsing": "Enter a boolean.",
    "string_too_short": "This value is too short.",
    "string_too_long": "This value is too long.",
    "greater_than": "This value is outside the allowed range.",
    "less_than": "This value is outside the allowed range.",
    "json_invalid": "The request body must contain valid JSON.",
    "extra_forbidden": "This field is not allowed.",
}


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = []
    for error in exc.errors():
        code = error["type"] if error["type"] in _VALIDATION_MESSAGES else "invalid_value"
        fields.append(
            FieldError(
                field=".".join(str(part) for part in error["loc"]),
                code=code,
                message=_VALIDATION_MESSAGES.get(code, "Enter a valid value."),
            )
        )
    return error_response(
        request.state.request_id,
        422,
        "validation_error",
        "The request contains invalid values.",
        fields=fields,
    )
