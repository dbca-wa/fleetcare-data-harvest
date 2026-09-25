# syntax=docker/dockerfile:1
# Args to centralise versions.
ARG PYTHON_VERSION=3.13-debian13-dev

# ---- Builder stage ----
FROM dhi.io/python:${PYTHON_VERSION} AS builder

RUN <<EOF
set -euxo pipefail
apt-get update
apt-get install -y --no-install-recommends \
  gcc \
  g++
EOF

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --frozen

# ---- Runtime stage ----
FROM dhi.io/python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.title="fleetcare-data-harvest" \
  org.opencontainers.image.description="Fleetcare data harvest webhook" \
  org.opencontainers.image.source="https://github.com/dbca-wa/fleetcare-data-harvest" \
  org.opencontainers.image.vendor="DBCA" \
  org.opencontainers.image.authors="asi@dbca.wa.gov.au"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy installed virtualenv from builder
COPY --from=builder /app /app

# Copy the remaining project files to finish building the project
COPY --chown=nonroot:nonroot entrypoint.sh gunicorn.py ./
COPY --chown=nonroot:nonroot fleetcare_data_harvest ./fleetcare_data_harvest

# Compile scripts
RUN python -m compileall fleetcare_data_harvest

# Image runs as the nonroot user
USER nonroot
EXPOSE 8080

# Use entrypoint.sh because we need to single-quote the run command.
ENTRYPOINT ["/bin/bash", "entrypoint.sh"]
