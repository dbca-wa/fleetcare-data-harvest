# syntax=docker/dockerfile:1
# Args to centralise versions.
# PYTHON_VERSION is the DHI runtime tag; the builder stage appends "-dev".
ARG PYTHON_VERSION=3.13-debian13
ARG UV_VERSION=0.13

# ---- Stages ----
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM dhi.io/python:${PYTHON_VERSION}-dev AS builder

# ---- Builder stage ----
# gcc is required: gunicorn[fast] -> gunicorn-h1c has no wheel for every
# platform and builds its extension from source.
COPY --from=uv /uv /bin/uv

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
  apt-get update && apt-get install -y --no-install-recommends gcc

# Install only runtime dependencies into /app/.venv. The venv path must match
# the runtime stage: uv writes absolute shebangs into console scripts such as
# gunicorn.
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  uv sync --locked --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads

# ---- Runtime stage ----
# The runtime (non-dev) image is distroless: no shell, no package manager.
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

# Copy installed virtualenv from builder (same path, so console-script
# shebangs stay valid).
COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/.venv

# Copy the application files
COPY --chown=nonroot:nonroot gunicorn.py ./
COPY --chown=nonroot:nonroot fleetcare_data_harvest ./fleetcare_data_harvest

# Compile scripts. Exec form because the runtime image has no shell; the base
# image's default user is nonroot, so no root-owned bytecode is created.
RUN ["python", "-m", "compileall", "-q", "fleetcare_data_harvest"]

# Image runs as the nonroot user
USER nonroot
EXPOSE 8080

ENTRYPOINT ["/app/.venv/bin/gunicorn", "fleetcare_data_harvest:create_app()", "--config", "gunicorn.py"]
