# syntax=docker/dockerfile:1
# Args to centralise versions.
# PYTHON_VERSION is the DHI *runtime* tag (distroless: no shell, no apt).
# The builder uses the matching -dev tag, which has a shell and apt.
ARG PYTHON_VERSION=3.13-debian13
ARG PYTHON_BUILD_VERSION=${PYTHON_VERSION}-dev
ARG UV_VERSION=0.13

# ---- Stages ----
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM dhi.io/python:${PYTHON_BUILD_VERSION} AS builder

# ---- Builder stage ----
COPY --link --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Compiler needed to build dependencies from source.
#   * gunicorn-h1c (gunicorn[fast]) publishes no cp313 wheel on any platform, so
#     its C extension is always compiled from the sdist -> gcc.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
  apt-get update && apt-get install -y --no-install-recommends \
  gcc

# Install only runtime dependencies into /app/.venv. The venv path must match
# the runtime stage: uv writes absolute shebangs into console scripts such as
# gunicorn.
RUN --mount=type=cache,target=/root/.cache/uv \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  uv sync --locked --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --no-install-project

# ---- Runtime stage ----
# The runtime (non-dev) image is distroless: no shell, no package manager.
FROM dhi.io/python:${PYTHON_VERSION} AS runtime
LABEL org.opencontainers.image.title="fleetcare-data-harvest" \
  org.opencontainers.image.description="Fleetcare data harvest webhook" \
  org.opencontainers.image.source="https://github.com/dbca-wa/fleetcare-data-harvest" \
  org.opencontainers.image.vendor="DBCA" \
  org.opencontainers.image.authors="asi@dbca.wa.gov.au"

WORKDIR /app

# Copy installed virtualenv from builder (same path, so console-script shebangs stay valid).
# --chown must be numeric here: a link layer can't resolve usernames from the
# base image's /etc/passwd.
COPY --link --chown=65532:65532 --from=builder /app/.venv /app/.venv

# Copy the application files
COPY --link --chown=65532:65532 gunicorn.py ./
COPY --link --chown=65532:65532 fleetcare_data_harvest ./fleetcare_data_harvest

# Runtime rootfs is read-only (see kustomize/base/webserver.yml), so .pyc can
# never be written in the pod. Suppress the attempt; the app is small enough
# that per-import compilation is not worth precompiling at build time.
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PATH="/app/.venv/bin:$PATH"

# Image runs as the nonroot user
USER nonroot
EXPOSE 8080

ENTRYPOINT ["gunicorn", "fleetcare_data_harvest:create_app()", "--config", "gunicorn.py"]
