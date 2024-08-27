# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/azure-functions/python:4-python3.11
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/fleetcare-data-harvest

ENV AzureWebJobsScriptRoot=/app \
  AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /app
ARG POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir --root-user-action=ignore poetry==${POETRY_VERSION}
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --only main
COPY function_app.py host.json  ./
