# syntax=docker/dockerfile:1
FROM dhi.io/python:3.13-debian13-dev AS build-stage
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/fleetcare-data-harvest

# Copy and configure uv, to install dependencies
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/
WORKDIR /app
# Install project dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --link-mode=copy --compile-bytecode --no-python-downloads --frozen \
  # Remove uv and lockfile after use
  && rm -rf /bin/uv \
  && rm uv.lock

COPY entrypoint.sh gunicorn.py ./
COPY fleetcare_data_harvest ./fleetcare_data_harvest

ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Image runs as the nonroot user
EXPOSE 8080

# Use entrypoint.sh because we need to single-quote the run command.
ENTRYPOINT ["/bin/bash", "entrypoint.sh"]
