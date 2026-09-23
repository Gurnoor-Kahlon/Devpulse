# API foundation

DevPulse currently exposes process health and development API documentation.
Database access, authentication, monitors, and jobs belong to later milestones.

## Application lifecycle

`app.factory.create_app(settings=None)` constructs an isolated FastAPI instance.
Passing a validated `Settings` object allows tests to configure their own app.
The factory does not open network connections. `app.main:app` remains the
Uvicorn entrypoint.

The lifespan configures process logging, marks application startup complete,
and clears readiness on shutdown. The application never enables debug traceback
responses, including in development.

| Endpoint            | Behavior                                                                       |
| ------------------- | ------------------------------------------------------------------------------ |
| `GET /health/live`  | `200` with `{"status":"ok"}` when the API can handle a request                 |
| `GET /health/ready` | `200` with `{"status":"ok"}` after application startup; `503` before readiness |
| `GET /docs`         | Swagger UI in development/test when enabled                                    |
| `GET /openapi.json` | Generated schema in development/test when enabled                              |

Both health endpoints are intentionally unversioned. Readiness does **not** yet
check PostgreSQL, Redis, workers, or monitored targets. Database readiness will
arrive with milestone 4. Future business endpoints will use `/api/v1`; that
namespace has no routes yet. Unknown routes, including `/`, return a structured 404. No frontend-to-backend proxy is introduced in this milestone.

## Configuration

Copy `backend/.env.example` to `backend/.env` only if overriding defaults.
Process environment variables override file values. The backend reads only its
own environment file, not the frontend or repository-root environment files.

| Variable                    | Default       | Allowed values                      |
| --------------------------- | ------------- | ----------------------------------- |
| `DEVPULSE_ENVIRONMENT`      | `development` | `development`, `test`, `production` |
| `DEVPULSE_LOG_LEVEL`        | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DEVPULSE_API_DOCS_ENABLED` | `true`        | Boolean                             |

Interactive documentation and the schema endpoint are always disabled in
production, even when the documentation flag is true. Health endpoints remain
available. Settings are validated once per app construction and cannot be
mutated afterward. Invalid startup configuration reports setting names without
echoing their values. No secrets are needed at this stage.

## Request IDs and errors

Every HTTP request receives a fresh server-generated UUID in `X-Request-ID`.
Incoming request IDs are ignored: they are untrusted input, not a log field.
The same ID appears in the request's structured log and in an error response.
Request context is isolated across asynchronous requests and reset after use.
Responses use `Cache-Control: no-store` by default.

Errors have this shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid values.",
    "fields": [
      {
        "field": "body.name",
        "code": "missing",
        "message": "This field is required."
      }
    ]
  },
  "request_id": "<server-generated UUID>"
}
```

`fields` is present only for validation failures. The field example illustrates
the shared contract; it is not an implemented monitor or account endpoint.

- Request validation failures return `422` and safe field descriptions. Input
  values, validation context, and custom validator exception messages are omitted.
- Framework HTTP errors use stable standard codes such as `not_found`,
  `method_not_allowed`, and `service_unavailable`. Exception details are private;
  protocol headers such as `Allow` and `Retry-After` are preserved.
- Unexpected failures, including invalid response models, return `500` with
  `internal_error` and safe generic text.
- If headers have already been sent, a failure cannot replace that response.
  The middleware records the failure and raises a sanitized exception so the
  server can abort delivery instead of appending another response.

The generated OpenAPI schema includes the health and error response models.

## Logging and privacy

Application logs are JSON lines on stdout with UTC timestamps, severity, and
an event name. Lifecycle events report startup/shutdown. Request events contain:

- Server-generated request ID.
- Standard HTTP method (unrecognized methods become `OTHER`).
- Matched route template, such as `/monitors/{id}`, or `<unmatched>`.
- HTTP status and elapsed milliseconds.
- A stable internal error code for unexpected failures.

Do not pass user-supplied values into these structured fields. Log only the
declared metadata. The formatter omits free-form messages, exception text,
tracebacks, and arbitrary extras because any of those can contain credentials.
Server exceptions still produce a safe `server_error` event. Increasing the log
level does not enable sensitive payload logging.

Raw URLs, query strings, path parameter values, request bodies, headers,
cookies, passwords, tokens, and environment values are not logged. Uvicorn's raw
access logger is disabled after application startup; the request middleware
provides its safe replacement. HTTPX/HTTPCore informational logs are also muted.
Early Uvicorn process startup messages may precede application JSON logging.

## Verification

From `backend/` with the virtual environment active:

```bash
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
```

The suite exercises startup configuration, independent factory state, health
lifecycle, documentation settings, error contracts, concurrent request IDs,
late response failures, and sensitive-value exclusion. Test fixtures use
synthetic canary strings and test-only routes, not real credentials or services.
