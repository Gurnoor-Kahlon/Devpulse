FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.lock .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --require-hashes -r requirements.lock

FROM dependencies AS test-dependencies
COPY requirements-dev.lock .
RUN /opt/venv/bin/pip install --require-hashes -r requirements-dev.lock

FROM python:3.13.15-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26 AS runtime
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 devpulse && useradd --uid 10001 --gid devpulse --no-create-home --home-dir /tmp --shell /usr/sbin/nologin devpulse
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
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
