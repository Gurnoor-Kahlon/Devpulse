FROM python:3.13.16-alpine3.24@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.lock requirements-container.lock requirements-container-build.lock ./
# Build psycopg against vendor-maintained libraries instead of bundled wheel libraries.
RUN apk add --no-cache gcc musl-dev postgresql18-dev=18.6-r0 libssl3=3.5.9-r0 libcrypto3=3.5.9-r0 \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install --require-hashes -r requirements.lock \
    && /opt/venv/bin/pip install --require-hashes -r requirements-container-build.lock \
    && /opt/venv/bin/pip install --require-hashes --no-deps --no-build-isolation -r requirements-container.lock \
    && /opt/venv/bin/pip uninstall -y psycopg-binary setuptools wheel

FROM dependencies AS test-dependencies
COPY requirements-dev.lock .
RUN /opt/venv/bin/pip install --require-hashes -r requirements-dev.lock \
    && /opt/venv/bin/pip uninstall -y psycopg-binary

FROM python:3.13.16-alpine3.24@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PSYCOPG_IMPL=c
RUN apk add --no-cache libpq=18.6-r0 libssl3=3.5.9-r0 libcrypto3=3.5.9-r0
RUN addgroup -g 10001 devpulse && adduser -u 10001 -G devpulse -D -H -h /tmp -s /sbin/nologin devpulse
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
# Runtime images execute locked application code; installers belong only in build/test stages.
RUN rm -rf /usr/local/lib/python3.13/ensurepip \
    /usr/local/lib/python3.13/site-packages/pip* /usr/local/bin/pip* \
    /opt/venv/lib/python3.13/site-packages/pip* /opt/venv/bin/pip*
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY container ./container
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]

FROM runtime AS tests
COPY --from=test-dependencies /opt/venv /opt/venv
COPY tests ./tests
COPY pyproject.toml ./pyproject.toml
CMD ["python", "-m", "pytest", "--run-integration", "--run-worker", "--run-mailpit", "-o", "cache_dir=/tmp/pytest-cache", "-q"]
